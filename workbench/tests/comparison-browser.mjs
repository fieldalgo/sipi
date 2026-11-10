// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-comparison-browser');
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
  await cdp.evaluate(`document.querySelector('#domain-settings').open=true;
    window.domainRequests=[];
    const post=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(message,...rest){if(message.input)window.domainRequests.push(message.input);return post.call(this,message,...rest)};
    const fetchOriginal=window.fetch;
    window.fetch=(url,options)=>{if(url==='/api/job' && options?.method==='POST')window.domainRequests.push(JSON.parse(options.body));return fetchOriginal(url,options)};`);
  async function ready() { await until(()=>cdp.evaluate('!document.querySelector("#domain-inspect").disabled'),'domain action complete',180000); }
  async function click(id, expectError=false) {
    await cdp.evaluate(`document.getElementById('${id}').click()`);await ready();
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

  await cdp.evaluate(`window.comparisonResults=[];
    const originalFetch=window.fetch;
    window.fetch=async (...args)=>{const response=await originalFetch(...args);if(args[0]==='/api/job' && args[1]?.method==='GET') {
      const value=await response.clone().json();if(value.status==='complete' && value.result.line)window.comparisonResults.push(value.result);
    }return response;};
    const originalPost=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(...args){if(!this.comparisonObserved){this.comparisonObserved=true;this.addEventListener('message',event=>{if(event.data.status==='complete' && event.data.result.line)window.comparisonResults.push(event.data.result)})}return originalPost.apply(this,args)};`);
  const current=()=>cdp.evaluate('window.comparisonResults.at(-1)');
  const rows=()=>cdp.evaluate(`Object.fromEntries([...document.querySelectorAll('#comparison-rows tr')].map(row=>[row.dataset.comparisonKey,[...row.cells].slice(1).map(cell=>cell.textContent==='—'?null:Number(cell.textContent))]))`);
  const inputDetails=()=>cdp.evaluate('JSON.parse(document.querySelector("#comparison-inputs").textContent)');
  const hidden=()=>cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden');
  const close=(a,b)=>assert.ok(Math.abs(a-b)<=1e-6*Math.max(1,Math.abs(b)),`${a} != ${b}`);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-pin").disabled'),true);
  await choose('coupled_grounded_coplanar');
  for(const [id,value] of [['profile','rectangular'],['width','.5'],['height','.5'],['gap','.3'],['ground_gap','.2'],['ground_width','1'],['thickness','0'],['eps_r','1'],['tan_delta','0'],['box_mode','fixed'],['box_width','12'],['air_mode','fixed'],['air_height','6']])await set(id,value);
  const fixed=await save();fixed.cross_section.mesh={edge_size:2e-6,far_size:.000125,grade:.15,min_angle:28};await open(fixed);
  await click('calculate');const nominal=await current();assert.ok(Math.abs(nominal.line.z_diff/172.45677879183611-1)<.02,'Independent zero-thickness vacuum panel');
  await click('comparison-pin');const baseline=(await inputDetails()).baseline;
  assert.deepEqual(baseline.document,nominal.document);
  const same=await rows();assert.equal(Object.keys(same).length,18);for(const values of Object.values(same))assert.equal(values[2],0);
  assert.equal(same['G_1GHz:0:0'][3],null);
  await set('box_width','24');await set('air_height','12');assert.equal(await hidden(),true);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-pin").disabled'),true);
  assert.deepEqual((await inputDetails()).baseline,baseline);assert.equal((await inputDetails()).current,null);
  await click('calculate');const wide=await current();assert.ok(Math.abs(wide.line.z_diff/nominal.line.z_diff-1)<.01,'Separate outer-domain enlargement');
  let table=await rows();close(table.z_diff[0],nominal.line.z_diff);close(table.z_diff[1],wide.line.z_diff);close(table.z_diff[2],wide.line.z_diff-nominal.line.z_diff);
  close(table['C:0:1'][2],(wide.line.C[0][1]-nominal.line.C[0][1])*1e12);
  close(table['C:0:1'][3],100*(wide.line.C[0][1]-nominal.line.C[0][1])/Math.abs(nominal.line.C[0][1]));
  assert.deepEqual((await inputDetails()).baseline,baseline);assert.deepEqual((await inputDetails()).current.document,wide.document);
  await click('domain-inspect');assert.deepEqual(await rows(),table);
  await click('mesh-refine');assert.equal(await hidden(),true);assert.deepEqual((await inputDetails()).baseline,baseline);
  await click('calculate');const fine=await current();assert.ok(Math.abs(fine.line.z_diff/wide.line.z_diff-1)<.01,'Separate mesh refinement');
  assert.equal(fine.document.mesh.edge_size,1e-6);assert.equal(fine.document.mesh.far_size,62.5e-6);assert.equal(fine.document.mesh.grade,.075);
  table=await rows();close(table.z_diff[2],fine.line.z_diff-nominal.line.z_diff);
  assert.deepEqual((await inputDetails()).baseline.document.mesh,fixed.cross_section.mesh);
  for(const unit of ['mil','mm']) {
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.deepEqual(await rows(),table);assert.deepEqual((await inputDetails()).baseline,baseline);
  }
  await set('box_width','.01');await click('calculate',true);assert.equal(await hidden(),true);assert.deepEqual((await inputDetails()).baseline,baseline);
  await set('box_width','24');
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel solve');
  assert.equal(await hidden(),true);assert.deepEqual((await inputDetails()).baseline,baseline);
  await click('calculate');assert.equal(await hidden(),false);
  await choose('microstrip');await click('calculate');assert.equal(await hidden(),true);
  assert.ok(await cdp.evaluate('document.querySelector("#comparison-status").textContent.includes("same ordered names")'));
  await click('comparison-clear');assert.equal(await cdp.evaluate('document.querySelector("#comparison-details").hidden'),true);
  await click('comparison-pin');const single=await current(),scalarBaseline=(await inputDetails()).baseline;
  assert.equal(Object.keys(await rows()).length,6);
  await set('width','.7');await click('calculate');const changed=await current();table=await rows();
  close(table.z0[2],changed.line.z0-single.line.z0);assert.notEqual(table.z0[2],0);assert.deepEqual((await inputDetails()).baseline,scalarBaseline);
  const project=await save('project-save','sipi-project.json');assert.equal(Object.hasOwn(project,'baseline'),false);
  assert.ok(project.designs.every(design=>design.records.length===0));assert.deepEqual((await inputDetails()).baseline,scalarBaseline);
  await writeFile(join(output,'results.json'),JSON.stringify({nominal,wide,fine,single,changed},null,2));
  const layouts=[];
  for(const width of [1400,768,390,320]) {
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    await cdp.evaluate('document.querySelector(".comparison").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['comparison-pin','comparison-clear'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    await writeFile(join(output,`layout-${width}.json`),JSON.stringify(layout,null,2));
    await writeFile(join(output,`comparison-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44 && control.left>=0 && control.right<=width,JSON.stringify(control));
    layouts.push(layout);await writeFile(join(output,`comparison-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  await cdp.call('Page.navigate',{url:'about:blank'});await until(()=>cdp.evaluate('location.href === "about:blank"'),'blank document');
  await cdp.call('Page.navigate',{url});await until(()=>cdp.evaluate('!!document.querySelector("#cross-section rect")'),'fresh workspace');
  assert.equal(await hidden(),true);assert.equal(await cdp.evaluate('document.querySelector("#comparison-clear").disabled'),true);
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');
  if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',nominal_z_diff:nominal.line.z_diff,wide_z_diff:wide.line.z_diff,fine_z_diff:fine.line.z_diff,layouts,errors,externalRequests:remoteRequests,checks:['qualified vacuum panel/domain/mesh gates','explicit immutable baseline snapshot','current minus baseline from actual full-precision solver outputs','zero G percentage unavailable','precise raw document/mesh retained','unit invariance','failed/cancelled result invalidation and recovery','signal-count mismatch refusal','scalar result comparison','input project does not persist session baseline','four viewports/44px controls','reload clears baseline','normal shutdown']},null,2));
  console.log('Result comparison acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
