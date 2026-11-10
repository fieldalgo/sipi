// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-offset-browser');
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
  for(const form of forms) {
    await choose(form);await set('trace_height','-1');
    assert.equal(await cdp.evaluate('document.querySelector("#placement-fields").hidden'),form!=='coupled_stripline');
    const input=await save();assert.equal(Object.hasOwn(await cdp.evaluate('window.domainRequests.at(-1).parameters'),'trace_height'),false);
    if(form==='coupled_stripline')assert.equal(input.parameters.trace_height,null);
    else assert.equal(Object.hasOwn(input.parameters,'trace_height'),false);
  }
  await choose('offset_stripline');
  assert.equal(await cdp.evaluate('document.querySelector("#placement-mode-field").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#trace-height-field").hidden'),false);
  assert.equal(await cdp.evaluate('Number(document.querySelector("#trace_height").value)'),
    await cdp.evaluate('(Number(document.querySelector("#height").value)-Number(document.querySelector("#thickness").value))/2'));
  for(const [id,value] of [['profile','rectangular'],['width','.3'],['height','1'],['thickness','0.035'],['eps_r','4'],['tan_delta','0'],['box_mode','fixed'],['box_width','6']])await set(id,value);
  await set('trace_height','0.3000000000123456');
  const precise=await save();assert.equal(precise.parameters.trace_height,.3000000000123456*1e-3);
  assert.ok(precise.cross_section.traces.every(t=>t.y===precise.parameters.trace_height));
  precise.cross_section.mesh={edge_size:2.5e-6,far_size:.0000625,grade:.075,min_angle:28};await open(precise);
  for(const unit of ['mil','mm']) {
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.deepEqual(await save(),precise);
  }
  await set('height','1.2');await set('thickness','.04');const changed=await save();assert.equal(changed.parameters.trace_height,precise.parameters.trace_height);
  assert.deepEqual(changed.cross_section.mesh,precise.cross_section.mesh);
  await open(precise);await set('project-label','Lower A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Higher B');await set('trace_height','.4');const higher=await save();
  const projectB=await save('project-save','sipi-project.json'),rawProject=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await open(rawProject,'#project-file');assert.deepEqual(await save(),precise);await switchDesign(idB);assert.deepEqual(await save(),higher);
  assert.ok(projectA.designs.length===1 && projectB.designs.length===2);
  // Use the qualified thin uniform single trace for reference/target/reflection checks.
  await set('thickness','0');await set('trace_height','.3');await click('calculate');
  const nominal=await save(), nominalZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(nominalZ/58.690493536233184-1)<.02);
  await click('comparison-pin');await set('trace_height','.7');assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),true);
  await click('calculate');const mirrorZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(mirrorZ/nominalZ-1)<.005);assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  await set('trace_height','.3');
  for(const [id,value] of [['study-mode','sweep'],['study-variable-1','trace_height'],['study-low-1','.28'],['study-high-1','.32'],['study-points','2']])await set(id,value);
  await click('study-calculate');
  const study=await save('study-save','sipi-parameter-study.json');assert.equal(study.rows.length,2);assert.equal(study.failed,0);
  for(const row of study.rows){assert.ok(row.document.traces.every(t=>t.y===row.parameters.trace_height));assert.deepEqual(row.document.mesh,nominal.cross_section.mesh);}
  for(const [id,value] of [['lower','.2'],['upper','.4'],['target','58.690493536233184'],['tolerance','.5']])await set(id,value);
  await click('design');const designed=await save();
  assert.ok(designed.cross_section.traces.every(t=>t.y===.3e-3));assert.deepEqual(designed.cross_section.mesh,nominal.cross_section.mesh);
  assert.ok(await cdp.evaluate('document.querySelector("#refinement").textContent.includes("Both meet")'));
  await set('trace_height','0');await click('calculate',true);assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await set('thickness','.035');await set('trace_height','.99');await click('calculate',true);
  await choose('stripline');const centred=await save();
  assert.equal(centred.template,'stripline');assert.equal(Object.hasOwn(centred.parameters,'trace_height'),false);
  assert.ok(centred.cross_section.traces.every(t=>t.y===(centred.parameters.plane_spacing-centred.parameters.thickness)/2));
  assert.equal(await cdp.evaluate('document.querySelector("#placement-fields").hidden'),true);
  assert.equal(await cdp.evaluate('[...document.querySelector("#study-variable-1").options].some(option=>option.value==="trace_height")'),false);
  await open(designed);assert.deepEqual(await save(),designed);
  for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','0'],['reference-z','50']])await set(id,value);
  await click('network-calculate');assert.equal(await cdp.evaluate('document.querySelector("#crosstalk-note").hidden'),true);
  assert.ok(await cdp.evaluate('document.querySelector("#network-description").textContent.includes("S21")'));
  await click('touchstone-save');const touchstone=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s2p'),'utf8')}catch{}},'single offset two-port export');
  assert.ok(touchstone.includes('# Hz S RI R 50'));await writeFile(join(output,'offset-line.s2p'),touchstone);
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');
  assert.equal(await cdp.evaluate('document.querySelector("#placement-mode-field").hidden'),true);await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]) {
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});
    await cdp.evaluate('document.querySelector("#placement-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['trace_height'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    await writeFile(join(output,`layout-${width}.json`),JSON.stringify(layout,null,2));
    await writeFile(join(output,`offset-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44 && control.left>=0 && control.right<=width,JSON.stringify(control));layouts.push(layout);
  }
  await writeFile(join(output,'offset-project.json'),rawProject);await writeFile(join(output,'offset-design.json'),JSON.stringify(designed,null,2));await writeFile(join(output,'offset-study.json'),JSON.stringify(study,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');
  if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',nominal_z0:nominalZ,mirror_z0:mirrorZ,layouts,errors,externalRequests:remoteRequests,checks:['seven-form inactive control isolation','separate centred single and required fixed offset','precise mm/mil and fixed mesh','spacing/thickness edits retain explicit height','raw A/B resume','qualified independent target and vertical reflection','existing comparison baseline invalidation','height sweep exact geometry/mesh','both goal mesh tolerances','ground-contact refusal','centred single unchanged; explicit single two-port export','cancel/restart','four viewports/44px controls','normal shutdown']},null,2));
  console.log('Offset stripline form acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
