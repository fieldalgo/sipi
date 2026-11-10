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

  const fixture=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/material_sweep_form_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const cases=JSON.parse(fixture.stdout),checks=[],records=[];
  const text=()=>cdp.evaluate('document.querySelector("#input-text").value');
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async value=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(value)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const field=async(name,value)=>cdp.evaluate('document.querySelector("#material-goal-'+name+'").value='+JSON.stringify(value)+';document.querySelector("#material-goal-'+name+'").dispatchEvent(new Event("input"))');
  const click=async id=>cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#material-goal-target").disabled'),'sweep operation',180000);
  const visible=()=>cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor label")).filter(l=>!l.hidden).map(l=>l.querySelector("input").id)');
  async function example(id){await cdp.evaluate('document.querySelector("#example-choice").value='+JSON.stringify(id));await click('example');}
  async function download(id,name){await rm(join(downloads,name),{force:true});await click(id);return until(async()=>{try{return await readFile(join(downloads,name),'utf8');}catch{}},name);}
  let files=0;
  async function openFile(value,project=false){const path=join(profile,'sweep-'+(++files)+'.json');await writeFile(path,value);const doc=await cdp.call('DOM.getDocument'),node=await cdp.call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:project?'#project-file':'#file'});await cdp.call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[path]});if(project)await idle();else await until(async()=>(await status()).startsWith('File opened'),'open input');}
  function compare(a,b,path='execution'){
    if(typeof b==='number'){assert.equal(typeof a,'number',path);assert.ok(Number.isFinite(a)&&Math.abs(a-b)<=Math.max(1e-10*Math.abs(b),1e-14),path);}
    else if(b!==null&&typeof b==='object'){assert.deepEqual(Object.keys(a).sort(),Object.keys(b).sort(),path);for(const k of Object.keys(b))compare(a[k],b[k],path+'.'+k);}
    else assert.equal(a,b,path);
  }
  for(const [index,item] of cases.slice(0,2).entries()){
    if(index===0)await example('material-sweep');else await openFile(JSON.stringify(item.original));
    assert.deepEqual(JSON.parse(await text()),item.original);assert.match(await cdp.evaluate('document.querySelector("#material-goal-editor h3").textContent'),/sweep/);
    assert.deepEqual(await visible(),['lower','upper','frequency','count'].map(k=>'material-goal-'+k));
    await field('count','7');
    if(index===0)await example('material-sweep');else await openFile(JSON.stringify(item.original));
    assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").value'),String(item.original.sampling.count));
    assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
    if(index===0){await click('project-start');await idle();}
    const before=await text();
    for(const [key,value] of Object.entries({lower:'1',upper:'5',frequency:'2e8',count:'5'}))await field(key,value);
    assert.equal(await text(),before);assert.equal(await cdp.evaluate('["run","record","check","save-input","project-save"].every(id=>document.getElementById(id).disabled)'),true);
    await click('material-goal-apply');await idle();assert.match(await status(),/applied and checked/);assert.deepEqual(JSON.parse(await text()),item.input);
    assert.deepEqual(JSON.parse(await download('save-input','sipi-input.json')),item.input);
    await click('record');await idle();const execution=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');
    assert.equal(execution.status,'complete');assert.equal(execution.result.rows.length,5);compare(execution,item.execution);
    const raw=await download('save-record','sipi-execution-record.json');records.push({raw,value:JSON.parse(raw)});
    await writeFile(join(output,item.name+'-execution.json'),JSON.stringify(execution,null,2));await writeFile(join(output,item.name+'-record.json'),raw);
    const project=JSON.parse(await download('project-save','sipi-analysis-project.json'));assert.equal(project.designs[0].records.length,index+1);
    for(let i=0;i<=index;i++)assert.deepEqual(project.designs[0].records[i],records[i].value);
    checks.push(item.name+': four explicit settings, exact normalized input, five rows and retained record/project');
  }
  await example('material-sweep');const before=await text();
  await field('count','7');await input(before);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").value'),'8');
  assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  for(const [key,value] of Object.entries({lower:'-.5',upper:'2',count:'6'}))await field(key,value);
  await click('material-goal-apply');await idle();assert.equal(await text(),before);assert.match(await status(),/relative permittivity/);
  assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),true);await click('material-goal-reset');assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  for(const [key,value] of [['count','1'],['count','129'],['lower','7'],['frequency','-1']]){await field(key,value);await click('material-goal-apply');await idle();assert.equal(await text(),before);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);await click('material-goal-reset');}
  const duplicate=before.replace('{','{"sampling":{},');await input(duplicate);await field('count','5');await click('material-goal-apply');await idle();assert.equal(await text(),duplicate);assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
  checks.push('invalid corner/bounds/count/frequency and duplicate source leave original input unchanged; reset recovers');
  await example('material-sweep');await field('count','7');await example('constant-target');
  assert.equal((await visible()).length,6);assert.match(await cdp.evaluate('document.querySelector("#material-goal-editor h3").textContent'),/target/);const goal=await text();await field('count','9');assert.equal(await text(),goal);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-apply").disabled'),true);
  await field('target','51');await example('constant-target');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-target").value'),'50');assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  await example('material-sweep');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").value'),'8');assert.equal(await cdp.evaluate('document.querySelector("#run").disabled'),false);
  await example('correlated-study');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-editor").hidden'),true);
  const normal=cases[2];await openFile(JSON.stringify(normal.input));assert.equal((await visible()).length,5);
  await click('record');await idle();const incomplete=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');compare(incomplete,normal.execution);
  assert.equal(incomplete.status,'incomplete');assert.equal(incomplete.result.failed,2);assert.equal(incomplete.result.summary,null);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#material-results table").length'),1);
  const normalRaw=await download('save-record','sipi-execution-record.json');records.push({raw:normalRaw,value:JSON.parse(normalRaw)});await writeFile(join(output,'mixed-normal-execution.json'),JSON.stringify(incomplete,null,2));
  checks.push('goal/sweep/normal/unsupported switches discard drafts, hidden fields have no effect, original normal failures remain incomplete');
  await openFile(JSON.stringify(cases[1].input));const saved=await download('project-save','sipi-analysis-project.json'),savedInput=await text();
  await example('rlc');await openFile(saved,true);assert.equal(await text(),savedInput);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").value'),'5');
  await field('count','7');await openFile(saved,true);assert.equal(await text(),savedInput);assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").value'),'5');
  checks.push('identical example, file, raw input and project reloads reset drafts, including scalar goal settings');
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[0].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');await click('project-view');await idle();
  assert.equal(await text(),savedInput);assert.match(await cdp.evaluate('document.querySelector("#material-goal-editor").textContent'),/Debye strength/);assert.match(await cdp.evaluate('document.querySelector("#material-results h3").textContent'),/^Saved run/);
  assert.equal(await download('save-record','sipi-execution-record.json'),records[0].raw);
  for(const width of [1400,390,320]){await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-goal-editor").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})()');await writeFile(join(output,'material-sweep-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));}
  checks.push('project reopens current sweep settings and historical record without changing either; labeled responsive form');
  await field('count','6');
  await cdp.evaluate(`(async()=>{const browser=document.documentElement.dataset.runtime==='browser';const m=await import(browser?'./browser-transport.js':'./transport.js');const p=(browser?m.BrowserTransport:m.LocalTransport).prototype;const original=p.run;p.run=async function(input){p.run=original;await new Promise(resolve=>window.releaseSweepApply=resolve);return original.call(this,input);};})()`);
  await click('material-goal-apply');assert.equal(await cdp.evaluate('document.querySelector("#material-goal-count").disabled'),true);const raw=JSON.stringify(normal.input);await input(raw);await cdp.evaluate('window.releaseSweepApply()');await idle();assert.equal(await text(),raw);assert.equal((await visible()).length,5);
  await example('material-sweep');await click('exit');await until(async()=>/closed|stopped/.test(await status()),'shutdown');assert.equal(await cdp.evaluate('Array.from(document.querySelectorAll("#material-goal-editor input, #material-goal-editor button")).every(e=>e.disabled)'),true);if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  checks.push('stale study apply cannot replace changed source; busy/closed guards and clean shutdown');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',checks,errors,externalRequests:remoteRequests,workerTargets},null,2));
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,
    serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
