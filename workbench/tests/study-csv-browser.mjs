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

  const fixture=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/study_csv_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixture.status,0,fixture.stderr);const cases=JSON.parse(fixture.stdout),checks=[],records=[];
  const text=()=>cdp.evaluate('document.querySelector("#input-text").value');
  const status=()=>cdp.evaluate('document.querySelector("#status").textContent');
  const input=async value=>cdp.evaluate('document.querySelector("#input-text").value='+JSON.stringify(value)+';document.querySelector("#input-text").dispatchEvent(new Event("input"))');
  const field=async(name,value)=>cdp.evaluate('document.querySelector("#material-goal-'+name+'").value='+JSON.stringify(value)+';document.querySelector("#material-goal-'+name+'").dispatchEvent(new Event("input"))');
  const click=async id=>cdp.evaluate('document.getElementById('+JSON.stringify(id)+').click()');
  const idle=()=>until(()=>cdp.evaluate('!document.querySelector("#material-goal-target").disabled'),'uniform operation',180000);
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
  const csvReady=()=>cdp.evaluate('!document.querySelector("#save-study-csv").hidden && !document.querySelector("#save-study-csv").disabled');
  const csvAbsent=()=>cdp.evaluate('document.querySelector("#save-study-csv").hidden && document.querySelector("#save-study-csv").disabled');
  async function verifyCSV(name,csv,execution){
    const csvPath=join(output,name+'.csv'),jsonPath=join(output,name+'-execution.json');await writeFile(csvPath,csv);await writeFile(jsonPath,JSON.stringify(execution,null,2));
    const checked=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/check_study_csv.py',csvPath,jsonPath],{encoding:'utf8'});
    assert.equal(checked.status,0,checked.stderr);assert.equal(JSON.parse(checked.stdout).status,'passed');
  }
  await example('rlc');assert.equal(await csvAbsent(),true);await click('run');await idle();assert.equal(await csvAbsent(),true);
  checks.push('unsupported network output has no sample CSV action');
  for(const [index,item] of cases.entries()){
    await openFile(JSON.stringify(item.input));assert.equal(await csvAbsent(),true);
    if(index===0){await click('project-start');await idle();}
    const source=await text();await click('record');assert.equal(await cdp.evaluate('document.querySelector("#save-study-csv").disabled'),true);await idle();
    assert.equal(await csvReady(),true);assert.equal(await cdp.evaluate('document.querySelector("#save-study-csv").textContent'),'Save sample table CSV ↓');
    const execution=await cdp.evaluate('JSON.parse(document.querySelector("#output").textContent)');compare(execution,item.execution);assert.equal(await text(),source);
    const csv=await download('save-study-csv','sipi-study-samples.csv');await verifyCSV(item.name,csv,execution);
    const raw=await download('save-record','sipi-execution-record.json');records.push({raw,value:JSON.parse(raw),csv,execution});
    assert.deepEqual(records.at(-1).value.receipt.execution,execution);
    if(item.name==='incomplete'){assert.equal(execution.result.summary,null);assert.deepEqual(execution.result.rows.filter(row=>row.error).map(row=>row.index),[0,2]);}
    checks.push(item.name+': current CSV independently parsed with exact ordered values, precision, failure cells and original record');
  }
  await field('mean','2.5');assert.equal(await csvAbsent(),true);await click('material-goal-reset');assert.equal(await csvAbsent(),true);
  await openFile(JSON.stringify(cases[1].input));const current=await text();await field('lowerFirst','4.5');
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[0].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');await click('project-view');await idle();
  assert.equal(await csvReady(),true);assert.equal(await text(),current);assert.equal(await cdp.evaluate('document.querySelector("#save-study-csv").textContent'),'Save saved-run samples CSV ↓');
  const historical=await download('save-study-csv','sipi-saved-study-samples.csv');assert.equal(historical,records[0].csv);await verifyCSV('historical',historical,records[0].execution);
  assert.equal(await download('save-record','sipi-execution-record.json'),records[0].raw);
  assert.match(await cdp.evaluate('document.querySelector("#material-goal-note").textContent'),/Unapplied settings/);assert.equal(await text(),current);await click('material-goal-reset');assert.equal(await csvAbsent(),true);
  checks.push('unapplied edits clear current export; explicit historical export preserves the unrelated current draft; historical CSV is the selected old execution without replacing current input or raw record');
  const project=await download('project-save','sipi-analysis-project.json');assert.equal(await csvAbsent(),true);
  assert.equal(JSON.parse(project).designs[0].records.length,3);await example('rlc');await openFile(project,true);assert.equal(await csvAbsent(),true);assert.equal(await text(),current);
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[2].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');await click('project-view');await idle();
  assert.equal(await text(),current);const mixed=await download('save-study-csv','sipi-saved-study-samples.csv');assert.equal(mixed,records[2].csv);await verifyCSV('restored-incomplete',mixed,records[2].execution);
  checks.push('project reload restores history and failed rows; historical download never recalculates or selects the current design');
  for(const width of [1400,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});assert.equal(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),true);
    const clip=await cdp.evaluate('(()=>{const r=document.querySelector("#material-results").getBoundingClientRect(),b=document.querySelector("#save-study-csv").getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:b.bottom-r.top+10,scale:1}})()');
    await writeFile(join(output,'study-csv-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip})).data,'base64'));
  }
  await click('cancel');await idle();assert.equal(await csvAbsent(),true);
  await cdp.evaluate(`(async()=>{const browser=document.documentElement.dataset.runtime==='browser';const m=await import(browser?'./browser-transport.js':'./transport.js');const p=(browser?m.BrowserTransport:m.LocalTransport).prototype;const original=p.run;p.run=async function(input){p.run=original;await new Promise(resolve=>window.releaseCSVRun=resolve);return original.call(this,input);};})()`);
  await click('run');assert.equal(await cdp.evaluate('document.querySelector("#save-study-csv").disabled'),true);
  const replacement='{}';await input(replacement);await cdp.evaluate('window.releaseCSVRun()');await idle();assert.equal(await text(),replacement);assert.equal(await csvAbsent(),true);
  checks.push('cancel, edited source and delayed stale result cannot retain or enable CSV export');
  await cdp.evaluate('document.querySelector("#project-record").value='+JSON.stringify(records[2].value.run_id)+';document.querySelector("#project-record").dispatchEvent(new Event("change"))');await click('project-view');await idle();assert.equal(await csvReady(),true);
  await rm(join(downloads,'sipi-saved-study-samples.csv'),{force:true});await click('exit');await until(async()=>/closed|stopped/.test(await status()),'shutdown');
  assert.equal(await cdp.evaluate('document.querySelector("#save-study-csv").disabled'),true);await cdp.evaluate('document.querySelector("#save-study-csv").onclick()');await pause(200);await assert.rejects(readFile(join(downloads,'sipi-saved-study-samples.csv')));
  if(!webRoot)await until(()=>server.exitCode===0,'host exit');assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  checks.push('closed workspace refuses CSV download; clean shutdown, no JavaScript errors or external requests');
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',checks,errors,externalRequests:remoteRequests,workerTargets},null,2));
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,outputHidden:document.querySelector("#output")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();await pause(400);await rm(profile,{recursive:true,force:true});
}
