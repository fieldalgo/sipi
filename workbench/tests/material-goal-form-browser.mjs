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

  const p=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/material_goal_form_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(p.status,0,p.stderr);const cases=JSON.parse(p.stdout),checks=[];
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const text=()=>cdp.evaluate('document.querySelector("#input-text").value');
  const input=async value=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(value)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const field=async(name,value)=>cdp.evaluate('document.querySelector("#material-goal-'+name+'").value='+JSON.stringify(value)+';document.querySelector("#material-goal-'+name+'").dispatchEvent(new Event("input"))');
  const click=async id=>cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#material-goal-target").disabled'),'form operation',180000);
  async function example(id){await cdp.evaluate('document.querySelector("#example-choice").value='+JSON.stringify(id));await click('example');}
  async function download(button,name){await rm(join(downloads,name),{force:true});await click(button);return until(async()=>{try{return await readFile(join(downloads,name),'utf8');}catch{}},name);}
  function close(actual,expected,path='result'){
    if(typeof expected==='number'){assert.equal(typeof actual,'number',path);assert.ok(Number.isFinite(actual)&&Math.abs(actual-expected)<=1e-10*Math.max(Math.abs(expected),1e-30),path);}
    else if(expected!==null&&typeof expected==='object'){assert.deepEqual(Object.keys(actual).sort(),Object.keys(expected).sort(),path);for(const k of Object.keys(expected))close(actual[k],expected[k],path+'.'+k);}
    else assert.equal(actual,expected,path);
  }
  await example('rlc');const rlc=await text();assert.equal(await cdp.evaluate('document.querySelector("#material-goal-editor").hidden'),true);
  await click('project-start');await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'project start',180000);
  await click('record');await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'RLC record',180000);
  const firstRaw=await download('save-record','sipi-execution-record.json');
  const records=[];
  for(const item of cases){
    await example(item.kind+'-target');const before=await text();
    assert.equal(await cdp.evaluate('document.querySelector("#material-goal-editor").hidden'),false);
    assert.equal(await cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor label[for]")).filter(label=>!label.hidden).length'),6);
    for(const [key,value] of Object.entries({target:String(item.target),tolerance:'1',lower:'2.5',upper:'7.5',frequency:'2e8',budget:'48'}))await field(key,value);
    assert.equal(await text(),before);
    assert.equal(await cdp.evaluate('["run","record","check","save-input","project-save","project-duplicate"].every(id=>document.getElementById(id).disabled)'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#output").hidden && document.querySelector("#material-results").hidden'),true);
    await click('material-goal-apply');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-target").disabled'),true);await idle();
    assert.match(await status(),/settings applied and checked/);assert.deepEqual(JSON.parse(await text()),JSON.parse(item.text));
    assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
    assert.deepEqual(JSON.parse(await download('save-input','sipi-input.json')),JSON.parse(item.text));
    await click('record');await until(()=>cdp.evaluate('!document.querySelector("#record").disabled'),'edited material record',180000);
    const got=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
    assert.equal(got.status,item.expected.status);assert.deepEqual(got.input,item.expected.input);close(got.result,item.expected.result);close(got.error,item.expected.error);
    if(got.status==='complete')assert.ok(Math.abs(got.result.residual)<=1&&Math.abs(got.result.refined_residual)<=1);
    else {assert.match(got.error.message,/not bracketed/);assert.equal(got.error.history.length,2);assert.equal(await cdp.evaluate('document.querySelector("#material-results").hidden'),false);assert.match(await cdp.evaluate('document.querySelector("#material-results h3").textContent'),/target not accepted/);}
    const raw=await download('save-record','sipi-execution-record.json');records.push(JSON.parse(raw));
    await writeFile(join(output,item.id+'-execution.json'),JSON.stringify(got,null,2));await writeFile(join(output,item.id+'-record.json'),raw);
    const project=JSON.parse(await download('project-save','sipi-analysis-project.json'));
    assert.equal(project.designs[0].records.length,records.length+1);assert.deepEqual(project.designs[0].records[0],JSON.parse(firstRaw));
    assert.deepEqual(JSON.parse(project.designs[0].source_text),JSON.parse(item.text));
    checks.push(item.id+': explicit apply, exact changed input, actual outcome/history/refinement, export and retained project history');
  }
  const saved=await download('project-save','sipi-analysis-project.json'),savedInput=await text();
  await example('rlc');const path=join(profile,'material-project.json');await writeFile(path,saved);
  const dom=await cdp.call('DOM.getDocument'),file=await cdp.call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#project-file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[path]});await idle();
  assert.equal(await text(),savedInput);assert.match(await cdp.evaluate('document.querySelector("#material-goal-editor").textContent'),/Debye strength/);
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[0].run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');
  await click('project-view');await idle();
  assert.equal(await text(),savedInput);assert.match(await cdp.evaluate('document.querySelector("#material-goal-editor").textContent'),/Debye strength/);
  assert.match(await cdp.evaluate('document.querySelector("#material-results h3").textContent'),/^Saved run/);
  assert.deepEqual(JSON.parse(await download('save-record','sipi-execution-record.json')),records[0]);
  checks.push('project reopen restores form; historical result leaves current material settings and original record unchanged');
  for(const [key,value] of [['target',''],['lower','9'],['budget','129']]){
    const before=await text();await field(key,value);await click('material-goal-apply');await idle();
    assert.equal(await text(),before);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
    await click('material-goal-reset');assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  }
  // A different spelling of an unchanged number must not leave a stuck draft.
  await field('frequency','2e8');await click('material-goal-apply');await idle();
  assert.equal(await text(),savedInput);assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  checks.push('invalid values preserve input; reset and semantic no-op apply unblock execution');
  await example('constant-target');const original=await text();
  const duplicate=original.replace('{','{"target_ohm":50,');await input(duplicate);await field('target','51');await click('material-goal-apply');await idle();
  assert.equal(await text(),duplicate);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
  checks.push('duplicate original JSON rejected before form transformation');
  await input(original);await field('target','51');
  await cdp.evaluate(`(async()=>{const browser=document.documentElement.dataset.runtime==='browser';const m=await import(browser?'./browser-transport.js':'./transport.js');const p=(browser?m.BrowserTransport:m.LocalTransport).prototype;const original=p.run;p.run=async function(input){p.run=original;await new Promise(resolve=>window.releaseFormApply=resolve);return original.call(this,input);};})()`);
  await click('material-goal-apply');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-target").disabled'),true);
  await input(rlc);await cdp.evaluate('window.releaseFormApply()');await idle();
  assert.equal(await text(),rlc);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-editor").hidden'),true);
  checks.push('stale validated form response cannot replace changed source');
  await example('debye-target');
  for(const width of [1400,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
    const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-goal-editor").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()');
    await writeFile(join(output,'material-form-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));
  }
  await click('exit');await until(async()=>/closed|stopped/.test(await status()),'shutdown');
  assert.equal(await cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor input, #material-goal-editor button")).every(e=>e.disabled)'),true);
  if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  checks.push('labeled fields, responsive widths, busy/closed guards and clean shutdown');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',checks,errors,externalRequests:remoteRequests,workerTargets},null,2));
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
