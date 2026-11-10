// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-saved-browser');
const webRoot = process.argv[3] ? resolve(process.argv[3]) : null;
await mkdir(output, {recursive: true});
const profile = await mkdtemp(join(tmpdir(), 'sipi-browser-'));
const owned = [], errors = [], remoteRequests = [], apiRequests = [], workerTargets = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(fn, label, timeout = 90000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { const value = await fn(); if (value) return value; await pause(150); }
  throw new Error('Timed out: ' + label);
}
class CDP {
  constructor(url) {
    this.id = 0; this.pending = new Map(); this.ws = new WebSocket(url);
    this.ready = new Promise((resolve,reject) => {this.ws.addEventListener('open',resolve,{once:true});this.ws.addEventListener('error',reject,{once:true});});
    this.ws.addEventListener('message', event => {
      const data = JSON.parse(event.data);
      if (data.id) { const p = this.pending.get(data.id); if(p){clearTimeout(p.timer);this.pending.delete(data.id);data.error?p.reject(new Error(JSON.stringify(data.error))):p.resolve(data.result);} }
      else if(data.method === 'Target.attachedToTarget') {
        const {sessionId,targetInfo}=data.params;
        if(targetInfo.type==='worker') workerTargets.push(targetInfo.url);
        (async()=>{
          await this.call('Network.enable',{},sessionId);
          if(this.blockedWorkerURLs?.length) await this.call('Network.setBlockedURLs',{urls:this.blockedWorkerURLs},sessionId);
          await this.call('Runtime.enable',{},sessionId);
          await this.call('Runtime.runIfWaitingForDebugger',{},sessionId);
        })().catch(error=>errors.push({workerAttach:error.message}));
      }
      else if(data.method === 'Runtime.exceptionThrown') errors.push(data.params.exceptionDetails);
      else if(data.method === 'Network.requestWillBeSent') {
        const url = data.params.request.url;
        if (/^https?:/.test(url) && !url.startsWith('http://127.0.0.1:')) remoteRequests.push(url);
        if (url.includes('/api/')) apiRequests.push({url,method:data.params.request.method});
      }
    });
  }
  async call(method, params = {}, sessionId) {
    await this.ready; const id = ++this.id;
    return new Promise((resolve,reject) => {const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('CDP timeout '+method));},30000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
  }
  async evaluate(expression) {
    const r=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
    if(r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
}
let cdp, serverLog = '';
try {
  const serverArgs = webRoot ? ['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot] : ['workbench/desktop/main.py','--no-browser'];
  const server = spawn(process.env.SIPI_PYTHON || 'python', serverArgs, {env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});
  owned.push(server);server.stdout.on('data',data=>serverLog+=data);server.stderr.on('data',data=>serverLog+=data);
  const url=await until(()=>serverLog.match(webRoot ? /http:\/\/127\.0\.0\.1:\d+\// : /http:\/\/127\.0\.0\.1:\d+\/#token=[\w-]+/)?.[0],'server launch');
  const found=spawnSync('which',['chromium','google-chrome','chromium-browser'],{encoding:'utf8'});
  const chrome=process.env.CHROME || found.stdout?.trim().split('\n')[0];
  assert.ok(chrome,'Chrome/Chromium is required');
  const browser=spawn(chrome,['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-background-networking','--no-first-run','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});owned.push(browser);
  const port=await until(async()=>{try{return (await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];}catch{return null;}},'browser launch');
  const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  cdp=new CDP(targets.find(target=>target.type==='page').webSocketDebuggerUrl);
  await cdp.call('Runtime.enable');await cdp.call('Network.enable');await cdp.call('Page.enable');
  await cdp.call('Target.setAutoAttach',{autoAttach:true,waitForDebuggerOnStart:true,flatten:true});
  const downloads=join(profile,'downloads');await mkdir(downloads);
  await cdp.call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:1400,height:1100,deviceScaleFactor:1,mobile:false});
  const inputCases = spawnSync(process.env.SIPI_PYTHON || 'python', ['workbench/tests/saved_cases.py'], {encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(inputCases.status,0,inputCases.stderr);
  const cases = JSON.parse(inputCases.stdout);
  const target = new URL(url); target.pathname='/saved.html';
  await cdp.call('Page.navigate',{url:target.href});
  await until(()=>cdp.evaluate('!!document.querySelector("#run") && document.readyState==="complete"'),'saved page');
  const status = () => cdp.evaluate('document.querySelector("#status").textContent');
  async function input(text) {
    await cdp.evaluate(`document.querySelector('#input-text').value=${JSON.stringify(text)};document.querySelector('#input-text').dispatchEvent(new Event('input'));`);
  }
  async function loadExample(id, expected) {
    const before=await cdp.evaluate('document.querySelector("#input-text").value');
    await cdp.evaluate(`document.querySelector('#example-choice').value=${JSON.stringify(id)};document.querySelector('#example-choice').dispatchEvent(new Event('change'));`);
    assert.equal(await cdp.evaluate('document.querySelector("#input-text").value'),before,'selection alone keeps edits');
    assert.ok((await cdp.evaluate('document.querySelector("#example-help").textContent')).length>20);
    await cdp.evaluate('document.querySelector("#example").click()');
    assert.deepEqual(await cdp.evaluate('JSON.parse(document.querySelector("#input-text").value)'),expected);
    assert.equal(await cdp.evaluate('document.querySelector("#output").hidden && document.querySelector("#save-result").disabled && document.querySelector("#material-results").hidden'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#characteristic").checked || document.querySelector("#modes").checked'),false);
  }
  async function checkResultView(out) {
    const failed=out.status==='failed' && ['sipi.impedance-design/1','sipi.impedance-design/2','sipi.impedance-design/3'].includes(out.input.schema);
    const supported=failed || out.error===null && ['sipi.impedance-study/4','sipi.impedance-design/3','sipi.pair-impedance-design/2'].includes(out.input.schema);
    const view=await cdp.evaluate(`(()=>{const c=document.querySelector('#material-results');return {hidden:c.hidden,text:c.textContent,tables:Array.from(c.querySelectorAll('table'),t=>Array.from(t.querySelectorAll('tbody tr'),r=>Array.from(r.cells,cell=>({text:cell.textContent,value:cell.dataset.value??null}))))};})()`);
    assert.equal(view.hidden,!supported);
    if(!supported) {assert.deepEqual(view.tables,[]);return;}
    const r=out.result;let expected;
    if(failed){
      const names={z0:'Single-ended',z_diff:'Differential',z_common:'Common',z_diff_forward:'Differential launch'};
      expected=[[[names[out.input.quantity],out.input.target_ohm,out.input.tolerance_ohm]],[[out.input.variable,...out.input.bounds]]];
      if(out.error.history.length)expected.push(out.error.history.map((row,index)=>[index,row.stage,row.parameter,row.value]));
      if(out.error.type==='GoalMeshSizeLimitError')expected.push([[out.error.attempts,out.error.stage,out.error.parameter,null,out.error.cause_type]]);
      assert.match(view.text,/target not accepted/);assert.ok(view.text.includes(out.error.message));
    } else if(out.input.schema==='sipi.impedance-study/4') {
      const names=out.input.sampling.variables.map(v=>v.name);
      expected=[r.rows.map(row=>[row.index,...names.map(name=>{
        const binding=out.input.material_variables[name];
        if(!binding)return row.parameters[name];
        return binding.path.reduce((value,key)=>value[key],row.material_evaluation.materials[binding.region].parameters);
      }),row.value,row.error===null?'Calculated':row.error_type+': '+row.error])];
      if(r.failed) {assert.equal(r.summary,null);assert.match(view.text,/no aggregate summary/);}
      else expected.push([['Minimum',r.summary.minimum],['Maximum',r.summary.maximum],['Mean',r.summary.mean],['Sample standard deviation',r.summary.sample_std],['5th percentile',r.summary.p05],['95th percentile',r.summary.p95]]);
    } else if(out.input.schema==='sipi.impedance-design/3') {
      expected=[[[out.input.variable,r.parameter]],[['Requested',r.target,r.value,r.residual,out.input.tolerance_ohm],['Refined',r.target,r.refined_value,r.refined_residual,out.input.tolerance_ohm]]];
    } else {
      expected=[out.input.variables.map((v,i)=>[v.name,r.parameters[i]]),...r.quantities.map((_,i)=>[
        ['Requested',r.targets_ohm[i],r.impedances_ohm[i],r.residuals_ohm[i],r.tolerances_ohm[i]],
        ['Refined',r.targets_ohm[i],r.refined_impedances_ohm[i],r.refined_residuals_ohm[i],r.tolerances_ohm[i]]])];
    }
    assert.deepEqual(view.tables,expected.map(rows=>rows.map(row=>row.map(value=>({text:value===null?'—':typeof value==='number'?String(Number(value.toPrecision(7))):value,value:typeof value==='number'?String(value):null})))));
    assert.match(view.text,/7 significant digits/);
  }
  async function checkViewFallbackAndText(out) {
    const before=await cdp.evaluate('document.querySelector("#output").textContent');
    const observed=await cdp.evaluate(`(async()=>{
      const {renderMaterialResults}=await import('./material-results.js'),c=document.querySelector('#material-results');
      const original=${JSON.stringify(out)},mutations=[v=>v.input.schema='future/1',v=>v.result=null,v=>v.result.parameter=null,v=>v.result.value=Infinity];
      const hidden=mutations.map(change=>{const copy=structuredClone(original);change(copy);renderMaterialResults(c,copy);return c.hidden&&c.children.length===0;});
      const hostile=structuredClone(original);hostile.input.variable='<img src=x onerror="window.materialViewInjected=true">';
      renderMaterialResults(c,hostile);const inert=c.textContent.includes(hostile.input.variable)&&c.querySelector('img')===null&&window.materialViewInjected===undefined;
      renderMaterialResults(c,original);return {hidden,inert,unchanged:JSON.stringify(original)===${JSON.stringify(JSON.stringify(out))}};
    })()`);
    assert.ok(observed.hidden.every(Boolean));assert.equal(observed.inert,true);assert.equal(observed.unchanged,true);
    assert.equal(await cdp.evaluate('document.querySelector("#output").textContent'),before);
    await checkResultView(out);
  }
  async function calculate() {
    assert.equal(await cdp.evaluate('document.querySelector("#run").click();document.querySelector("#example-choice").disabled && document.querySelector("#example").disabled'),true);
    await until(()=>cdp.evaluate('!document.querySelector("#run").disabled'),'calculation finished',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#example-choice").disabled || document.querySelector("#example").disabled'),false);
    assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),false,await status());
    const execution=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
    await checkResultView(execution);return execution;
  }
  assert.deepEqual(await cdp.evaluate('Array.from(document.querySelector("#example-choice").options, item=>item.value)'),
    ['rlc','constant-target','debye-target','pair-target','material-sweep','correlated-study','normal-study']);
  assert.equal(await cdp.evaluate('document.querySelector("label[for=example-choice]") !== null'),true);
  const untouched=await cdp.evaluate('document.querySelector("#input-text").value');
  await cdp.evaluate('document.querySelector("#example-choice").focus()');
  for(const key of ['ArrowDown','ArrowUp']) {
    await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key,code:key,windowsVirtualKeyCode:key==='ArrowDown'?40:38});
    await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key,code:key,windowsVirtualKeyCode:key==='ArrowDown'?40:38});
    assert.equal(await cdp.evaluate('document.querySelector("#example-choice").value'),key==='ArrowDown'?'constant-target':'rlc');
    assert.equal(await cdp.evaluate('document.querySelector("#input-text").value'),untouched);
  }
  await cdp.evaluate('document.querySelector("#example").click();document.querySelector("#check").click()');
  await until(async()=>(await status()).startsWith('Input checked'),'checked input',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#save-input").disabled'),false);
  await cdp.evaluate('document.querySelector("#save-input").click()');
  const savedInput=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-input.json'),'utf8'));}catch{}},'input download');
  assert.equal(savedInput.schema,'sipi.lumped-network/1');
  let result=await calculate();
  assert.equal(result.status,'complete');assert.deepEqual(result.input,cases.expected.input);
  for(const part of ['real','imag']) for(let f=0;f<2;f++) for(let i=0;i<2;i++) for(let j=0;j<2;j++)
    assert.ok(Math.abs(result.result.network.s[part][f][i][j]-cases.expected.result.network.s[part][f][i][j])<=1e-12);
  await cdp.evaluate('document.querySelector("#save-result").click()');
  const downloaded=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-result.json'),'utf8'));}catch{}},'result download');
  assert.deepEqual(downloaded.execution,result);
  await writeFile(join(output,'saved-analysis.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  const capacitance3d = [];
  for (const item of cases.capacitance3d) {
    await input(item.text);
    await cdp.evaluate('document.querySelector("#check").click()');
    await until(async()=>(await status()).startsWith('Input checked'),'3D normalization',180000);
    const got = await calculate(), expected = item.expected;
    assert.deepEqual(got.input,expected.input);
    assert.equal(got.status,'complete'); assert.equal(got.result.model,'bounded-static-3d');
    assert.deepEqual(got.result.names,expected.result.names);
    const ratios = {};
    for (const key of ['capacitance_f','energy_capacitance_f','ground_charge_c_at_unit_voltage']) {
      const a=[got.result[key]].flat(3), b=[expected.result[key]].flat(3);
      assert.equal(a.length,b.length);
      const ratio=Math.max(...a.map((v,i)=>Math.abs(v-b[i])))/Math.max(...b.map(Math.abs));
      assert.ok(Number.isFinite(ratio)&&ratio<=1e-11,key+': '+ratio); ratios[key]=ratio;
    }
    for (const value of Object.values(got.result.consistency)) assert.ok(value>=0&&value<=1e-8);
    await rm(join(downloads,'sipi-result.json'));
    await cdp.evaluate('document.querySelector("#save-result").click()');
    const exported=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-result.json'),'utf8'));}catch{}},'3D result export');
    assert.deepEqual(exported.execution,got);
    capacitance3d.push({name:item.name,ratios});
  }
  const materialGoals = [];
  function compareMaterial(actual, expected, path='result') {
    if(typeof expected === 'number') {
      assert.equal(typeof actual,'number',path);
      assert.ok(Number.isFinite(actual),path);
      assert.ok(Math.abs(actual-expected)<=1e-10*Math.max(Math.abs(expected),1e-30),path);
    } else if(expected !== null && typeof expected === 'object') {
      assert.deepEqual(Object.keys(actual),Object.keys(expected),path);
      for(const key of Object.keys(expected)) compareMaterial(actual[key],expected[key],path+'.'+key);
    } else assert.equal(actual,expected,path);
  }
  for(const item of cases.material_goals) {
    await loadExample(item.name==='constant'?'constant-target':'debye-target',item.expected.input);
    await cdp.evaluate('document.querySelector("#check").click()');
    await until(async()=>(await status()).startsWith('Input checked'),'material normalization',180000);
    await rm(join(downloads,'sipi-input.json'),{force:true});
    await cdp.evaluate('document.querySelector("#save-input").click()');
    const saved=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-input.json'),'utf8'));}catch{}},'material input export');
    assert.deepEqual(saved,item.expected.input);
    const started=Date.now();const got=await calculate();const seconds=(Date.now()-started)/1000;
    assert.equal(got.status,'complete');assert.equal(got.error,null);
    assert.deepEqual(got.input,item.expected.input);
    assert.deepEqual(got.result.document,item.expected.result.document);
    assert.deepEqual(got.result.material_evaluation,item.expected.result.material_evaluation);
    assert.deepEqual(got.result.history.map(row=>[row.parameter,row.stage]),item.expected.result.history.map(row=>[row.parameter,row.stage]));
    compareMaterial(got.result,item.expected.result);
    assert.ok(Math.abs(got.result.residual)<=1 && Math.abs(got.result.refined_residual)<=1);
    assert.equal(got.result.history.at(-1).stage,'refinement');
    await rm(join(downloads,'sipi-result.json'),{force:true});
    await cdp.evaluate('document.querySelector("#save-result").click()');
    const exported=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-result.json'),'utf8'));}catch{}},'material result export');
    assert.deepEqual(exported.execution,got);
    await writeFile(join(output,'material-'+item.name+'.json'),JSON.stringify(exported,null,2));
    if(item.name==='constant') await checkViewFallbackAndText(got);
    materialGoals.push({name:item.name,seconds,parameter:got.result.parameter,history:got.result.history.length});
  }
  const materialBatch = [];
  function compareStudy(actual, expected, path='study') {
    if(typeof expected === 'number') {
      assert.equal(typeof actual,'number',path);
      assert.ok(Number.isFinite(actual),path);
      assert.ok(Math.abs(actual-expected)<=Math.max(1e-14,1e-10*Math.abs(expected)),path);
    } else if(expected !== null && typeof expected === 'object') {
      assert.deepEqual(Object.keys(actual),Object.keys(expected),path);
      for(const key of Object.keys(expected)) compareStudy(actual[key],expected[key],path+'.'+key);
    } else assert.equal(actual,expected,path);
  }
  function checkPairMaterial(execution, expected) {
    assert.equal(execution.status,'complete');assert.equal(execution.error,null);
    assert.deepEqual(execution.input,expected.input);
    const r=execution.result, e=expected.result;
    assert.deepEqual(r.quantities,['z_diff','z_common']);
    assert.deepEqual(r.targets_ohm,[100,34]);assert.deepEqual(r.tolerances_ohm,[1,.5]);
    assert.deepEqual(r.input,e.input);assert.deepEqual(r.refined_input,e.refined_input);
    assert.ok(r.evaluations<=64 && r.evaluations===r.history.length);
    assert.ok(r.history.length>2);assert.deepEqual(r.history[0].parameters,[3,3]);
    assert.equal(r.history.at(-1).stage,'refinement');
    function model(parameters, evaluation) {
      const wanted=structuredClone(execution.input.material_evaluation);
      for(const [index,axis] of ['axis1','axis2'].entries()) {
        assert.ok(parameters[index]>=2 && parameters[index]<=6);
        wanted.materials.dielectric.parameters[axis].parameters.eps_r=parameters[index];
      }
      assert.deepEqual(evaluation,wanted);
    }
    model(r.parameters,r.material_evaluation);
    for(const row of r.history) {
      model(row.parameters,row.material_evaluation);
      assert.ok(row.stage==='search' || row.stage==='refinement');
      assert.deepEqual(row.input,row.stage==='search'?r.input:r.refined_input);
      assert.ok(row.impedances_ohm.every(value=>Number.isFinite(value)&&value>0));
    }
    const selected=r.history.find(row=>row.stage==='search' && row.parameters.every((v,i)=>v===r.parameters[i]));
    assert.ok(selected);assert.deepEqual(selected.impedances_ohm,r.impedances_ohm);
    assert.deepEqual(r.history.at(-1).parameters,r.parameters);
    assert.deepEqual(r.history.at(-1).impedances_ohm,r.refined_impedances_ohm);
    for(let i=0;i<2;i++) {
      assert.ok(Math.abs(r.parameters[i]-e.parameters[i])<=1e-4*Math.abs(e.parameters[i]));
      for(const [values,residuals] of [['impedances_ohm','residuals_ohm'],['refined_impedances_ohm','refined_residuals_ohm']]) {
        assert.equal(r[residuals][i],r[values][i]-r.targets_ohm[i]);
        assert.ok(Math.abs(r[residuals][i])<=r.tolerances_ohm[i]);
        assert.ok(Math.abs(r[values][i]-e[values][i])<=1e-5*Math.abs(e[values][i]));
      }
    }
  }
  for(const item of cases.material_batch) {
    const exampleId={'pair-goal':'pair-target',constant:'material-sweep',tensor:'correlated-study'}[item.name];
    if(exampleId) await loadExample(exampleId,item.expected.input);
    else await input(item.text);
    if(exampleId==='pair-target') await writeFile(join(output,'saved-material-example.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
    await cdp.evaluate('document.querySelector("#check").click()');
    await until(async()=>(await status()).startsWith('Input checked'),'batch material normalization',180000);
    await rm(join(downloads,'sipi-input.json'),{force:true});
    await cdp.evaluate('document.querySelector("#save-input").click()');
    const saved=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-input.json'),'utf8'));}catch{}},'batch material input export');
    assert.deepEqual(saved,item.expected.input);
    const started=Date.now();const got=await calculate();const seconds=(Date.now()-started)/1000;
    assert.deepEqual(got.input,item.expected.input);
    if(item.name==='pair-goal') checkPairMaterial(got,item.expected);
    else {
      compareStudy(got,item.expected);
      if(item.name==='mixed-normal') {
        assert.equal(got.status,'incomplete');assert.equal(got.result.failed,2);
        assert.equal(got.result.summary,null);
        assert.deepEqual(got.result.rows.map(row=>row.error_type),item.expected.result.rows.map(row=>row.error_type));
      } else assert.equal(got.status,'complete');
    }
    await rm(join(downloads,'sipi-result.json'),{force:true});
    await cdp.evaluate('document.querySelector("#save-result").click()');
    const exported=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-result.json'),'utf8'));}catch{}},'batch material result export');
    assert.deepEqual(exported.execution,got);
    await writeFile(join(output,'batch-'+item.name+'.json'),JSON.stringify(exported,null,2));
    if(item.name==='pair-goal' || item.name==='mixed-normal') await writeFile(join(output,'result-table-'+item.name+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
    if(item.name==='pair-goal' || item.name==='mixed-normal') {
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
      assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
      await writeFile(join(output,'result-table-'+item.name+'-mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
      await cdp.call('Emulation.setDeviceMetricsOverride',{width:1400,height:1100,deviceScaleFactor:1,mobile:false});
    }
    if(item.name==='mixed-normal') {
      const probe=await cdp.evaluate(`(async()=>{
        const {renderMaterialResults}=await import('./material-results.js'),c=document.querySelector('#material-results'),original=${JSON.stringify(got)};
        const partial=structuredClone(original);partial.result.summary={mean:50};renderMaterialResults(c,partial);const hidden=c.hidden;
        const hostile=structuredClone(original),failed=hostile.result.rows.find(row=>row.error!==null);
        failed.error='<svg onload="window.materialErrorInjected=true">';renderMaterialResults(c,hostile);
        const inert=c.textContent.includes(failed.error)&&c.querySelector('svg')===null&&window.materialErrorInjected===undefined;
        renderMaterialResults(c,original);return {hidden,inert};
      })()`);
      assert.deepEqual(probe,{hidden:true,inert:true});await checkResultView(got);
    }
    materialBatch.push({name:item.name,seconds,status:got.status});
  }
  await input('{"schema":"sipi.lumped-network/1","schema":"invalid"}');
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#material-results").hidden'),true);
  await cdp.evaluate('document.querySelector("#check").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#check").disabled'),'duplicate rejection');
  assert.ok((await status()).toLowerCase().includes('duplicate'));
  assert.equal(await cdp.evaluate('document.querySelector("#save-input").disabled'),true);
  // Real file input, preserving raw text until the Python validator sees it.
  const importPath=join(profile,'분석 input.json');await writeFile(importPath,cases.study);
  const dom=await cdp.call('DOM.getDocument');
  const file=await cdp.call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[importPath]});
  await until(async()=>(await status()).startsWith('File opened'),'file input');
  result=await calculate();
  assert.equal(result.status,'incomplete');assert.equal(result.result.summary,null);
  assert.equal(result.result.rows.length,3);assert.ok(result.result.failed>0);
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),false);
  await input(cases.goal);result=await calculate();
  assert.equal(result.status,'failed');assert.equal(result.result,null);
  assert.equal(result.error.history.at(-1).stage,'refinement');
  assert.ok((await status()).startsWith('Target not met:'));
  await writeFile(join(output,'retained-target-failure.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await input(cases.mesh_goal);result=await calculate();
  assert.equal(result.status,'failed');assert.equal(result.result,null);
  assert.equal(result.error.type,'GoalMeshSizeLimitError');
  assert.equal(result.error.cause_type,'MeshSizeLimitError');
  assert.equal(result.error.stage,'search');assert.equal(result.error.attempts,1);
  assert.equal(result.error.parameter,.0002);assert.deepEqual(result.error.history,[]);
  assert.deepEqual(result.error.input.mesh,{edge_size:1e-12,far_size:.0002,grade:.2,min_angle:28});
  assert.equal(result.error.input.traces[0].width,.0002);
  assert.equal(result.error.material_evaluation,null);assert.match(result.error.message,/300000 points/);
  for(const width of [1400,390]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
    const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-results").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()');
    await writeFile(join(output,'mesh-failure-view-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));
  }
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:1400,height:900,deviceScaleFactor:1,mobile:false});
  assert.ok((await status()).startsWith('Target not met:'));
  await rm(join(downloads,'sipi-result.json'),{force:true});
  await cdp.evaluate('document.querySelector("#save-result").click()');
  const failedExport=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-result.json'),'utf8'));}catch{}},'mesh failure result export');
  assert.deepEqual(failedExport.execution,result);
  await writeFile(join(output,'mesh-failure.json'),JSON.stringify(failedExport,null,2));
  await input(cases.line);
  await cdp.evaluate(`document.querySelector('#modes').checked=true;document.querySelector('#modes').dispatchEvent(new Event('change'));`);
  result=await calculate();assert.equal(result.status,'complete');assert.equal(result.result.diagnostics.modes.status,'failed');
  assert.equal(await cdp.evaluate('document.querySelector("#diagnostic-status").hidden'),false);
  await cdp.evaluate('document.querySelector("#example-choice").value="rlc";document.querySelector("#example-choice").dispatchEvent(new Event("change"));document.querySelector("#example").click();document.querySelector("#run").click();document.querySelector("#cancel").click()');
  await until(async()=>(await status()).startsWith('Calculation cancelled'),'cancel pending start');
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#material-results").hidden'),true);
  result=await calculate();assert.equal(result.status,'complete');
  // A late successful result must not replace edited input or become exportable.
  await cdp.evaluate(`document.querySelector('#run').click();document.querySelector('#input-text').value+=' ';document.querySelector('#input-text').dispatchEvent(new Event('input'));`);
  await until(()=>cdp.evaluate('!document.querySelector("#run").disabled'),'stale completion');
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#material-results").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await writeFile(join(output,'saved-mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(async()=>/closed|stopped/.test(await status()),'shutdown');
  assert.equal(await cdp.evaluate('document.querySelector("#example-choice").disabled && document.querySelector("#example").disabled'),true);
  if(!webRoot) await until(()=>server.exitCode===0,'server exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'local-native',
    externalRequests:remoteRequests,errors,workerTargets,capacitance3d,materialGoals,materialBatch,checks:['material result cells match exact execution with display rounding','malformed display fallback and inert hostile labels','summary clears on edits, cancellation and stale completion','six canonical examples, explicit load and keyboard selection','busy/closed example controls','raw duplicate rejection','canonical input download','RLC native S within 1e-12',
      'result download','constant/Debye material goals, selected models, refinement and exports','pair material goal and complete/incomplete material studies with exports','fixed-mesh 3D C/energy/charge and export','Unicode file input','incomplete study','refined target failure history','optional diagnostic failure',
      'pending-start cancellation and restart','stale completion rejection','mobile width','shutdown']},null,2));
  console.log('Saved analysis browser acceptance passed.');
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
