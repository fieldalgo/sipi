// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-record-browser');
const webRoot = process.argv[3] ? resolve(process.argv[3]) : null;
const integrityOnly = process.argv[4] === '--expect-integrity-error';
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
  await cdp.call('Page.navigate',{url});
  await until(()=>cdp.evaluate('document.readyState==="complete"'),'page');
  await cdp.evaluate(`(async()=>{window.recordTransport = new (await import(${JSON.stringify(webRoot?'./browser-transport.js':'./transport.js')})).${webRoot?'BrowserTransport':'LocalTransport'}();})()`);
  const fixture=spawnSync(process.env.SIPI_PYTHON || 'python',['-c',
    'import json;from sipi import LumpedNetworkDocument;print(json.dumps({str(r):LumpedNetworkDocument([0,1e9],resistance=r).dumps() for r in (10,20)}))'],
    {encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const texts=JSON.parse(fixture.stdout);
  const run=input=>cdp.evaluate('window.recordTransport.run('+JSON.stringify(input)+')');
  const rejected=input=>cdp.evaluate('window.recordTransport.run('+JSON.stringify(input)+').then(()=>({accepted:true}),e=>({accepted:false,message:e.message}))');
  const input={action:'saved-record',text:texts['10']};
  let checks=[];
  if(integrityOnly) {
    assert.ok(webRoot,'Integrity cases require a staged browser runtime.');
    const failure=await rejected(input);assert.equal(failure.accepted,false);
    assert.match(failure.message,/mismatch|Invalid browser source-file descriptor/);
    checks.push('corrupt source rejected before calculation without server fallback');
  } else {
    const first=await run(input),record=JSON.parse(first.record_text);
    assert.equal(record.schema,'sipi.execution-record/1');assert.equal(record.receipt.execution.status,'complete');
    assert.equal(record.artifacts.verification,'host-declared');
    assert.equal(record.artifacts.items.length,webRoot?8:7);
    assert.match(record.run_id,/^run:[0-9a-f]{32}$/);
    const second=await run(input),other=JSON.parse(second.record_text);
    assert.notEqual(record.run_id,other.run_id);assert.deepEqual(record.receipt,other.receipt);
    assert.equal(first.runtime_manifest_text,second.runtime_manifest_text);
    const old=await run({action:'saved-analyze',text:texts['10']});
    assert.deepEqual(record.receipt.execution,old.execution);
    let created=await run({action:'project-create',text:texts['10'],project_id:'p',design_id:'a',title:'Recorded',label:'A'});
    let attached=await run({action:'project-attach',project_text:created.project_text,design_id:'a',record_text:first.record_text,select:true});
    assert.equal(JSON.parse(attached.project_text).designs[0].selected_run_id,record.run_id);
    const lookup=await run({action:'project-record',project_text:attached.project_text,design_id:'a',run_id:record.run_id});
    assert.equal(lookup.record_text,first.record_text);assert.equal(lookup.selected,true);assert.equal(lookup.matches_current,true);
    const damaged=await rejected({action:'project-attach',project_text:created.project_text,design_id:'a',record_text:JSON.stringify(record),select:true});
    assert.equal(damaged.accepted,false);assert.match(damaged.message,/digest/);
    const both=await run({action:'project-attach',project_text:attached.project_text,design_id:'a',record_text:second.record_text,select:false});
    assert.equal(JSON.parse(both.project_text).designs[0].selected_run_id,record.run_id);
    const edited=await run({action:'project-update',project_text:both.project_text,design_id:'a',text:texts['20']});
    assert.equal(JSON.parse(edited.project_text).designs[0].selected_run_id,null);
    const past=await run({action:'project-record',project_text:edited.project_text,design_id:'a',run_id:record.run_id});
    assert.equal(past.record_text,first.record_text);assert.equal(past.selected,false);assert.equal(past.matches_current,false);
    const missing=await rejected({action:'project-record',project_text:edited.project_text,design_id:'a',run_id:'absent'});
    assert.equal(missing.accepted,false);assert.match(missing.message,/not in this design/);
    const stale=await rejected({action:'project-select',project_text:edited.project_text,design_id:'a',run_id:record.run_id});
    assert.equal(stale.accepted,false);assert.match(stale.message,/current design request/);
    const forged=await rejected({...input,artifacts:[]});assert.equal(forged.accepted,false);
    const casesResult=spawnSync(process.env.SIPI_PYTHON || 'python',['workbench/tests/saved_cases.py'],
      {encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
    assert.equal(casesResult.status,0,casesResult.stderr);const cases=JSON.parse(casesResult.stdout);

    for(const [name,status] of [['study','incomplete'],['goal','failed'],['mesh_goal','failed']]) {
      const recordedOutput=await run({action:'saved-record',text:cases[name]});
      const saved=JSON.parse(recordedOutput.record_text);assert.equal(saved.receipt.execution.status,status);
      const checked=await run({action:'project-create',text:cases[name],project_id:'p:'+name,design_id:'a',title:name,label:'A'});
      const restored=await run({action:'project-attach',project_text:checked.project_text,design_id:'a',record_text:recordedOutput.record_text,select:true});
      const stored=JSON.parse(restored.project_text).designs[0].records[0];
      const lookup=await run({action:'project-record',project_text:restored.project_text,design_id:'a',run_id:saved.run_id});
      assert.equal(lookup.record_text,recordedOutput.record_text);assert.equal(lookup.selected,true);assert.equal(lookup.matches_current,true);
      assert.deepEqual(stored,saved);
      if(name==='study') assert.ok(saved.receipt.execution.result.failed>0);
      else if(name==='goal') assert.equal(saved.receipt.execution.error.history.at(-1).stage,'refinement');
      else {
        const failure=saved.receipt.execution.error;
        assert.equal(saved.receipt.execution.result,null);
        assert.equal(failure.type,'GoalMeshSizeLimitError');
        assert.equal(failure.cause_type,'MeshSizeLimitError');
        assert.equal(failure.stage,'search');assert.equal(failure.attempts,1);
        assert.deepEqual(failure.history,[]);assert.equal(failure.parameter,.0002);
        assert.deepEqual(failure.input.mesh,{edge_size:1e-12,far_size:.0002,grade:.2,min_angle:28});
        assert.equal(failure.input.traces[0].width,.0002);
        assert.equal(failure.material_evaluation,null);
        assert.match(failure.message,/300000 points/);
      }
      await writeFile(join(output,'record-'+name+'.json'),recordedOutput.record_text);
    }
    const cancelled=await cdp.evaluate(`(async()=>{const pending=window.recordTransport.run(${JSON.stringify(input)}).then(()=>({accepted:true}),e=>({accepted:false,name:e.name}));await window.recordTransport.cancel();return pending;})()`);
    assert.equal(cancelled.accepted,false);assert.equal(cancelled.name,'AbortError');
    const restarted=await run(input);assert.equal(JSON.parse(restarted.record_text).receipt.execution.status,'complete');
    await writeFile(join(output,'record.json'),first.record_text);
    await writeFile(join(output,'runtime-manifest.json'),first.runtime_manifest_text);
    await writeFile(join(output,'project.json'),both.project_text);
    checks=['real recorded calculation','same semantic receipt with unique run IDs','exact old saved execution',
      'raw project attachment','numeric reserialization rejected','history retained on edit','stale selection rejected',
      'caller provenance rejected','incomplete-study record/project history','failed refined-goal record/project history',
      'actual mesh-budget failure retained with exact failed input in record and project',
      'raw current and historical project lookup','missing record rejected','pending cancellation and restart'];
  }
  await cdp.evaluate('window.recordTransport.close()');
  if(!webRoot) await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot) assert.deepEqual(apiRequests,[],'Worker must not fall back to server calculation.');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',
    scope:'Actual browser transport contracts; automatic result-history UI is separate',integrityOnly,
    externalRequests:remoteRequests,errors,workerTargets,checks},null,2));
  console.log('Recorded execution browser transport acceptance passed.');
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
