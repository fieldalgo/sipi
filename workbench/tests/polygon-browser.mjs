// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-polygon-browser');
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
  async function save(id='save-editable',name='sipi-editable-design.json',keepsError=false) {
    await rm(join(downloads,name),{force:true});await click(id,keepsError);
    return await until(async()=>{try{return JSON.parse(await readFile(join(downloads,name),'utf8'))}catch{}},name);
  }
  async function open(value,selector='#file',expectError=false) {
    const path=join(profile,'domain input.json');await writeFile(path,typeof value==='string'?value:JSON.stringify(value));
    const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector});
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[path]});await ready();
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),expectError,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function choose(name) { await cdp.evaluate(`document.querySelector('[data-template=${name}]').click()`); }
  async function switchDesign(id) {await cdp.evaluate(`const e=document.querySelector('#project-design');e.value=${JSON.stringify(id)};e.dispatchEvent(new Event('change'))`);await ready();}


  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/polygon_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const fixtures=JSON.parse(fixtureRun.stdout);
  const drawingChecks=[],results={},layouts=[];
  async function inspect(doc){
    const actual=await cdp.evaluate(`(()=>{const svg=document.querySelector('#cross-section'),all=[...svg.children];return {regions:[...svg.querySelectorAll('polygon[data-region]')].map(p=>({name:p.dataset.region,points:Array.from(p.points,v=>[v.x,v.y]),order:all.indexOf(p)})),traces:[...svg.querySelectorAll('polygon[data-trace]')].map(p=>({name:p.dataset.trace,points:Array.from(p.points,v=>[v.x,v.y]),order:all.indexOf(p)})),labels:[...svg.querySelectorAll('[data-geometry-label],[data-region-label]')].map(p=>{const b=p.getBBox();return {text:p.textContent,x:b.x,y:b.y,width:b.width,height:b.height}}),view:[svg.viewBox.baseVal.width,svg.viewBox.baseVal.height]}})()`);
    const h=doc.layers.reduce((a,l)=>a+l.thickness,0),w=doc.box.width;
    function points(actual,raw){assert.equal(actual.length,raw.length);for(let i=0;i<raw.length;i++){assert.ok(Math.abs(actual[i][0]-(65+(raw[i][0]/w+.5)*630))<1e-4);assert.ok(Math.abs(actual[i][1]-(245-raw[i][1]/h*210))<1e-4);}}
    assert.equal(actual.regions.length,(doc.dielectric_regions??[]).length);
    for(const region of doc.dielectric_regions??[]){const p=actual.regions.find(p=>p.name===region.name);assert.ok(p);points(p.points,region.vertices);}
    for(const trace of doc.traces){
      if(trace.kind==='polygon'){const p=actual.traces.find(p=>p.name===trace.name);assert.ok(p);points(p.points,trace.vertices);}
    }
    for(const region of actual.regions)for(const trace of actual.traces)assert.ok(region.order<trace.order,'local dielectric must be below metal');
    for(let i=0;i<actual.labels.length;i++){
      const a=actual.labels[i];assert.ok(a.x>=0&&a.y>=0&&a.x+a.width<=actual.view[0]&&a.y+a.height<=actual.view[1],JSON.stringify(a));
      for(const b of actual.labels.slice(i+1))assert.ok(!(a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height),JSON.stringify([a,b]));
    }
    return actual;
  }
  for(const [name,doc] of Object.entries(fixtures)){
    for(const unit of ['mm','µm','mil']){
      await choose('microstrip');await cdp.evaluate(`document.querySelector('#unit').value=${JSON.stringify(unit)};document.querySelector('#unit').dispatchEvent(new Event('change'))`);
      await open(doc);assert.equal(await cdp.evaluate('document.querySelector("#inputs").hidden'),true);
      assert.equal(await cdp.evaluate('document.querySelector("#design").disabled&&document.querySelector("#save-editable").disabled'),true);
      drawingChecks.push({name,unit,...await inspect(doc)});assert.deepEqual(await save('save','sipi-cross-section.json'),doc);
    }
    if(name!=='clockwise'){
      await click('calculate');results[name]=await cdp.evaluate('window.completedResults.at(-1)');assert.deepEqual(results[name].document,doc);
      if(name==='asymmetric-pair'){
        assert.ok(results[name].line.scalar_summary_unavailable);
        assert.equal(await cdp.evaluate('document.querySelector("#scalar-summary").hidden'),true);
      }
      for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
      await click('network-calculate');const net=results[name+'-network']=await cdp.evaluate('window.completedResults.at(-1)');
      assert.equal(net.network.extension,name==='asymmetric-pair'?'s4p':'s2p');
      const file='sipi-line.'+net.network.extension;await rm(join(downloads,file),{force:true});await click('touchstone-save');
      const raw=await until(async()=>{try{return await readFile(join(downloads,file),'utf8')}catch{}},'polygon network export');
      assert.equal(raw,net.network.touchstone);await writeFile(join(output,name+'.'+net.network.extension),raw);
    }
  }
  // Refusal must preserve an already completed result, not merely an empty form.
  const original=fixtures['normal-film'];await open(original);await click('calculate');
  const snapshot=await cdp.evaluate('({drawing:document.querySelector("#cross-section").outerHTML,z:document.querySelector("#z-value").textContent,hidden:document.querySelector("#result").hidden})');
  const invalid=structuredClone(original);invalid.dielectric_regions[0].vertices[0][0]=-.1;
  const complex=structuredClone(original);complex.layers=Array.from({length:65},(_,i)=>({name:'layer'+i,thickness:.005/65,eps_r:4,tan_delta:0}));
  for(const value of [invalid,complex,JSON.stringify(original).replace('"schema":','"schema":"duplicate","schema":')]){
    await open(value,'#file',true);const now=await cdp.evaluate('({drawing:document.querySelector("#cross-section").outerHTML,z:document.querySelector("#z-value").textContent,hidden:document.querySelector("#result").hidden})');assert.deepEqual(now,snapshot);
    assert.deepEqual(await save('save','sipi-cross-section.json',true),original);
  }
  // A delayed file read must not replace the current result after cancellation.
  await cdp.evaluate(`window.originalPolygonText=File.prototype.text;File.prototype.text=function(){return new Promise(resolve=>{window.releasePolygonText=()=>resolve(${JSON.stringify(JSON.stringify(fixtures.concave))})})}`);
  const delayed=join(profile,'delayed polygon.json');await writeFile(delayed,JSON.stringify(fixtures.concave));
  const delayedRoot=await cdp.call('DOM.getDocument');const delayedInput=await cdp.call('DOM.querySelector',{nodeId:delayedRoot.root.nodeId,selector:'#file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:delayedInput.nodeId,files:[delayed]});await until(()=>cdp.evaluate('typeof window.releasePolygonText==="function"'),'pending file read');
  await cdp.evaluate('document.querySelector("#cancel").click()');await ready();
  await cdp.evaluate('window.releasePolygonText();File.prototype.text=window.originalPolygonText');await pause(300);
  assert.deepEqual(await cdp.evaluate('({drawing:document.querySelector("#cross-section").outerHTML,z:document.querySelector("#z-value").textContent,hidden:document.querySelector("#result").hidden})'),snapshot);
  assert.deepEqual(await save('save','sipi-cross-section.json'),original);
  const named=structuredClone(original);named.dielectric_regions[0].name='<script>window.polygonInjected=true</script>';
  await open(named);assert.equal(await cdp.evaluate('window.polygonInjected??false'),false);assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section script").length'),0);
  assert.ok(await cdp.evaluate('document.querySelector("[data-region-label]").textContent.includes("<script>")'));
  await open(original);
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');
  await click('calculate');assert.deepEqual(await save('save','sipi-cross-section.json'),original);
  // All supported editable choices still draw, with layer labels separated.
  const names=await cdp.evaluate('[...document.querySelectorAll("[data-template]")].map(b=>b.dataset.template)');assert.equal(names.length,17);
  await cdp.evaluate(`document.querySelector('#unit').value='mm';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
  for(const name of names){await choose(name);await set('profile','rectangular');await set('thickness','0');await set('width','.5');await set('height','1');await set('coating_height','.2');if(name.includes('conformal_'))await click('geometry-inspect');
    const labels=await cdp.evaluate('[...document.querySelectorAll("#cross-section [data-geometry-label]")].map(p=>{const b=p.getBBox();return {x:b.x,y:b.y,w:b.width,h:b.height}})');assert.ok(labels.length>=2,name);
    for(let i=0;i<labels.length;i++)for(const b of labels.slice(i+1)){const a=labels[i];assert.ok(!(a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h),name);}
  }
  for(const [name,doc] of [['concave',fixtures.concave],['normal-film',original]]){
    await open(doc);
    for(const width of [1400,768,390,320]){
      await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#cross-section").scrollIntoView({block:"center"})');
      const layout=await cdp.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})');assert.ok(layout.scrollWidth<=width);layouts.push({name,...layout});await inspect(doc);
      await writeFile(join(output,`${name}-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    }
  }
  // New geometry still cannot silently replace an editable project.
  await choose('microstrip');await click('project-save');await open(original,'#file',true);assert.equal(await cdp.evaluate('document.querySelector("#inputs").hidden'),false);
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'results.json'),JSON.stringify(results,null,2));
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',actions,drawingChecks,editableForms:names.length,layouts,errors,externalRequests:remoteRequests,checks:['v3 validation before replacement','concave and clockwise vertices','region below metal and exact coordinates','four geometry inputs across three prior display units','read-only exact geometry export','scalar/asymmetric matrices and two/four-port export','invalid/duplicate/complexity input preserves prior result','late file cancellation preserves previous result','safe literal material names','cancel/restart','all17 form layer labels separated','four viewports','project preservation','shutdown']},null,2));
  console.log('Polygon import and geometry display acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
