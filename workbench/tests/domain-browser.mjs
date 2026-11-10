// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-domain-browser');
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
  const forms=['microstrip','stripline','coupled_microstrip','coupled_stripline','grounded_coplanar','coupled_grounded_coplanar','coated_microstrip'];
  const inspected=[];
  for(const form of forms) {
    await choose(form);await click('domain-inspect');const doc=await save();
    assert.equal(await cdp.evaluate('document.querySelector("#air-domain-fields").hidden'),['stripline','coupled_stripline'].includes(form));
    assert.equal(await cdp.evaluate('document.querySelector("#mesh-mode").textContent'),'Automatic mesh');
    const sent=await cdp.evaluate('window.domainRequests.at(-1)');
    assert.equal(Object.hasOwn(sent.parameters,'box_width'),false);assert.equal(Object.hasOwn(sent.parameters,'air_height'),false);
    assert.equal(doc.parameters.box_width,null);
    if(!['stripline','coupled_stripline'].includes(form))assert.equal(doc.parameters.air_height,null);
    const width=await cdp.evaluate('document.querySelector("[data-domain-key=width]").textContent');
    assert.equal(width,`${Number((doc.cross_section.box.width*1e3).toPrecision(10))} mm`);
    inspected.push({form,width:doc.cross_section.box.width,total_height:doc.cross_section.layers.reduce((sum,l)=>sum+l.thickness,0)});
  }
  await choose('coupled_grounded_coplanar');
  for(const [id,value] of [['profile','rectangular'],['width','.5'],['height','.5'],['gap','.3'],['ground_gap','.2'],['ground_width','1'],['thickness','0'],['eps_r','1'],['tan_delta','0']])await set(id,value);
  await click('domain-inspect');const automatic=await save();
  await click('calculate');const originalZ=await cdp.evaluate('document.querySelector("#z-value").textContent');
  await click('domain-inspect');assert.equal(await cdp.evaluate('document.querySelector("#z-value").textContent'),originalZ);
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#mesh-mode").textContent'),'Automatic mesh');
  // An existing saved explicit mesh stays fixed as only outer dimensions change.
  const fixed=structuredClone(automatic);fixed.cross_section.mesh={edge_size:2e-6,far_size:.000125,grade:.15,min_angle:28};
  await open(fixed);await set('box_mode','fixed');
  assert.equal(await cdp.evaluate('Number(document.querySelector("#box_width").value)'),automatic.cross_section.box.width*1e3);
  await set('box_width','12.00000000012345');await set('air_mode','fixed');await set('air_height','6.00000000012345');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const manual=await save();assert.deepEqual(manual.cross_section.mesh,fixed.cross_section.mesh);
  assert.equal(manual.parameters.box_width,12.00000000012345*1e-3);assert.equal(manual.parameters.air_height,6.00000000012345*1e-3);
  for(const unit of ['mil','mm']) {
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.deepEqual(await save(),manual);
  }
  await click('domain-inspect');await click('calculate');
  const nominalZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(nominalZ/172.45677879183611-1)<.02,'Independent zero-thickness vacuum panel reference');
  await click('domain-inspect');assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  await set('box_width','24');await set('air_height','12');await click('calculate');
  const wideZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(wideZ/nominalZ-1)<.01,'Separate finite-domain enlargement gate');
  const wide=await save();assert.deepEqual(wide.cross_section.mesh,fixed.cross_section.mesh);
  assert.equal(wide.cross_section.box.width,.024);assert.equal(wide.cross_section.layers.at(-1).thickness,.012);
  await set('project-label','Wide domain A');const projectA=await save('project-save','sipi-project.json');
  const idA=await cdp.evaluate('document.querySelector("#project-design").value');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Narrow domain B');await set('box_width','12.00000000012345');await set('air_height','6.00000000012345');
  const projectB=await save('project-save','sipi-project.json'),rawProject=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await open(rawProject,'#project-file');assert.deepEqual(await save(),wide);
  await switchDesign(idB);assert.deepEqual(await save(),manual);
  assert.equal(JSON.parse(projectA.designs.find(d=>d.design_id===idA).source_text).parameters.box_width,.024);
  assert.deepEqual(JSON.parse(projectB.designs.find(d=>d.design_id===idB).source_text),manual);
  await set('box_mode','auto');await set('air_mode','auto');const reset=await save();
  assert.equal(reset.parameters.box_width,null);assert.equal(reset.parameters.air_height,null);
  assert.equal(reset.cross_section.box.width,automatic.cross_section.box.width);
  assert.deepEqual(reset.cross_section.mesh,fixed.cross_section.mesh);
  await open(reset);assert.equal(await cdp.evaluate('document.querySelector("#box_mode").value'),'auto');
  assert.equal(await cdp.evaluate('document.querySelector("#air_mode").value'),'auto');
  await set('box_mode','fixed');await set('box_width','-1');
  const beforeInvalid=await cdp.evaluate('window.domainRequests.length');await click('domain-inspect',true);
  assert.equal(await cdp.evaluate('window.domainRequests.length'),beforeInvalid);
  await set('box_width','.01');await click('domain-inspect',true);
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await set('box_width','12');await set('air_mode','fixed');await set('air_height','6');await click('domain-inspect');
  const layouts=[];
  for(const width of [1400,768,390,320]) {
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['box_mode','box_width','air_mode','air_height','domain-inspect'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width);for(const c of layout.controls)assert.ok(c.height>=44 && c.left>=0 && c.right<=width,JSON.stringify(c));
    layouts.push(layout);await cdp.evaluate('document.querySelector("#domain-settings").scrollIntoView({block:"center"})');
    await writeFile(join(output,`domain-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  await set('air_height','-1');await choose('stripline');const buried=await save();
  assert.equal(Object.hasOwn(buried.parameters,'air_height'),false);
  // A fresh workspace can inspect raw geometry but must not expose editable bounds.
  await cdp.call('Page.navigate',{url:'about:blank'});await until(()=>cdp.evaluate('location.href === "about:blank"'),'blank document');
  await cdp.call('Page.navigate',{url});await until(()=>cdp.evaluate('!!document.querySelector("#cross-section rect")'),'fresh workspace');
  await cdp.evaluate('document.querySelector("#domain-settings").open=true');await open(manual.cross_section);
  assert.equal(await cdp.evaluate('document.querySelector("#domain-inputs").hidden'),true);
  await click('domain-inspect');assert.ok(await cdp.evaluate('document.querySelector("#domain-mode").textContent.includes("read only")'));
  assert.equal(await cdp.evaluate('document.querySelector("[data-domain-key=air]").textContent'),'—');
  await cdp.evaluate('document.querySelector("#domain-inspect").click();document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel inspection');
  await click('domain-inspect');
  await writeFile(join(output,'domain-project.json'),rawProject);
  await writeFile(join(output,'manual-design.json'),JSON.stringify(manual,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');
  if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',inspected,nominal_z_diff:nominalZ,wide_z_diff:wideZ,explicit_mesh:fixed.cross_section.mesh,layouts,errors,externalRequests:remoteRequests,checks:['seven-form inspection does not solve/fix mesh','explicit precise domain mm/mil roundtrip','independent vacuum panel and domain enlargement','fixed mesh retained','exact raw A/B reopen','null automatic reset','invalid box refusal/recovery','inactive stripline air omitted','imported bounds read-only','cancel/restart','44px controls/four viewports','normal shutdown']},null,2));
  console.log('Domain controls acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
