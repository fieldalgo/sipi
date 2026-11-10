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

  const fixture=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/material_normal_form_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const cases=JSON.parse(fixture.stdout),checks=[],records=[];
  const text=()=>cdp.evaluate('document.querySelector("#input-text").value');
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async value=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(value)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const field=async(name,value)=>cdp.evaluate('document.querySelector("#material-goal-'+name+'").value='+JSON.stringify(value)+';document.querySelector("#material-goal-'+name+'").dispatchEvent(new Event("input"))');
  const click=async id=>cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#material-goal-mean").disabled'),'normal operation',180000);
  const visible=()=>cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor label")).filter(l=>!l.hidden).map(l=>l.querySelector("input").id)');
  async function example(id){await cdp.evaluate('document.querySelector("#example-choice").value='+JSON.stringify(id));await click('example');}
  async function download(id,name){await rm(join(downloads,name),{force:true});await click(id);return until(async()=>{try{return await readFile(join(downloads,name),'utf8');}catch{}},name);}
  let files=0;
  async function openFile(value,project=false){const path=join(profile,'normal-'+(++files)+'.json');await writeFile(path,value);const doc=await cdp.call('DOM.getDocument'),node=await cdp.call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:project?'#project-file':'#file'});await cdp.call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[path]});if(project)await idle();else await until(async()=>(await status()).startsWith('File opened'),'open input');}
  function compare(a,b,path='execution'){
    if(typeof b==='number'){assert.equal(typeof a,'number',path);assert.ok(Number.isFinite(a)&&Math.abs(a-b)<=Math.max(1e-10*Math.abs(b),1e-14),path);}
    else if(b!==null&&typeof b==='object'){assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),path);for(const key of Object.keys(b))compare(a[key],b[key],path+'.'+key);}
    else assert.equal(a,b,path);
  }
  await example('rlc');const rlc=await text();await example('normal-study');assert.deepEqual(JSON.parse(await text()),cases[0].input);
  assert.deepEqual(await visible(),['mean','std','count','seed','frequency'].map(k=>'material-goal-'+k));
  await field('seed','10');await example('normal-study');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").value'),'9');assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  await click('project-start');await idle();
  for(const [index,item] of [cases[1],cases[0],cases[3],cases[2],cases[4]].entries()){
    if(index===2)await openFile(JSON.stringify(cases[2].input));
    if(index===4)await openFile(JSON.stringify(cases[1].input));
    const before=await text(),variable=item.input.sampling.variables[0];
    for(const [key,value] of Object.entries({mean:String(variable.mean),std:String(variable.std),count:String(item.input.sampling.count),seed:String(item.input.sampling.seed),frequency:String(item.input.material_evaluation.frequency_hz)}))await field(key,value);
    assert.equal(await text(),before);assert.equal(await cdp.evaluate('["run","record","check","save-input","project-save"].every(id=>document.getElementById(id).disabled)'),true);
    await click('material-goal-apply');await idle();assert.match(await status(),/applied and checked/);assert.deepEqual(JSON.parse(await text()),item.input);
    assert.deepEqual(JSON.parse(await download('save-input','sipi-input.json')),item.input);
    await click('record');await idle();const execution=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');compare(execution,item.execution);
    assert.equal(execution.result.rows.length,item.input.sampling.count);
    if(execution.result.failed){assert.equal(execution.status,'incomplete');assert.equal(execution.result.summary,null);assert.equal(await cdp.evaluate('document.querySelectorAll("#material-results table").length'),1);}
    else {assert.equal(execution.status,'complete');assert.equal(await cdp.evaluate('document.querySelectorAll("#material-results table").length'),2);}
    const raw=await download('save-record','sipi-execution-record.json');records.push({raw,value:JSON.parse(raw)});
    await writeFile(join(output,item.name+'-execution.json'),JSON.stringify(execution,null,2));await writeFile(join(output,item.name+'-record.json'),raw);
    const project=JSON.parse(await download('project-save','sipi-analysis-project.json'));assert.equal(project.designs[0].records.length,index+1);project.designs[0].records.forEach((record,i)=>assert.deepEqual(record,records[i].value));
    checks.push(item.name+': five explicit settings, exact input and ordered sampled rows, correct complete/incomplete summary and retained project record');
  }
  await click('record');await idle();const repeated=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');assert.deepEqual(repeated,records.at(-1).value.receipt.execution);
  const repeatedRaw=await download('save-record','sipi-execution-record.json');records.push({raw:repeatedRaw,value:JSON.parse(repeatedRaw)});await writeFile(join(output,'repeated-seed-execution.json'),JSON.stringify(repeated,null,2));
  checks.push('same explicit seed/input re-executes identical rows and full result; changed seed remains its own input/record');
  const before=await text();
  for(const [key,value] of [['std','0'],['std','-1'],['count','1'],['count','129'],['seed','-1'],['seed','4294967296'],['seed','2.5'],['frequency','-1']]){
    await field(key,value);await click('material-goal-apply');await idle();assert.equal(await text(),before);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);await click('material-goal-reset');
  }
  const duplicate=before.replace('{','{"sampling":{},');await input(duplicate);await field('seed','11');await click('material-goal-apply');await idle();assert.equal(await text(),duplicate);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
  await openFile(before);await field('seed','11');await openFile(before);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").value'),'10');
  await field('seed','11');await input(before);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").value'),'10');
  checks.push('invalid std/count/seed/frequency and duplicate source reject atomically; identical file/raw restore clears drafts');
  await field('seed','11');await example('material-sweep');assert.equal((await visible()).length,4);await field('seed','12');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-apply").disabled'),true);
  await example('constant-target');assert.equal((await visible()).length,6);await field('mean','3');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-apply").disabled'),true);
  await example('pair-target');assert.equal((await visible()).length,12);await field('std','1');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-apply").disabled'),true);
  await example('correlated-study');assert.equal((await visible()).length,8);
  await example('normal-study');assert.equal((await visible()).length,5);await field('lower','1');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-apply").disabled'),true);
  checks.push('normal/sweep/scalar/pair/unsupported transitions clear drafts; hidden fields do not affect active settings');
  await openFile(before);const saved=await download('project-save','sipi-analysis-project.json');assert.equal(JSON.parse(saved).designs[0].records.length,6);JSON.parse(saved).designs[0].records.forEach((record,i)=>assert.deepEqual(record,records[i].value));await example('rlc');await openFile(saved,true);assert.equal(await text(),before);
  await field('seed','11');await openFile(saved,true);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").value'),'10');
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[0].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');await click('project-view');await idle();assert.equal(await text(),before);assert.equal(await download('save-record','sipi-execution-record.json'),records[0].raw);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").value'),'10');
  for(const width of [1400,390,320]){await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-goal-editor").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()');await writeFile(join(output,'material-normal-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));}
  checks.push('project restore and historical incomplete run retain current seed and exact raw record; responsive form');
  await field('seed','11');await cdp.evaluate(`(async()=>{const browser=document.documentElement.dataset.runtime==='browser';const m=await import(browser?'./browser-transport.js':'./transport.js');const p=(browser?m.BrowserTransport:m.LocalTransport).prototype;const original=p.run;p.run=async function(input){p.run=original;await new Promise(resolve=>window.releaseNormalApply=resolve);return original.call(this,input);};})()`);
  await click('material-goal-apply');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-seed").disabled'),true);await input(rlc);await cdp.evaluate('window.releaseNormalApply()');await idle();assert.equal(await text(),rlc);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-editor").hidden'),true);
  await example('normal-study');await click('exit');await until(async()=>/closed|stopped/.test(await status()),'shutdown');assert.equal(await cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor input, #material-goal-editor button")).every(e=>e.disabled)'),true);if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  checks.push('stale normal apply cannot replace changed source; busy/closed controls and clean shutdown');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',checks,errors,externalRequests:remoteRequests,workerTargets},null,2));
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
