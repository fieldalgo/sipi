// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-geometry-view-browser');
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
const actions=[];
try {
  const serverArgs = webRoot ? ['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot] : ['gui','--no-browser'];
  const server = spawn(webRoot ? (process.env.SIPI_PYTHON || 'python') : process.env.SIPI_CONSOLE, serverArgs, {env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});
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
  await cdp.evaluate(`document.querySelector('#domain-settings').open=true;
    window.domainRequests=[];window.completedResults=[];
    const observedWorkers=new WeakSet();
    const post=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(message,...rest){if(message.input)window.domainRequests.push(message.input);if(!observedWorkers.has(this)){observedWorkers.add(this);this.addEventListener('message',event=>{if(event.data.status==='complete')window.completedResults.push(event.data.result)})}return post.call(this,message,...rest)};
    const fetchOriginal=window.fetch;
    window.fetch=(url,options)=>{if(url==='/api/job' && options?.method==='POST')window.domainRequests.push(JSON.parse(options.body));return fetchOriginal(url,options).then(async response=>{if(url==='/api/job'&&options?.method==='GET'){const value=await response.clone().json();if(value.status==='complete')window.completedResults.push(value.result)}return response})};`);
  async function ready(timeout=180000) { await until(()=>cdp.evaluate('!document.querySelector("#domain-inspect").disabled'),'domain action complete',timeout); }
  async function click(id, expectError=false) {
    const started=performance.now();
    await cdp.evaluate(`document.getElementById('${id}').click()`);await ready(id==='design'?310000:180000);
    actions.push({id,seconds:(performance.now()-started)/1000});
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),expectError,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function set(id,value) { await cdp.evaluate(`(()=>{const e=document.getElementById(${JSON.stringify(id)});e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('input'))})()`); }
  async function save(id='save-editable',name='sipi-editable-design.json') {
    await rm(join(downloads,name),{force:true});await click(id);
    return await until(async()=>{try{return JSON.parse(await readFile(join(downloads,name),'utf8'))}catch{}},name);
  }
  async function open(value,selector='#file') {
    const path=join(profile,'domain input.json');await writeFile(path,typeof value==='string'?value:JSON.stringify(value));
    const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector});
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[path]});await ready();
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function choose(name) { await cdp.evaluate(`document.querySelector('[data-template=${name}]').click()`); }
  async function switchDesign(id) {await cdp.evaluate(`const e=document.querySelector('#project-design');e.value=${JSON.stringify(id)};e.dispatchEvent(new Event('change'))`);await ready();}

  const fixtures={};
  for(const file of ['normal_film_cases.py','normal_coplanar_cases.py','normal_unbacked_cases.py']) {
    const run=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/'+file],{encoding:'utf8'});
    assert.equal(run.status,0,run.stderr);Object.assign(fixtures,JSON.parse(run.stdout));
  }
  assert.equal(Object.keys(fixtures).length,6);
  const checks=[],layouts=[];
  for(const [name,precise] of Object.entries(fixtures)) {
    await choose(name);
    assert.equal(await cdp.evaluate('document.querySelector("#geometry-view-controls").hidden'),true);
    await open(precise);
    assert.equal(await cdp.evaluate('document.querySelector("#cross-section").dataset.geometryView'),'full');
    assert.equal(await cdp.evaluate('document.querySelector("#upper-air-mode-label").textContent'),'Upper air clearance');
    assert.equal(await cdp.evaluate('document.querySelector("#upper-air-value-label").textContent'),'Upper air clearance');
    const before=await save();
    await click('calculate');const physical=await cdp.evaluate('window.completedResults.at(-1)');
    assert.ok(physical.line.C[0][0]>0);assert.deepEqual(physical.document,precise.cross_section);
    await writeFile(join(output,name+'-physical.json'),JSON.stringify(physical,null,2));
    const snapshot=await cdp.evaluate('JSON.stringify({inputs:[...document.querySelectorAll("input,select")].filter(e=>e.type!=="file").map(e=>[e.id,e.value]),requests:window.domainRequests,results:window.completedResults})');
    await cdp.evaluate('document.querySelector("#geometry-detail").click()');
    assert.equal(await cdp.evaluate('document.querySelector("#cross-section").dataset.geometryView'),'detail');
    assert.equal(await cdp.evaluate('document.querySelector("#geometry-detail").getAttribute("aria-pressed")'),'true');
    assert.equal(await cdp.evaluate('document.querySelector("#geometry-detail-note").hidden'),false);
    assert.match(await cdp.evaluate('document.querySelector("#geometry-detail-note").textContent'),/Outer boundaries are cropped/);
    assert.equal(await cdp.evaluate('JSON.stringify({inputs:[...document.querySelectorAll("input,select")].filter(e=>e.type!=="file").map(e=>[e.id,e.value]),requests:window.domainRequests,results:window.completedResults})'),snapshot);
    const view=await cdp.evaluate('JSON.parse(document.querySelector("#cross-section").dataset.displayBounds)');
    const polygons=await cdp.evaluate('[...document.querySelectorAll("#cross-section polygon[data-region]")].map(e=>({name:e.dataset.region,points:[...e.points].map(p=>[p.x,p.y]),clip:e.parentElement.getAttribute("clip-path")}))');
    for(const region of precise.cross_section.dielectric_regions) {
      const shape=polygons.find(p=>p.name===region.name);assert.ok(shape);assert.equal(shape.clip,'url(#geometry-detail-clip)');
      assert.equal(shape.points.length,region.vertices.length);
      region.vertices.forEach(([x,y],i)=>{
        assert.ok(Math.abs(shape.points[i][0]-(65+(x-view.left)/(view.right-view.left)*630))<1e-3);
        assert.ok(Math.abs(shape.points[i][1]-(245-(y-view.bottom)/(view.top-view.bottom)*210))<1e-3);
      });
    }
    assert.equal(await cdp.evaluate('[...document.querySelectorAll("#cross-section text")].some(e=>e.textContent==="GROUND PLANE")'),false);
    if(name.includes('coupled_conformal')||name==='conformal_coated_microstrip') {
      for(const width of [1400,768,390,320]) {
        await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});
        await cdp.evaluate('document.querySelector("#geometry-view-controls").scrollIntoView({block:"center"})');
        await until(()=>cdp.evaluate('[...document.querySelectorAll("#cross-section [data-geometry-label], #cross-section [data-region-label]")].every(e=>parseFloat(getComputedStyle(e).fontSize)*e.getScreenCTM().a>=10.5)'), 'readable detail labels');
        const layout=await cdp.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:["geometry-full","geometry-detail"].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})})');
        assert.ok(layout.scrollWidth<=width);for(const c of layout.controls)assert.ok(c.left>=0&&c.right<=width&&c.height>=44,JSON.stringify(c));
        layouts.push({name,...layout});await writeFile(join(output,name+'-'+width+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
      }
    }
    await cdp.evaluate('document.querySelector("#geometry-full").click()');
    assert.equal(await cdp.evaluate('document.querySelector("#cross-section").dataset.geometryView'),'full');
    const after=await save();assert.deepEqual(after,before);
    await writeFile(join(output,name+'-design.json'),JSON.stringify(after,null,2));
    await cdp.evaluate('document.querySelector("#geometry-detail").click()');
    await set('coating_thickness','.025');
    assert.equal(await cdp.evaluate('document.querySelector("#geometry-view-controls").hidden'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#geometry-detail-note").hidden'),true);
    checks.push({name,view,exact_saved_before_after:true,display_only_no_transport:true,engine_vertices_retained:true});
  }
  const longGeometry=structuredClone(fixtures.conformal_coated_unbacked_coplanar.cross_section);
  longGeometry.layers.forEach((l,i)=>{l.name='L'+i+'W'.repeat(30)});
  longGeometry.traces.forEach((t,i)=>{t.name='T'+i+'W'.repeat(30)});
  longGeometry.dielectric_regions.forEach((d,i)=>{d.name='R'+i+'W'.repeat(30)});
  await open(longGeometry);const importedBefore=await save('save','sipi-cross-section.json');
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:320,height:1200,deviceScaleFactor:1,mobile:true});
  await cdp.evaluate('document.querySelector("#geometry-detail").click()');
  await until(()=>cdp.evaluate('[...document.querySelectorAll("#cross-section [data-geometry-label], #cross-section [data-region-label]")].every(e=>parseFloat(getComputedStyle(e).fontSize)*e.getScreenCTM().a>=10.5)'), 'readable imported labels');
  const wrapped=await cdp.evaluate('[...document.querySelectorAll("#cross-section [data-geometry-label], #cross-section [data-region-label]")].map(e=>({text:e.getAttribute("aria-label"),x:e.getBBox().x,right:e.getBBox().x+e.getBBox().width,lines:e.querySelectorAll("tspan").length}))');
  assert.ok(wrapped.some(v=>v.lines>1));for(const label of wrapped)assert.ok(label.x>=8&&label.right<=752,JSON.stringify(label));
  await cdp.evaluate('document.querySelector("#geometry-view-controls").scrollIntoView({block:"start"})');
  await writeFile(join(output,'long-labels-320.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  const importedAfter=await save('save','sipi-cross-section.json');assert.deepEqual(importedAfter,importedBefore);assert.deepEqual(importedAfter,longGeometry);
  checks.push({name:'long imported labels',wrapped,geometry_export_exact:true});
  await choose('microstrip');
  assert.equal(await cdp.evaluate('document.querySelector("#upper-air-mode-label").textContent'),'Air layer height');
  assert.equal(await cdp.evaluate('document.querySelector("#upper-air-value-label").textContent'),'Air height');
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',scope:'Six normal-film forward results and exact editable inputs through display-only detail/full toggles; long imported labels retain geometry export',actions,checks,layouts,errors,externalRequests:remoteRequests},null,2));
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
