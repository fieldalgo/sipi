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
  async function calculate() {
    await cdp.evaluate('document.querySelector("#run").click()');
    await until(()=>cdp.evaluate('!document.querySelector("#run").disabled'),'calculation finished',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),false,await status());
    return cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
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
  await input('{"schema":"sipi.lumped-network/1","schema":"invalid"}');
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
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
  await input(cases.line);
  await cdp.evaluate(`document.querySelector('#modes').checked=true;document.querySelector('#modes').dispatchEvent(new Event('change'));`);
  result=await calculate();assert.equal(result.status,'complete');assert.equal(result.result.diagnostics.modes.status,'failed');
  assert.equal(await cdp.evaluate('document.querySelector("#diagnostic-status").hidden'),false);
  await cdp.evaluate('document.querySelector("#example").click();document.querySelector("#run").click();document.querySelector("#cancel").click()');
  await until(async()=>(await status()).startsWith('Calculation cancelled'),'cancel pending start');
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  result=await calculate();assert.equal(result.status,'complete');
  // A late successful result must not replace edited input or become exportable.
  await cdp.evaluate(`document.querySelector('#run').click();document.querySelector('#input-text').value+=' ';document.querySelector('#input-text').dispatchEvent(new Event('input'));`);
  await until(()=>cdp.evaluate('!document.querySelector("#run").disabled'),'stale completion');
  assert.equal(await cdp.evaluate('document.querySelector("#output").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#save-result").disabled'),true);
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth <= innerWidth'),true);
  await writeFile(join(output,'saved-mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(async()=>/closed|stopped/.test(await status()),'shutdown');
  if(!webRoot) await until(()=>server.exitCode===0,'server exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'local-native',
    externalRequests:remoteRequests,errors,workerTargets,checks:['raw duplicate rejection','canonical input download','RLC native S within 1e-12',
      'result download','Unicode file input','incomplete study','refined target failure history','optional diagnostic failure',
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
