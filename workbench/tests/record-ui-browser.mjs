// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-record-ui-browser');
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
  const target = new URL(url);target.pathname='/saved.html';
  await cdp.call('Page.navigate',{url:target.href});
  await until(()=>cdp.evaluate('document.readyState==="complete" && !!document.querySelector("#record")'),'record screen');
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async text=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(text)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const disabled=()=>cdp.evaluate('["save-record","save-environment"].every(id=>document.getElementById(id).disabled)');
  async function calculate(button='record') {
    await cdp.evaluate('document.getElementById('+JSON.stringify(button)+').click()');
    await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'calculation complete',300000);
    assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),false,await status());
    return cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
  }
  const fixture=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/saved_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const cases=JSON.parse(fixture.stdout);
  const checks=[];
  const assertRendered=async record=>assert.equal(await cdp.evaluate('document.querySelector("#output").textContent'),JSON.stringify(record.receipt.execution,null,2));
  async function exported(name) {
    for(const file of ['sipi-execution-record.json','sipi-runtime-manifest.json']) await rm(join(downloads,file),{force:true});
    await cdp.evaluate('document.querySelector("#save-record").click();document.querySelector("#save-environment").click()');
    const text=await until(async()=>{try{return await readFile(join(downloads,'sipi-execution-record.json'),'utf8');}catch{}},'raw record download');
    const manifest=await until(async()=>{try{return await readFile(join(downloads,'sipi-runtime-manifest.json'),'utf8');}catch{}},'raw environment download');
    const recordPath=join(output,name+'-record.json'),manifestPath=join(output,name+'-manifest.json');
    await writeFile(recordPath,text);await writeFile(manifestPath,manifest);
    // Python validates the digest-bearing original download, independently of JS rendering.
    const verify=spawnSync(process.env.SIPI_PYTHON||'python',['-c',[
      'from pathlib import Path',
      'import json,hashlib,sys',
      'from sipi.execution_record import SavedExecutionRecord',
      'raw=Path(sys.argv[1]).read_text(); record=SavedExecutionRecord.loads(raw,max_record_bytes=200*1024)',
      'assert record.dumps()==raw',
      'text=Path(sys.argv[2]).read_text(); manifest=json.loads(text)',
      'items={row["component"]:row for row in record.artifacts["items"]}',
      'if manifest.get("schema")=="sipi.installed-runtime/1":',
      ' for component in manifest["components"]:',
      '  canonical=json.dumps(component,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)',
      '  assert items[component["component"]]["sha256"]==hashlib.sha256(canonical.encode()).hexdigest()',
      'else:',
      ' assert items["sipi-browser-runtime"]["sha256"]==hashlib.sha256(text.encode()).hexdigest()',
      ' assert len(items)==8',
      'print(json.dumps({"status":"passed","run_id":record.run_id}))',
    ].join('\n'),recordPath,manifestPath],{cwd:profile,encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
    assert.equal(verify.status,0,verify.stderr);
    return {record:JSON.parse(text),text,manifest};
  }
  assert.equal(await disabled(),true);
  await cdp.evaluate('document.querySelector("#example").click()');
  const old=await calculate('run');assert.equal(await disabled(),true);
  const firstOutput=await calculate();assert.deepEqual(firstOutput,old);
  const first=await exported('first');await assertRendered(first.record);
  assert.deepEqual(first.record.receipt.request.controls,{max_input_bytes:204800,max_evaluations:128,diagnostics:[]});
  assert.equal(await cdp.evaluate('document.querySelector("#record-status").hidden'),false);
  await calculate();const second=await exported('second');
  assert.notEqual(first.record.run_id,second.record.run_id);
  assert.deepEqual(first.record.receipt,second.record.receipt);assert.equal(first.manifest,second.manifest);
  checks.push('ordinary result unchanged','raw record digest roundtrip','environment linked to record','same input unique run IDs');
  for(const [name,expected] of [['study','incomplete'],['goal','failed']]) {
    await input(cases[name]);assert.equal(await disabled(),true);
    const out=await calculate();assert.equal(out.status,expected);
    const downloaded=await exported(name);assert.equal(downloaded.record.source_text,cases[name]);
    await assertRendered(downloaded.record);
    if(name==='study'){assert.equal(out.result.summary,null);assert.ok(out.result.failed>0);}
    else assert.equal(out.error.history.at(-1).stage,'refinement');
  }
  checks.push('incomplete rows retained in download','failed refinement history retained in download');
  await input(cases.line);
  await cdp.evaluate('document.querySelector("#modes").checked=true;document.querySelector("#modes").dispatchEvent(new Event("change"))');
  const line=await calculate();assert.equal(line.result.diagnostics.modes.status,'failed');
  assert.equal(await cdp.evaluate('document.querySelector("#diagnostic-status").hidden'),false);
  const diagnostic=await exported('diagnostic');
  assert.deepEqual(diagnostic.record.receipt.request.controls.diagnostics,['modes']);
  await assertRendered(diagnostic.record);
  await cdp.evaluate('document.querySelector("#modes").checked=false;document.querySelector("#modes").dispatchEvent(new Event("change"))');
  assert.equal(await disabled(),true);
  checks.push('diagnostic controls and partial failure retained','diagnostic edit invalidates record');
  await cdp.evaluate('document.querySelector("#example").click();document.querySelector("#record").click();document.querySelector("#cancel").click()');
  await until(async()=>(await status()).startsWith('Calculation cancelled'),'cancel record');
  assert.equal(await disabled(),true);
  await calculate();assert.equal(await disabled(),false);
  await cdp.evaluate('document.querySelector("#record").click();document.querySelector("#input-text").value+=" ";document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'stale recorded completion',300000);
  assert.equal(await disabled(),true);assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  await input('{"schema":"sipi.lumped-network/1","schema":"invalid"}');
  await cdp.evaluate('document.querySelector("#record").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'invalid record input');
  assert.match(await status(),/duplicate/i);assert.equal(await disabled(),true);
  await cdp.evaluate('document.querySelector("#example").click()');await calculate();
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
  await writeFile(join(output,'record-ui-mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#check").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'check clears record');
  assert.equal(await disabled(),true);
  await calculate();
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(async()=>/closed|stopped/.test(await status()),'close record screen');
  assert.equal(await disabled(),true);
  if(!webRoot) await until(()=>server.exitCode===0,'installed host exit');
  checks.push('pending cancellation and restart','late completion cannot restore export','invalid input refusal','mobile width','check clears record','close disables export');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot) assert.deepEqual(apiRequests,[],'Worker must not fall back to server calculation.');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',externalRequests:remoteRequests,errors,workerTargets,checks},null,2));
  console.log('Recorded execution screen acceptance passed.');
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
