// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-mesh-browser');
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
  await cdp.call('Page.navigate',{url});
  await until(()=>cdp.evaluate('!!document.querySelector("#cross-section rect")'),'drawing');
  await cdp.evaluate(`document.querySelector('.mesh-settings').open=true;
    window.meshRequests=[];
    const post=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(message,...rest){if(message.input)window.meshRequests.push(message.input);return post.call(this,message,...rest)};
    const fetchOriginal=window.fetch;
    window.fetch=(url,options)=>{if(url==='/api/job' && options?.method==='POST')window.meshRequests.push(JSON.parse(options.body));return fetchOriginal(url,options)};`);
  async function click(id) {
    await cdp.evaluate(`document.getElementById('${id}').click()`);
    await until(()=>cdp.evaluate('!document.querySelector("#mesh-inspect").disabled'),'mesh action complete',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function save(id,name) {
    await rm(join(downloads,name),{force:true});await click(id);
    return await until(async()=>{try{return JSON.parse(await readFile(join(downloads,name),'utf8'))}catch{}},name);
  }
  async function open(value, selector='#file') {
    const filePath=join(profile,'mesh input.json');await writeFile(filePath,JSON.stringify(value));
    const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector});
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[filePath]});
    await until(()=>cdp.evaluate('!document.querySelector("#mesh-inspect").disabled'),'mesh file loaded',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  const mode=()=>cdp.evaluate('document.querySelector("#mesh-mode").textContent');
  assert.equal(await mode(),'Automatic mesh');
  assert.equal(await cdp.evaluate('document.querySelector("#mesh-refine").disabled'),true);
  await click('mesh-inspect');assert.equal(await mode(),'Automatic mesh');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const initial=await save('save-editable','sipi-editable-design.json');
  assert.equal(await mode(),'Automatic mesh');
  await click('calculate');
  const z=await cdp.evaluate('document.querySelector("#z-value").textContent');
  await click('mesh-inspect');assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#z-value").textContent'),z);
  await click('mesh-refine');assert.equal(await mode(),'Fixed mesh');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const refined=await save('save-editable','sipi-editable-design.json');
  const expected={...initial.cross_section.mesh};for(const key of ['edge_size','far_size','grade'])expected[key]/=2;
  assert.deepEqual(refined.cross_section.mesh,expected);assert.deepEqual(refined.parameters,initial.parameters);
  await cdp.evaluate(`for(const u of ['mil','mm']){document.querySelector('#unit').value=u;document.querySelector('#unit').dispatchEvent(new Event('change'))}
    document.querySelector('#width').value='.6';document.querySelector('#width').dispatchEvent(new Event('input'));`);
  const edited=await save('save-editable','sipi-editable-design.json');assert.deepEqual(edited.cross_section.mesh,expected);
  assert.equal(edited.parameters.width,.0006);
  await click('project-duplicate');
  const project=await save('project-save','sipi-project.json');assert.equal(project.designs.length,2);
  for(const d of project.designs)assert.deepEqual(JSON.parse(d.source_text).cross_section.mesh,expected);
  await click('mesh-auto');assert.equal(await mode(),'Automatic mesh');
  assert.equal(await cdp.evaluate('document.querySelector("#mesh-refine").disabled'),true);
  await cdp.evaluate("document.querySelector('#width').value='.5';document.querySelector('#width').dispatchEvent(new Event('input'))");
  const automatic=await save('save-editable','sipi-editable-design.json');assert.deepEqual(automatic.cross_section.mesh,initial.cross_section.mesh);
  await open(refined);assert.equal(await mode(),'Fixed mesh');
  assert.deepEqual((await save('save-editable','sipi-editable-design.json')).cross_section.mesh,expected);
  await open(project,'#project-file');assert.equal(await mode(),'Fixed mesh');
  assert.deepEqual((await save('save-editable','sipi-editable-design.json')).cross_section.mesh,expected);
  // Cancel an inspection before completion; its late result must not restore
  // stale values or disable another request. Worker cancellation resets loading.
  await cdp.evaluate("document.querySelector('#mesh-inspect').click();document.querySelector('#cancel').click()");
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel inspection');
  await click('mesh-inspect');assert.equal(await mode(),'Fixed mesh');
  const requests=await cdp.evaluate('window.meshRequests');
  const first= requests.find(x=>x.action==='document');assert.ok(first && !Object.hasOwn(first,'mesh'));
  assert.ok(requests.some(x=>x.action==='template-document' && x.mesh?.edge_size===expected.edge_size));
  assert.ok(requests.filter(x=>x.action==='document').every(x=>!Object.hasOwn(x,'design')));
  const layouts=[];
  for(const width of [1400,768,390,320]) {
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    await cdp.evaluate('document.querySelector(".mesh-settings").scrollIntoView({block:"center"})');
    const row=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,buttons:[...document.querySelectorAll('.mesh-actions button')].map(e=>{const b=e.getBoundingClientRect();return {left:b.left,right:b.right,height:b.height}})}))()`);
    assert.ok(row.scrollWidth<=width && row.buttons.every(b=>b.height>=44 && b.left>=0 && b.right<=width));layouts.push(row);
    await writeFile(join(output,`mesh-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  await writeFile(join(output,'project.json'),JSON.stringify(project,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(()=>cdp.evaluate('/closed|stopped/.test(document.querySelector("#status").textContent)'),'close');
  if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'worker':'native',initial_mesh:initial.cross_section.mesh,refined_mesh:expected,request_count:requests.length,layouts,errors,externalRequests:remoteRequests},null,2));
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
