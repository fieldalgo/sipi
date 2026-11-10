// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-project-history-browser');
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
    return new Promise((resolve,reject) => {const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('CDP timeout '+method));},method==='Runtime.evaluate'?310000:30000);this.pending.set(id,{resolve,reject,timer});this.ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));});
  }
  async evaluate(expression) {
    const r=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
    if(r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  }
}
let cdp, serverLog = '';
try {
  const serverArgs = webRoot ? ['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot] : ['-m','sipi','gui','--no-browser'];
  const server = spawn(process.env.SIPI_PYTHON || 'python', serverArgs, {cwd:profile,env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});
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
  const target=new URL(url);target.pathname='/saved.html';
  await cdp.call('Page.navigate',{url:target.href});
  await until(()=>cdp.evaluate('document.readyState==="complete" && !!document.querySelector("#project-start")'),'project page');

  const fixture=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/failed_pair_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const cases=JSON.parse(fixture.stdout),checks=[],records=[];
  const text=()=>cdp.evaluate('document.querySelector("#input-text").value');
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async value=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(value)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const click=async id=>cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'failure view operation',180000);
  async function download(id,name){await rm(join(downloads,name),{force:true});await click(id);return until(async()=>{try{return await readFile(join(downloads,name),'utf8');}catch{}},name);}
  function compare(a,b,path='execution'){
    assert.deepEqual(a.input,b.input);assert.equal(a.status,'failed');assert.equal(a.result,null);
    assert.equal(a.error.type,'PairImpedanceGoalError');assert.equal(a.error.stage,b.error.stage);assert.equal(a.error.message,b.error.message);
    assert.equal(a.error.attempts,a.error.history.length);assert.ok(a.error.history.length<=a.input.max_evaluations);
    a.error.failed_parameters.forEach((value,i)=>assert.ok(Math.abs(value-b.error.failed_parameters[i])/Math.abs(b.error.failed_parameters[i])<=1e-4));
    for(const row of a.error.history){assert.equal(row.parameters.length,2);assert.equal(row.impedances_ohm.length,2);assert.ok(row.parameters.every(Number.isFinite)&&row.impedances_ohm.every(value=>Number.isFinite(value)&&value>0));}
    const reference=b.error.stage==='budget'?b.error.history[0]:b.error.history.findLast(row=>row.parameters.every((value,i)=>value===b.error.failed_parameters[i]));
    const observed=a.error.stage==='budget'?a.error.history[0]:a.error.history.findLast(row=>row.parameters.every((value,i)=>value===a.error.failed_parameters[i]));
    assert.ok(reference&&observed);observed.impedances_ohm.forEach((value,i)=>assert.ok(Math.abs(value-reference.impedances_ohm[i])/Math.abs(reference.impedances_ohm[i])<=(a.error.stage==='budget'?1e-10:1e-5)));
    if(a.error.stage==='budget'){assert.equal(a.error.history.length,1);assert.deepEqual(a.error.history[0].parameters,[3.2,3.5]);}
    if(a.error.stage==='refinement/target'){
      const refined=a.error.history.at(-1);assert.equal(refined.stage,'refinement');
      const chosen=a.error.history.find(row=>row.stage==='search'&&row.parameters.every((value,i)=>value===refined.parameters[i]));assert.ok(chosen);
      assert.ok(chosen.impedances_ohm.every((value,i)=>Math.abs(value-[101,34][i])<=.01));
      assert.ok(refined.impedances_ohm.some((value,i)=>Math.abs(value-[101,34][i])>.01));
    }
  }
  async function checkView(execution){
    const got=await cdp.evaluate('(()=>{const c=document.querySelector("#material-results");return {hidden:c.hidden,title:c.querySelector("h3")?.textContent,text:c.textContent,tables:Array.from(c.querySelectorAll("table"),t=>Array.from(t.querySelectorAll("tbody tr"),r=>Array.from(r.cells,c=>({text:c.textContent,value:c.dataset.value??null}))))}})()');
    assert.equal(got.hidden,false);assert.match(got.title,/targets not accepted/);assert.ok(got.text.includes(execution.error.message));
    const expected=[
      [['Differential',execution.input.targets_ohm.z_diff,execution.input.tolerances_ohm.z_diff],['Common',execution.input.targets_ohm.z_common,execution.input.tolerances_ohm.z_common]],
      execution.input.variables.map(v=>[v.name,...v.bounds]),
      execution.error.history.map((r,i)=>[i,r.stage,...r.parameters,...r.impedances_ohm]),
      [[execution.error.stage,...execution.error.failed_parameters]]];
    assert.deepEqual(got.tables,expected.map(rows=>rows.map(row=>row.map(value=>({text:typeof value==='number'?String(Number(value.toPrecision(7))):value,value:typeof value==='number'?String(value):null})))));
    assert.match(got.text,/does not select a solution/);
  }
  for(const [index,item] of cases.entries()){
    await input(JSON.stringify(item.input));
    if(index===0){await click('project-start');await idle();}
    await click('record');await idle();
    const execution=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
    assert.equal(execution.status,'failed');assert.equal(execution.result,null);compare(execution,item.execution);await checkView(execution);
    const raw=await download('save-record','sipi-execution-record.json');records.push({raw,value:JSON.parse(raw)});
    await writeFile(join(output,item.name+'-execution.json'),JSON.stringify(execution,null,2));await writeFile(join(output,item.name+'-record.json'),raw);
    for(const width of (index===0?[1400,390,320]:[1400,390])){
      await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
      assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
      const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-results").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()');
      await writeFile(join(output,item.name+'-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));
    }
    const project=JSON.parse(await download('project-save','sipi-analysis-project.json'));assert.equal(project.designs[0].records.length,index+1);
    for(let j=0;j<=index;j++)assert.deepEqual(project.designs[0].records[j],records[j].value);
    checks.push(item.name+': every completed history row and phase match failed execution; record/export preserved');
  }
  const current=await text();
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[0].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');
  await click('project-view');await idle();assert.equal(await text(),current);await checkView(records[0].value.receipt.execution);
  assert.match(await cdp.evaluate('document.querySelector("#material-results h3").textContent'),/^Saved run/);
  assert.equal(await download('save-record','sipi-execution-record.json'),records[0].raw);
  const before=await cdp.evaluate('document.querySelector("#output").textContent');
  const inert=await cdp.evaluate(`(async()=>{const {renderMaterialResults}=await import('./material-results.js');const c=document.querySelector('#material-results');const original=${JSON.stringify(records[0].value.receipt.execution)},hostile=structuredClone(original);hostile.error.message='<img src=x onerror="window.failureInjected=true">';renderMaterialResults(c,hostile);const safe=c.textContent.includes(hostile.error.message)&&!c.querySelector('img')&&window.failureInjected===undefined;hostile.error.history[0].impedances_ohm[0]=NaN;renderMaterialResults(c,hostile);const hidden=c.hidden&&c.children.length===0;renderMaterialResults(c,original,{historical:true});return safe&&hidden;})()`);
  assert.equal(inert,true);assert.equal(await cdp.evaluate('document.querySelector("#output").textContent'),before);
  checks.push('historical failure retains current input/raw bytes; hostile errors inert and malformed history falls back');
  await cdp.evaluate('document.querySelector("#example-choice").value="pair-target";document.querySelector("#example").click()');
  assert.equal(await cdp.evaluate('document.querySelector("#material-results").hidden'),true);
  await click('record');await idle();
  const success=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');assert.equal(success.status,'complete');
  assert.ok(success.result.residuals_ohm.every((v,i)=>Math.abs(v)<=[1,.5][i])&&success.result.refined_residuals_ohm.every((v,i)=>Math.abs(v)<=[1,.5][i]));
  assert.equal(await cdp.evaluate('document.querySelector("#material-results h3").classList.contains("error")'),false);
  const finalProject=JSON.parse(await download('project-save','sipi-analysis-project.json'));assert.equal(finalProject.designs[0].records.length,4);
  for(let i=0;i<3;i++)assert.deepEqual(finalProject.designs[0].records[i],records[i].value);
  checks.push('editing clears failed view; successful recovery keeps failed records and removes failure presentation');
  await click('exit');await until(async()=>/closed|stopped/.test(await status()),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',checks,errors,externalRequests:remoteRequests,workerTargets},null,2));
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
