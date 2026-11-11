// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const paired=process.env.SIPI_LAYERED_PAIR==='1';
const template=paired?'coupled_layered_stripline':'layered_stripline';
const quantity=paired?'z_diff':'z0',extension=paired?'s4p':'s2p';
const output = resolve(process.argv[2] || '.validation/sipi-buried-coplanar-browser');
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
const actions=[];
try {
  const serverArgs = webRoot ? ['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot] : ['gui','--no-browser'];
  const server = spawn(webRoot ? (process.env.SIPI_PYTHON || 'python') : process.env.SIPI_CONSOLE, serverArgs, {env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});
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
  await cdp.call('Page.navigate',{url});
  await until(()=>cdp.evaluate('!!document.querySelector("#cross-section rect")'),'drawing');
  await cdp.evaluate(`document.querySelector('#domain-settings').open=true;
    window.domainRequests=[];window.completedResults=[];
    const observedWorkers=new WeakSet();
    const post=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(message,...rest){if(message.input)window.domainRequests.push(message.input);if(!observedWorkers.has(this)){observedWorkers.add(this);this.addEventListener('message',event=>{if(event.data.status==='complete')window.completedResults.push(event.data.result)})}return post.call(this,message,...rest)};
    const fetchOriginal=window.fetch;
    window.fetch=(url,options)=>{if(url==='/api/job' && options?.method==='POST')window.domainRequests.push(JSON.parse(options.body));return fetchOriginal(url,options).then(async response=>{if(url==='/api/job'&&options?.method==='GET'){const value=await response.clone().json();if(value.status==='complete')window.completedResults.push(value.result)}return response})};`);
  async function ready(timeout=180000) { await until(()=>cdp.evaluate('!document.querySelector("#domain-inspect").disabled'),'domain action complete',timeout); }
  async function click(id, expectError=false) {
    const started=performance.now();
    await cdp.evaluate(`document.getElementById('${id}').click()`);await ready(id==='design'?310000:180000);
    actions.push({id,seconds:(performance.now()-started)/1000});
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),expectError,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function set(id,value) { await cdp.evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input'))})()`); }
  async function save(id='save-editable',name='sipi-editable-design.json') {
    await rm(join(downloads,name),{force:true});await click(id);
    return await until(async()=>{try{return JSON.parse(await readFile(join(downloads,name),'utf8'))}catch{}},name);
  }
  async function open(value,selector='#file') {
    const path=join(profile,'domain input.json');await writeFile(path,typeof value==='string'?value:JSON.stringify(value));
    const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector});
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[path]});await ready();
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function choose(name) { await cdp.evaluate(`document.querySelector('[data-template=${name}]').click()`); }
  async function switchDesign(id) {await cdp.evaluate(`const e=document.querySelector('#project-design');e.value=${JSON.stringify(id)};e.dispatchEvent(new Event('change'))`);await ready();}

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/layered_interface_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const precise=JSON.parse(fixtureRun.stdout)[template];
  assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),28);
  await choose(template);
  for(const id of ['height','eps_r','tan_delta','air_mode','offset'])assert.equal(await cdp.evaluate(`document.getElementById('${id}').disabled`),true);
  for(const id of ['lower_height','upper_height','lower_eps_r','upper_eps_r','lower_tan_delta','upper_tan_delta'])assert.equal(await cdp.evaluate(`document.getElementById('${id}').disabled`),false);
  await click('calculate');const first=await cdp.evaluate('window.completedResults.at(-1)');assert.ok(first.line[quantity]>0);
  assert.equal(Object.hasOwn(await cdp.evaluate('window.domainRequests.at(-1)'),'mesh'),false);
  const firstInput=await save();assert.equal(firstInput.parameters.lower_eps_r,3.8);assert.equal(firstInput.parameters.upper_eps_r,4.5);
  function exactGeometry(d) {
    const p=d.parameters,cs=d.cross_section;
    assert.deepEqual(cs.layers.map(l=>l.thickness),[p.lower_height,p.upper_height]);
    assert.deepEqual(cs.layers.map(l=>l.eps_r),[p.lower_eps_r,p.upper_eps_r]);
    assert.deepEqual(cs.layers.map(l=>l.tan_delta),[p.lower_tan_delta,p.upper_tan_delta]);
    for(const t of cs.traces){assert.equal(t.y,p.lower_height);assert.equal(t.thickness,p.thickness);assert.ok(t.y+t.thickness<p.lower_height+p.upper_height);assert.equal(t.top_width??t.width,p.top_width??p.width);}
    assert.equal(cs.box.top,'ground');assert.equal(cs.box.bottom,'ground');
    if(paired){const x=(p.width+p.gap)/2;assert.deepEqual(cs.traces.map(t=>t.x),[-x,x]);}
  }
  exactGeometry(firstInput);await open(precise);
  for(const unit of ['µm','mil','mm']){
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.deepEqual(await save(),precise);
  }
  for(const [id,value] of [['lower_height','0'],['upper_height','.02'],['lower_eps_r','.5'],['upper_tan_delta','-1']]){await set(id,value);await click('calculate',true);await open(precise);}
  for(const id of ['height','eps_r','tan_delta'])await set(id,'invalid');assert.deepEqual(await save(),precise);
  const layerEdits=[];
  for(const [id,value,scale] of [['lower_height','.45',1e-3],['upper_height','.7',1e-3],['lower_eps_r','3.9',1],['upper_tan_delta','.03',1]]){
    await open(precise);await set(id,value);const d=await save();assert.equal(d.parameters[id],Number(value)*scale);exactGeometry(d);
    for(const key of Object.keys(precise.parameters))if(key!==id)assert.deepEqual(d.parameters[key],precise.parameters[key]);
    assert.deepEqual(d.cross_section.mesh,precise.cross_section.mesh);layerEdits.push(d);
  }
  await open(precise);await set('project-label','Interface A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Interface B');await set('lower_height','.45');await set('upper_eps_r','4.8');const alternative=await save();
  const project=await save('project-save','sipi-project.json');await open(await readFile(join(downloads,'sipi-project.json'),'utf8'),'#project-file');
  assert.deepEqual(await save(),precise);await switchDesign(idB);assert.deepEqual(await save(),alternative);assert.equal(projectA.designs.length,1);assert.equal(project.designs.length,2);
  await open(precise);await click('calculate');const physical=await cdp.evaluate('window.completedResults.at(-1)');assert.deepEqual(physical.document,precise.cross_section);
  await click('comparison-pin');await set('box_width','12');await click('calculate');const outer=await cdp.evaluate('window.completedResults.at(-1)');assert.ok(Math.abs(outer.line[quantity]/physical.line[quantity]-1)<.005);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  await open(precise);await click('mesh-inspect');await click('mesh-refine');await click('calculate');const fine=await cdp.evaluate('window.completedResults.at(-1)');assert.ok(Math.abs(fine.line[quantity]/physical.line[quantity]-1)<.015);
  await open(precise);
  assert.equal(await cdp.evaluate('document.querySelector("#study-variable-2").value'),'lower_eps_r');
  for(const [id,value] of [['study-mode','sweep'],['study-points','2'],['study-variable-1','upper_eps_r']])await set(id,value);
  for(const unit of ['µm','mil','mm']){
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.equal(await cdp.evaluate('Number(document.querySelector("#study-low-1").value)'),4.05);
    assert.equal(await cdp.evaluate('Number(document.querySelector("#study-high-1").value)'),4.95);
  }
  await click('study-calculate');const defaultStudy=await save('study-save','sipi-parameter-study.json');
  assert.deepEqual(defaultStudy.settings.variables,[{parameter:'upper_eps_r',lower:4.5*.9,upper:4.5*1.1}]);assert.equal(defaultStudy.failed,0);
  for(const [id,value] of [['study-mode','corners'],['study-count','2'],['study-variable-1','upper_eps_r'],['study-low-1','4.2'],['study-high-1','4.8'],['study-variable-2','lower_height'],['study-low-2','.38'],['study-high-2','.42']])await set(id,value);
  await click('study-calculate');const study=await save('study-save','sipi-parameter-study.json');assert.equal(study.failed,0);assert.equal(study.quantity,quantity);assert.equal(study.rows.length,4);
  for(const row of study.rows){assert.deepEqual(row.document.mesh,precise.cross_section.mesh);assert.equal(row.impedance,row.line[quantity]);assert.equal(row.document.layers[1].eps_r,row.parameters.upper_eps_r);assert.ok(row.document.traces.every(t=>t.y===row.parameters.lower_height));}
  await click('study-csv');const csv=await until(async()=>{try{return await readFile(join(downloads,'sipi-parameter-study.csv'),'utf8')}catch{}},'study CSV');assert.ok(csv.split('\n')[0].includes('upper_eps_r_1'));assert.ok(csv.split('\n')[0].includes('lower_height_m'));
  for(const [id,value] of [['study-variable-2','upper_height'],['study-low-2','.02'],['study-high-2','.6']])await set(id,value);
  await click('study-calculate',true);await open(precise);
  for(const [id,value] of [['profile','rectangular'],['width','.3'],['lower_height','.4'],['upper_height','.6'],...(paired?[['gap','.2']]:[]),['lower','.05'],['upper','1.5'],['target',paired?'100':'50'],['tolerance','.5']])await set(id,value);
  await click('mesh-auto');const goalInput=await save();await click('design');const goal=await cdp.evaluate('window.completedResults.at(-1)');
  assert.ok(Math.abs(goal.design.residual)<=.5&&Math.abs(goal.design.refined_residual)<=.5);assert.equal(Object.hasOwn(goal.design,'search_tolerance'),false);
  assert.equal(Object.hasOwn(await cdp.evaluate('window.domainRequests.at(-1)'),'mesh'),false);
  assert.equal(goal.line[quantity],goal.design.impedance);const design=await save();assert.equal(design.parameters.width,goal.design.width);assert.deepEqual(design.cross_section.mesh,goal.document.mesh);exactGeometry(design);
  for(const key of ['lower_height','upper_height','lower_eps_r','upper_eps_r','lower_tan_delta','upper_tan_delta','thickness','box_width','top_width',...(paired?['gap']:[])])assert.equal(design.parameters[key],goalInput.parameters[key]);
  await open(precise);for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
  await click('network-calculate');const network=await cdp.evaluate('window.completedResults.at(-1)');assert.equal(network.network.extension,extension);
  await click('touchstone-save');const ts=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.'+extension),'utf8')}catch{}},'port export');assert.ok(ts.includes('# Hz S RI R 50'));
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#layered-dielectric-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['lower_height','upper_height','lower_eps_r','upper_eps_r','lower_tan_delta','upper_tan_delta'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44&&control.left>=0&&control.right<=width,JSON.stringify(control));layouts.push(layout);
    await writeFile(join(output,`layered-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  for(const [name,value] of Object.entries({first,firstInput,layerEdits,project,physical,outer,fine,defaultStudy,study,goal,network,design}))await writeFile(join(output,name+'.json'),JSON.stringify(value,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',actions,editableForms:28,layouts,errors,externalRequests:remoteRequests,checks:['two independent layers first use','inactive uniform fields and valid layer controls','exact three-unit inputs','invalid interface and material refusal','hidden fields ignored','independent layer edits preserve other inputs and mesh','A/B exact project restore','nominal document identity','separate mesh and box checks','dimensionless default material bounds across units','layer height and permittivity corners','CSV dimensionless and length columns','invalid clearance bounds refusal','bounded50/100ohm requested/refined width','exact chosen interface and mesh export','two/four-port export','cancel/restart','four viewport controls','shutdown']},null,2));
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
