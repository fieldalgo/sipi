// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-unit-browser');
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

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/editable_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const fixtures=JSON.parse(fixtureRun.stdout);
  assert.equal(fixtures.cases.length,11);
  assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),19);
  async function changeUnit(unit) {await cdp.evaluate(`document.querySelector('#unit').value=${JSON.stringify(unit)};document.querySelector('#unit').dispatchEvent(new Event('change'))`);}
  for(const input of fixtures.cases) {
    await open(input);
    for(const unit of ['µm','mil','µm','mm']) {await changeUnit(unit);assert.deepEqual(await save(),input);}
  }
  await choose('offset_stripline');
  for(const [id,value] of [['profile','rectangular'],['width','.3000000000123456'],['height','1'],['trace_height','.3'],['thickness','0'],['eps_r','4'],['tan_delta','0'],['box_mode','fixed'],['box_width','6'],['lower','.2000000000123456'],['upper','.4000000000234567'],['target','58.69'],['tolerance','.5'],['study-mode','corners'],['study-count','2'],['study-variable-1','width'],['study-low-1','.10164400000000001'],['study-high-1','.3200000000234567'],['study-variable-2','eps_r'],['study-low-2','3.8123456789012345'],['study-high-2','4.2123456789012345']])await set(id,value);
  await cdp.evaluate(`(()=>{window.precisionRequests=[];window.probeOnly=true;
    function capture(input){if(!input)return false;window.precisionRequests.push(structuredClone(input));return window.probeOnly&&['design','study','analyze','network'].includes(input.action)};
    const post=Worker.prototype.postMessage;Worker.prototype.postMessage=function(message,...rest){if(capture(message.input)){queueMicrotask(()=>this.dispatchEvent(new MessageEvent('message',{data:{id:message.id,status:'error',message:'Captured before calculation'}})));return;}return post.call(this,message,...rest)};
    const originalFetch=window.fetch;window.fetch=(url,options)=>{if(url==='/api/job'&&options?.method==='POST'&&capture(JSON.parse(options.body)))return Promise.resolve(new Response(JSON.stringify({message:'Captured before calculation'}),{status:400}));return originalFetch(url,options)};})();`);
  async function captured(id,action) {await click(id,true);return cdp.evaluate(`window.precisionRequests.filter(x=>x.action===${JSON.stringify(action)}).at(-1)`);}
  const goal=await captured('design','design'), study=await captured('study-calculate','study'),cycles=[];
  for(const unit of ['µm','mil','mm','mil','µm','mm']) {
    await changeUnit(unit);const g=await captured('design','design'),t=await captured('study-calculate','study');
    assert.deepEqual(g,goal);assert.deepEqual(t,study);cycles.push({unit,goal:g,study:t});
  }
  // Updating one bound cannot round the other bound from its displayed value.
  await changeUnit('µm');await set('lower','200.12345678912346');const editedGoal=await captured('design','design');
  assert.equal(editedGoal.design.bounds[0],200.12345678912346*1e-6);assert.equal(editedGoal.design.bounds[1],goal.design.bounds[1]);
  await set('study-low-1','101.64400000000001');const editedStudy=await captured('study-calculate','study');
  assert.equal(editedStudy.study.variables[0].lower,101.64400000000001*1e-6);
  assert.equal(editedStudy.study.variables[0].upper,study.study.variables[0].upper);assert.deepEqual(editedStudy.study.variables[1],study.study.variables[1]);
  await changeUnit('mil');assert.deepEqual(await captured('design','design'),editedGoal);assert.deepEqual(await captured('study-calculate','study'),editedStudy);
  // A variable reset derives physical bounds from SI, independent of display units.
  await set('study-variable-1','thickness');const zeroBounds=await captured('study-calculate','study');
  assert.equal(zeroBounds.study.variables[0].lower,0);assert.equal(zeroBounds.study.variables[0].upper,.05*1e-3);
  await set('study-variable-1','trace_height');const heightBounds=await captured('study-calculate','study');
  assert.equal(heightBounds.study.variables[0].lower,.0003*.9);assert.equal(heightBounds.study.variables[0].upper,.0003*1.1);
  await changeUnit('µm');assert.deepEqual(await captured('study-calculate','study'),heightBounds);
  // Empty zero-allowed thickness and study inputs remain invalid on unit changes.
  await set('thickness','');let count=await cdp.evaluate('window.precisionRequests.length');await click('calculate',true);
  for(const unit of ['mil','mm','µm']) {await changeUnit(unit);await click('calculate',true);}
  assert.equal(await cdp.evaluate('window.precisionRequests.length'),count);assert.equal(await cdp.evaluate('document.querySelector("#thickness").value'),'');
  await set('thickness','0');assert.equal((await captured('calculate','analyze')).parameters.thickness,0);
  await set('study-low-1','');count=await cdp.evaluate('window.precisionRequests.length');
  for(const unit of ['mil','mm','µm']) {await changeUnit(unit);await click('study-calculate',true);}
  assert.equal(await cdp.evaluate('window.precisionRequests.length'),count);
  const net=await captured('network-calculate','network');assert.equal(net.network.length,.1);
  const precision=await cdp.evaluate('window.precisionRequests');
  await cdp.evaluate('window.probeOnly=false');
  // Real calculation at the qualified plane-reference section, entered in µm.
  for(const [id,value] of [['width','300'],['height','1000'],['trace_height','300'],['thickness','0'],['box_width','6000'],['lower','200'],['upper','400'],['target','58.690493536233184'],['tolerance','.5']])await set(id,value);
  const fixed=await save();fixed.cross_section.mesh={edge_size:2.5e-6,far_size:.0000625,grade:.075,min_angle:28};await open(fixed);
  await click('calculate');const z=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');assert.ok(Math.abs(z/58.690493536233184-1)<.02);
  await changeUnit('mil');assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);assert.deepEqual(await save(),fixed);await changeUnit('µm');
  await click('design');assert.ok(await cdp.evaluate('document.querySelector("#refinement").textContent.includes("Both meet")'));
  const designed=await save();assert.deepEqual(designed.cross_section.mesh,fixed.cross_section.mesh);assert.equal(designed.parameters.trace_height,fixed.parameters.trace_height);
  for(const [id,value] of [['study-mode','sweep'],['study-variable-1','width'],['study-low-1','280'],['study-high-1','320'],['study-points','2']])await set(id,value);
  await click('study-calculate');const widthStudy=await save('study-save','sipi-parameter-study.json');
  assert.equal(widthStudy.failed,0);assert.deepEqual(widthStudy.settings.variables,[{parameter:'width',lower:280*1e-6,upper:320*1e-6}]);
  await changeUnit('mil');assert.deepEqual(await save('study-save','sipi-parameter-study.json'),widthStudy);
  for(const [id,value] of [['study-variable-1','eps_r'],['study-low-1','3.8'],['study-high-1','4.2']])await set(id,value);
  await changeUnit('µm');await click('study-calculate');const dielectricStudy=await save('study-save','sipi-parameter-study.json');
  assert.equal(dielectricStudy.failed,0);assert.deepEqual(dielectricStudy.settings.variables,[{parameter:'eps_r',lower:3.8,upper:4.2}]);
  const scaled=dielectricStudy.rows.map(row=>row.impedance*Math.sqrt(row.parameters.eps_r));assert.ok(Math.abs(scaled[0]/scaled[1]-1)<2e-9);
  await set('project-label','Micrometre A');await save('project-save','sipi-project.json');await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Micrometre B');await set('width','450.1234567891234');const b=await save();await save('project-save','sipi-project.json');const project=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await open(project,'#project-file');assert.deepEqual(await save(),designed);await switchDesign(idB);assert.deepEqual(await save(),b);
  assert.equal(await cdp.evaluate('document.querySelector("#drawing-unit").textContent'),'µm');
  const layouts=[];
  for(const width of [1400,768,390,320]) {
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#unit").scrollIntoView({block:"center"})');
    const row=await cdp.evaluate('(()=>{const r=document.querySelector("#unit").getBoundingClientRect();return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,left:r.left,right:r.right,height:r.height}})()');
    await writeFile(join(output,`units-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
    assert.ok(row.scrollWidth<=width&&row.height>=44&&row.left>=0&&row.right<=width);layouts.push(row);
  }
  for(const [name,data] of [['precision-requests',precision],['cycles',cycles],['width-study',widthStudy],['dielectric-study',dielectricStudy],['design',designed]])await writeFile(join(output,name+'.json'),JSON.stringify(data,null,2));
  await writeFile(join(output,'project.json'),project);
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');
  if(!webRoot)await until(()=>server.exitCode===0,'host exit');assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',editableForms:11,nominal_z0:z,layouts,errors,externalRequests:remoteRequests,checks:['eleven exact inputs through mm/µm/mil','exact goal and length/material study bounds through repeated display changes','one-sided edits preserve opposite bound','variable reset physical SI','blank thickness/study bounds stay invalid','network length stays explicit mm','real micrometre target requested/refined gates','real width and dimensionless TEM studies','raw A/B project resume','four viewports and44px unit control','normal shutdown']},null,2));
  console.log('Display-unit precision acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
