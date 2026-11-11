// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-coated-coplanar-browser');
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

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/editable_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const fixtures=JSON.parse(fixtureRun.stdout);
  assert.equal(fixtures.cases.length,11);assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),28);
  for(const input of fixtures.cases){await open(input);for(const unit of ['µm','mil','mm']){await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.deepEqual(await save(),input);}}
  await choose('microstrip');for(const key of ['coating_height','coating_eps_r','coating_tan_delta'])await set(key,'-1');
  assert.equal(await cdp.evaluate('document.querySelector("#coating-fields").hidden'),true);await save();
  await choose('coated_grounded_coplanar');
  assert.equal(await cdp.evaluate('document.querySelector("#coating-fields").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#gap-field").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#ground-field").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#target-label").textContent.includes("Differential")'),false);
  for(const [id,value] of [['profile','tapered'],['width','.5'],['height','.5'],['gap','.2'],['ground_width','1'],['thickness','.035'],['top_width','.4'],['eps_r','4'],['tan_delta','.01'],['coating_height','.1000000000123456'],['coating_eps_r','3.5'],['coating_tan_delta','.02'],['box_mode','fixed'],['box_width','12'],['air_mode','fixed'],['air_height','6']])await set(id,value);
  const precise=await save();assert.equal(precise.parameters.coating_height,.1000000000123456*1e-3);
  precise.cross_section.mesh={edge_size:4e-6,far_size:.00025,grade:.2,min_angle:28};await open(precise);
  await set('project-label','Coating A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Coating B');await set('coating_eps_r','3.8');const alternative=await save();
  const projectB=await save('project-save','sipi-project.json'),rawProject=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await open(rawProject,'#project-file');assert.deepEqual(await save(),precise);await switchDesign(idB);assert.deepEqual(await save(),alternative);
  assert.equal(projectA.designs.length,1);assert.equal(projectB.designs.length,2);
  await open(precise);await click('calculate');const physicalZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(physicalZ/52.95103754-1)<.005);
  await click('comparison-pin');await set('coating_eps_r','1');await set('coating_tan_delta','0');await click('calculate');
  const airZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');assert.ok(airZ>physicalZ);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  await open(precise);
  for(const [id,value] of [['study-mode','corners'],['study-count','2'],['study-variable-1','coating_height'],['study-low-1','.09'],['study-high-1','.11'],['study-variable-2','coating_eps_r'],['study-low-2','3.2'],['study-high-2','3.8']])await set(id,value);
  await click('study-calculate');const study=await save('study-save','sipi-parameter-study.json');
  assert.equal(study.quantity,'z0');assert.equal(study.failed,0);assert.equal(study.rows.length,4);
  for(const row of study.rows){assert.equal(row.document.layers[1].thickness,row.parameters.coating_height);assert.equal(row.document.layers[1].eps_r,row.parameters.coating_eps_r);assert.deepEqual(row.document.mesh,precise.cross_section.mesh);assert.equal(row.impedance,row.line.z0);}
  for(const [id,value] of [['study-mode','sweep'],['study-variable-1','ground_width'],['study-low-1','.8'],['study-high-1','1.2'],['study-points','2']])await set(id,value);
  await click('study-calculate');const groundStudy=await save('study-save','sipi-parameter-study.json');
  assert.equal(groundStudy.quantity,'z0');assert.equal(groundStudy.failed,0);assert.equal(groundStudy.rows.length,2);
  for(const row of groundStudy.rows){const signal=row.document.traces.find(t=>!t.ground),grounds=row.document.traces.filter(t=>t.ground);assert.equal(grounds.length,2);for(const t of grounds){assert.equal(t.width,row.parameters.ground_width);assert.equal(t.top_width,t.width);assert.ok(Math.abs(Math.abs(t.x)-t.width/2-signal.width/2-.0002)<1e-15);}}
  await set('study-low-1','0');await click('study-calculate',true);
  await set('study-variable-1','coating_height');await set('study-high-1','.11');
  await set('study-low-1','.03');await click('study-calculate',true);
  await set('coating_height','.035');await click('calculate',true);assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await set('coating_height','');await cdp.evaluate(`document.querySelector('#unit').value='µm';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.equal(await cdp.evaluate('document.querySelector("#coating_height").value'),'');await click('calculate',true);
  await cdp.evaluate(`document.querySelector('#unit').value='mm';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
  await open(precise);
  // Qualified thin vacuum geometry; layer interface remains present with eps=1.
  for(const [id,value] of [['profile','rectangular'],['thickness','0'],['eps_r','1'],['tan_delta','0'],['coating_height','.1'],['coating_eps_r','1'],['coating_tan_delta','0'],['box_width','24'],['air_height','12']])await set(id,value);
  const vacuum=await save();vacuum.cross_section.mesh={edge_size:1e-6,far_size:.00025,grade:.1,min_angle:28};await open(vacuum);
  await click('calculate');const vacuumZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(vacuumZ/100.39046647904753-1)<.02);
  for(const [id,value] of [['lower','.4'],['upper','.6'],['target','100.39046647904753'],['tolerance','1']])await set(id,value);
  await click('design');const designed=await save();assert.equal(designed.template,'coated_grounded_coplanar');
  assert.ok(Math.abs(designed.parameters.width/.0005-1)<.04);assert.deepEqual(designed.cross_section.mesh,vacuum.cross_section.mesh);
  for(const key of ['coating_height','coating_eps_r','coating_tan_delta','gap','ground_width'])assert.equal(designed.parameters[key],vacuum.parameters[key]);
  assert.ok(await cdp.evaluate('document.querySelector("#refinement").textContent.includes("Both meet")'));
  await open(precise);
  for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
  await click('network-calculate');assert.equal(await cdp.evaluate('document.querySelector("#crosstalk-note").hidden'),true);
  assert.ok(await cdp.evaluate('document.querySelector("#network-description").textContent.includes("S21")'));
  await click('touchstone-save');const touchstone=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s2p'),'utf8')}catch{}},'coated two-port export');
  assert.ok(touchstone.includes('# Hz S RI R 50'));await writeFile(join(output,'coated-line.s2p'),touchstone);
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#coating-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['coating_height','coating_eps_r','coating_tan_delta','gap','ground_width'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44&&control.left>=0&&control.right<=width,JSON.stringify(control));layouts.push(layout);
    await writeFile(join(output,`coated-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  await writeFile(join(output,'coated-project.json'),rawProject);await writeFile(join(output,'coated-design.json'),JSON.stringify(designed,null,2));await writeFile(join(output,'coated-study.json'),JSON.stringify(study,null,2));await writeFile(join(output,'ground-study.json'),JSON.stringify(groundStudy,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',actions,editableForms:11,physical_z0:physicalZ,air_z0:airZ,vacuum_z0:vacuumZ,layouts,errors,externalRequests:remoteRequests,checks:['eleven exact forms and mm/µm/mil','coating/gap controls and inactive-field isolation','finite tapered physical/reference agreement','coating air limit ordering','coating height/eps corners with fixed mesh','clearance bounds and blank coating rejection','independent vacuum target and both mesh gates','two-port Touchstone response','raw A/B reopen','cancel/restart','four viewports/44px controls','normal shutdown']},null,2));
  console.log('Planar coated coplanar form acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
