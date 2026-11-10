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
  const fixture=name=>{
    const p=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/'+name],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
    assert.equal(p.status,0,p.stderr);return JSON.parse(p.stdout);
  };
  const cases=fixture('project_cases.py'),physical=fixture('saved_cases.py'),checks=[];
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async text=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(text)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'project operation',300000);
  async function click(id){await cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');await idle();}
  async function choose(id,value){await cdp.evaluate('document.getElementById('+JSON.stringify(id)+').value='+JSON.stringify(value)+';document.getElementById('+JSON.stringify(id)+').dispatchEvent(new Event("change"))');await idle();}
  async function textDownload(button,filename){
    await rm(join(downloads,filename),{force:true});await click(button);
    return until(async()=>{try{return await readFile(join(downloads,filename),'utf8');}catch{}},filename+' download');
  }
  let savedNumber=0;
  function verifyRaw(text,kind,name){
    const path=join(output,name+'.json');
    return writeFile(path,text).then(()=>{
      const p=spawnSync(process.env.SIPI_PYTHON||'python',['-c',
        'from pathlib import Path;import sys;from sipi.project import SavedProject;from sipi.execution_record import SavedExecutionRecord;text=Path(sys.argv[1]).read_text();value=SavedProject.loads(text,max_project_bytes=200*1024) if sys.argv[2]=="project" else SavedExecutionRecord.loads(text,max_record_bytes=200*1024);assert value.dumps()==text',
        path,kind],{cwd:profile,encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
      assert.equal(p.status,0,p.stderr);return text;
    });
  }
  const saveProject=async name=>verifyRaw(await textDownload('project-save','sipi-analysis-project.json'),'project',name||'project-'+(++savedNumber));
  const saveRecord=async name=>verifyRaw(await textDownload('save-record','sipi-execution-record.json'),'record',name);
  let openedNumber=0;
  async function openProject(text){
    const path=join(profile,'프로젝트-'+(++openedNumber)+'.json');await writeFile(path,text);
    const dom=await cdp.call('DOM.getDocument');
    const field=await cdp.call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#project-file'});
    await cdp.call('DOM.setFileInputFiles',{nodeId:field.nodeId,files:[path]});await idle();
  }
  async function recorded(){
    await click('record');assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),false,await status());
    return cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
  }
  const currentID=()=>cdp.evaluate('document.querySelector("#project-design").value');
  await input(cases.input);await click('project-start');assert.match(await status(),/Project ready/);
  const a=await currentID();
  await cdp.evaluate('document.querySelector("#project-label").value="RLC A";document.querySelector("#project-label").dispatchEvent(new Event("input"))');
  await recorded();const firstRaw=await saveRecord('first-record'),first=JSON.parse(firstRaw);
  assert.equal(await cdp.evaluate('document.querySelector("#save-environment").disabled'),false);
  let p=JSON.parse(await saveProject('first-project'));
  assert.equal(p.designs[0].selected_run_id,first.run_id);assert.equal(p.designs[0].label,'RLC A');
  await recorded();const secondRaw=await saveRecord('second-record'),second=JSON.parse(secondRaw);
  assert.notEqual(first.run_id,second.run_id);assert.deepEqual(first.receipt,second.receipt);
  p=JSON.parse(await saveProject());assert.equal(p.designs[0].records.length,2);
  assert.equal(p.designs[0].selected_run_id,second.run_id);
  await choose('project-record',first.run_id);await click('project-view');
  assert.match(await status(),/not selected/);assert.equal(await cdp.evaluate('document.querySelector("#save-environment").disabled'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  assert.equal(await saveRecord('viewed-first'),firstRaw);
  await click('project-select');assert.match(await status(),/Selected in the saved project/);
  p=JSON.parse(await saveProject());assert.equal(p.designs[0].selected_run_id,first.run_id);
  const retained=p.designs[0].records;
  await choose('example-choice','pair-target');
  assert.equal(await cdp.evaluate('document.querySelector("#input-text").value'),cases.input);
  await click('example');
  assert.match(await cdp.evaluate('document.querySelector("#project-note").textContent'),/Unsaved input changes/);
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  p=JSON.parse(await saveProject('example-loaded-project'));
  assert.deepEqual(p.designs[0].records,retained);
  assert.equal(p.designs[0].selected_run_id,null);
  assert.equal(JSON.parse(p.designs[0].source_text).schema,'sipi.pair-impedance-design/2');
  await input(cases.input);await saveProject();
  await choose('project-record',first.run_id);await click('project-select');
  assert.equal(await saveRecord('example-retained-first'),firstRaw);
  checks.push('example selection preserves edits; explicit load retains project history and clears current selection');
  await click('project-clear');p=JSON.parse(await saveProject());assert.equal(p.designs[0].selected_run_id,null);
  checks.push('raw project/record downloads validate in Python','unique repeated runs and explicit selection','viewing does not select or invent environment evidence');
  await click('project-duplicate');const b=await currentID();assert.notEqual(a,b);
  assert.equal(await cdp.evaluate('document.querySelector("#project-record").options.length'),1);
  await input(cases.changed);await recorded();
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:1400,height:1100,deviceScaleFactor:1,mobile:false});
  await writeFile(join(output,'project-history-ab.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  p=JSON.parse(await saveProject('ab-project'));
  assert.equal(p.designs.length,2);assert.equal(p.designs.find(d=>d.design_id===a).records.length,2);
  assert.equal(p.designs.find(d=>d.design_id===b).records.length,1);
  await choose('project-design',a);
  assert.equal(await cdp.evaluate('document.querySelector("#input-text").value'),cases.input);
  await input(cases.changed_again);
  await choose('project-record',first.run_id);await click('project-view');
  assert.match(await status(),/unsaved changes/);
  assert.equal(await cdp.evaluate('document.querySelector("#input-text").value'),cases.changed_again);
  await click('project-select');assert.match(await status(),/current design request/);
  p=JSON.parse(await saveProject('historical-project'));assert.equal(p.designs.find(d=>d.design_id===a).selected_run_id,null);
  await choose('project-record',first.run_id);await click('project-view');assert.match(await status(),/Historical input/);
  assert.equal(await saveRecord('historical-first'),firstRaw);
  await input(cases.input+'\n ');await saveProject();
  await choose('project-record',first.run_id);await click('project-select');
  assert.match(await status(),/Selected in the saved project/);
  checks.push('A/B input switch and duplicate empty history','semantic edits retain old history but reject current selection','format-only matching preserves raw old record');
  await openProject(cases.limit129);assert.match(await status(),/Project opened/);
  await click('run');assert.match(await status(),/at most 128/);assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  await openProject(cases.limit17);await recorded();
  const limited=JSON.parse(await saveRecord('limited-record'));
  assert.deepEqual(limited.receipt.request.controls,{max_input_bytes:100000,max_evaluations:17,diagnostics:[]});
  const normal=await click('run');assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),false);
  checks.push('imported byte/evaluation controls preserved','ordinary project run refuses unsupported stored budget without clamping');
  // Use default controls for physical fixtures; retain the actual failure records.
  const initialProject=await readFile(join(output,'first-project.json'),'utf8');
  await openProject(initialProject);
  for(const [name,expected] of [['study','incomplete'],['goal','failed']]){
    await input(physical[name]);const out=await recorded();assert.equal(out.status,expected);
    const raw=await saveRecord(name+'-record');
    p=JSON.parse(await saveProject(name+'-project'));const d=p.designs[0];
    assert.equal(d.selected_run_id,JSON.parse(raw).run_id);
    assert.equal(d.records.at(-1).receipt.execution.status,expected);
    if(name==='study')assert.equal(d.records.at(-1).receipt.execution.result.summary,null);
    else assert.equal(d.records.at(-1).receipt.execution.error.history.at(-1).stage,'refinement');
  }
  const last=p.designs[0].selected_run_id,beforeCount=p.designs[0].records.length;
  await choose('project-record',last);await click('project-remove');
  p=JSON.parse(await saveProject());assert.equal(p.designs[0].records.length,beforeCount-1);assert.equal(p.designs[0].selected_run_id,null);
  checks.push('incomplete study and failed refined goal remain selected saved runs','remove selected record clears selection');
  const preserved=await saveProject('preserved-project');
  await openProject(preserved.replace(/"content_sha256":\s*"([0-9a-f])/,(_,hex)=>'"content_sha256":"'+(hex==='0'?'1':'0')));
  assert.match(await status(),/digest/i);assert.equal(await saveProject(),preserved);
  await openProject(' '.repeat(200*1024+1));assert.match(await status(),/exceeds 200 KiB/);assert.equal(await saveProject(),preserved);
  await cdp.evaluate('(()=>{const f=new File(["{}"],"late-project.json",{type:"application/json"});f.text=()=>new Promise(resolve=>window.releaseProjectRead=resolve);const dt=new DataTransfer();dt.items.add(f);const e=document.querySelector("#project-file");e.files=dt.files;e.dispatchEvent(new Event("change"));})()');
  await cdp.evaluate('document.querySelector("#cancel").click()');
  await until(async()=>(await status()).startsWith('Calculation cancelled'),'late-open cancellation');
  await cdp.evaluate('window.releaseProjectRead('+JSON.stringify(cases.limit17)+')');await pause(100);
  assert.equal(await saveProject(),preserved);
  checks.push('tamper and oversize import preserve original project','late project file read cannot replace cancelled state');
  // Hold an actual successful attachment response until after an edit.
  await input(cases.input);const beforeLate=JSON.parse(await saveProject());
  const module=webRoot?'./browser-transport.js':'./transport.js',className=webRoot?'BrowserTransport':'LocalTransport';
  await cdp.evaluate('(async()=>{const C=(await import('+JSON.stringify(module)+')).'+className+';const original=C.prototype.run;window.restoreProjectTransport=()=>C.prototype.run=original;C.prototype.run=async function(input){const result=await original.call(this,input);if(input.action==="project-attach")await new Promise(resolve=>window.releaseAttachment=resolve);return result;};})()');
  await cdp.evaluate('document.querySelector("#record").click()');
  await until(()=>cdp.evaluate('typeof window.releaseAttachment==="function"'),'real attachment held',300000);
  await input(cases.changed);await cdp.evaluate('window.releaseAttachment();window.restoreProjectTransport()');await idle();
  assert.equal(await cdp.evaluate('document.querySelector("#save-record").disabled'),true);
  p=JSON.parse(await saveProject());assert.equal(p.designs[0].records.length,beforeLate.designs[0].records.length);
  assert.equal(p.designs[0].source_text,cases.changed);
  checks.push('late real attachment cannot replace edited input or append a stale run');
  await openProject(cases.large);assert.match(await status(),/Project opened/);
  await recorded();assert.match(await status(),/Record was not added to the project/);
  assert.equal(await cdp.evaluate('document.querySelector("#save-record").disabled'),false);
  await saveRecord('unattached-record');
  assert.equal(await saveProject('unchanged-large-project'),cases.large);
  checks.push('combined project growth refuses attachment but preserves standalone record and original project');
  await openProject(cases.long);
  for(const width of [1400,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
    await writeFile(join(output,'project-history-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  }
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(async()=>/closed|stopped/.test(await status()),'shutdown');
  if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot)assert.deepEqual(apiRequests,[],'Worker must not fall back to server calculation.');
  checks.push('long labels mobile width','normal close');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',externalRequests:remoteRequests,errors,workerTargets,checks},null,2));
  console.log('Saved-analysis project history acceptance passed.');
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
