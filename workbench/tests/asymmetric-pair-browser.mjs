// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const buried=process.env.SIPI_ASYMMETRIC_BURIED==='1';const paired=true;
const template=buried?'asymmetric_coupled_stripline':'asymmetric_coupled_microstrip';
const quantity='z_diff_forward',extension=paired?'s4p':'s2p';
const output = resolve(process.argv[2] || '.validation/sipi-normal-coplanar-browser');
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

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/asymmetric_pair_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const precise=JSON.parse(fixtureRun.stdout)[template];
  assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),30);
  const outputs={};
  async function result(key) { const v=await cdp.evaluate('window.completedResults.at(-1)');outputs[key]=v;await writeFile(join(output,key+'.json'),JSON.stringify(v,null,2));return v; }
  function exactGeometry(d) {
    const p=d.parameters,cs=d.cross_section,[a,b]=cs.traces;
    assert.deepEqual(cs.traces.map(t=>t.name),['positive','negative']);
    assert.equal(a.x,-(p.gap+p.right_width)/2);assert.equal(b.x,(p.gap+p.left_width)/2);
    for(const [side,t] of [['left',a],['right',b]]){
      assert.equal(t.width,p[side+'_width']);assert.equal(t.thickness,p[side+'_thickness']);
      assert.equal(t.top_width??t.width,p[side+'_top_width']??p[side+'_width']);
      assert.equal(t.y,buried?(p.plane_spacing-t.thickness)/2:p.substrate_height);
    }
    assert.equal(cs.box.bottom,'ground');assert.equal(cs.box.top,buried?'ground':'open');
    for(const key of ['width','thickness','top_width','trace_height'])assert.equal(Object.hasOwn(p,key),false);
  }
  await choose(template);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section [data-geometry-label=trace]").length'),2);
  for(const id of ['width','thickness','profile','top_width'])assert.equal(await cdp.evaluate(`document.getElementById('${id}').disabled`),true);
  for(const id of ['left_width','right_width','left_thickness','right_thickness','left_profile','right_profile','target_variable'])assert.equal(await cdp.evaluate(`document.getElementById('${id}').disabled`),false);
  const firstInput=await save();exactGeometry(firstInput);await click('calculate');const first=await result('first');
  assert.ok(first.line.z_diff_forward>0);assert.equal(Object.hasOwn(first.line,'z_diff'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#z-label").textContent'),'Forward differential (Ic=0)');
  for(const id of ['eps-metric','delay-metric'])assert.equal(await cdp.evaluate(`document.getElementById('${id}').hidden`),true);
  await cdp.evaluate('document.querySelector("#result").scrollIntoView({block:"center"})');
  await writeFile(join(output,'forward-summary-1400.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await open(precise);
  for(const unit of ['µm','mil','mm']){
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.deepEqual(await save(),precise);
  }
  for(const [id,value] of [['left_width','0'],['right_thickness','-1'],['left_top_width','0'],['height',buried?'.01':'0']]){
    await set(id,value);const before=await cdp.evaluate('window.completedResults.length');await click('calculate',true);
    assert.equal(await cdp.evaluate('window.completedResults.length'),before);await open(precise);
  }
  for(const id of ['width','thickness','top_width'])await set(id,'invalid');assert.deepEqual(await save(),precise);
  const edits=[];
  for(const [id,value] of [['left_width','.44'],['right_width','.73'],['left_thickness','.04'],['right_thickness','.055'],['left_top_width','.3'],['right_top_width','.41'],['gap','.35']]){
    await open(precise);await set(id,value);const d=await save();exactGeometry(d);
    assert.equal(d.parameters[id],Number(value)*1e-3);
    for(const key of Object.keys(precise.parameters))if(key!==id)assert.deepEqual(d.parameters[key],precise.parameters[key]);
    assert.deepEqual(d.cross_section.mesh,precise.cross_section.mesh);edits.push(d);
  }
  for(const side of ['left','right']){
    await open(precise);await set(side+'_profile','rectangular');const d=await save();exactGeometry(d);
    assert.equal(d.parameters[side+'_top_width'],null);
    for(const key of Object.keys(precise.parameters))if(key!==side+'_top_width')assert.deepEqual(d.parameters[key],precise.parameters[key]);
    await set(side+'_thickness','0');const zero=await save();assert.equal(zero.parameters[side+'_thickness'],0);exactGeometry(zero);
  }
  await open(precise);await set('project-label','Unequal A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Unequal B');await set('right_width','.7');await set('left_thickness','.04');const alternative=await save();
  const project=await save('project-save','sipi-project.json');await open(project,'#project-file');
  assert.deepEqual(await save(),precise);await switchDesign(idB);assert.deepEqual(await save(),alternative);
  assert.equal(projectA.designs.length,1);assert.equal(project.designs.length,2);
  await open(precise);await click('calculate');const physical=await result('physical');assert.deepEqual(physical.document,precise.cross_section);
  await click('comparison-pin');await set('box_width',buried?'12':'24');await click('calculate');const outer=await result('outer');
  assert.ok(Math.abs(outer.line[quantity]/physical.line[quantity]-1)<.005);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  if(!buried){await open(precise);await set('air_height','12');await click('calculate');const air=await result('air');assert.ok(Math.abs(air.line[quantity]/physical.line[quantity]-1)<.005);}
  await open(precise);await click('mesh-inspect');await click('mesh-refine');await click('calculate');const fine=await result('fine');
  assert.ok(Math.abs(fine.line[quantity]/physical.line[quantity]-1)<.015);
  await open(precise);
  assert.equal(await cdp.evaluate('document.querySelector("#study-variable-1").value'),'left_width');
  for(const [id,value] of [['study-mode','sweep'],['study-points','2'],['study-variable-1','eps_r']])await set(id,value);
  for(const unit of ['µm','mil','mm']){
    await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
    assert.equal(await cdp.evaluate('Number(document.querySelector("#study-low-1").value)'),3.6);
    assert.equal(await cdp.evaluate('Number(document.querySelector("#study-high-1").value)'),4.4);
  }
  await click('study-calculate');const defaultStudy=await save('study-save','sipi-parameter-study.json');assert.equal(defaultStudy.failed,0);outputs.defaultStudy=defaultStudy;
  for(const [id,value] of [['study-mode','corners'],['study-count','2'],['study-variable-1','left_width'],['study-low-1',buried?'.29':'.38'],['study-high-1',buried?'.33':'.44'],['study-variable-2','right_thickness'],['study-low-2','.045'],['study-high-2','.055']])await set(id,value);
  await click('study-calculate');const study=await save('study-save','sipi-parameter-study.json');outputs.study=study;
  assert.equal(study.failed,0);assert.equal(study.quantity,quantity);assert.equal(study.rows.length,4);
  for(const row of study.rows){assert.deepEqual(row.document.mesh,precise.cross_section.mesh);assert.equal(row.impedance,row.line[quantity]);assert.equal(row.document.traces[0].width,row.parameters.left_width);assert.equal(row.document.traces[1].thickness,row.parameters.right_thickness);}
  await click('study-csv');const csv=await until(async()=>{try{return await readFile(join(downloads,'sipi-parameter-study.csv'),'utf8')}catch{}},'study CSV');
  assert.ok(csv.split('\n')[0].includes('left_width_m'));assert.ok(csv.split('\n')[0].includes('right_thickness_m'));
  for(const [id,value] of [['study-low-2','-1'],['study-high-2','.055']])await set(id,value);await click('study-calculate',true);
  const goals={};
  for(const variable of ['left_width','right_width']){
    await open(precise);
    const fields={left_profile:'rectangular',right_profile:'rectangular',left_width:buried?'.3':'.4',right_width:buried?'.5':'.65',left_thickness:'.035',right_thickness:'.05',height:buried?'1':'.5',gap:buried?'.4':'.25',box_width:buried?'6':'12',...(!buried?{air_height:'6'}:{}),eps_r:'4',tan_delta:'.02',target_variable:variable,lower:'.1',upper:'1.2',target:'100',tolerance:'.5'};
    for(const [id,value] of Object.entries(fields))await set(id,value);
    await click('mesh-auto');const input=await save();await click('design');const goal=await result(variable+'Goal');
    assert.equal(goal.design.variable,variable);assert.equal(goal.design.quantity,quantity);assert.equal(Object.hasOwn(goal.design,'width'),false);assert.equal(goal.design.search_tolerance,.25);
    assert.ok((await cdp.evaluate('document.querySelector("#history-data").textContent')).includes(variable.replace('_',' ')));
    assert.ok((await cdp.evaluate('document.querySelector("#refinement").textContent')).startsWith(variable==='left_width'?'Left width':'Right width'));
    assert.ok(Math.abs(goal.design.residual)<=.25&&Math.abs(goal.design.refined_residual)<=.5);assert.equal(goal.line[quantity],goal.design.impedance);
    assert.deepEqual(goal.design.history.slice(0,2).map(x=>x.parameter),[.1*1e-3,1.2*1e-3]);
    assert.equal(Object.hasOwn(await cdp.evaluate('window.domainRequests.at(-1)'),'mesh'),false);
    const designed=await save();exactGeometry(designed);assert.equal(designed.parameters[variable],goal.design.parameter);assert.deepEqual(designed.cross_section.mesh,goal.document.mesh);
    for(const key of Object.keys(input.parameters))if(key!==variable)assert.deepEqual(designed.parameters[key],input.parameters[key]);
    goals[variable]={input,designed};
    if(variable==='right_width'){await cdp.evaluate('document.querySelector("#refinement").scrollIntoView({block:"center"})');await writeFile(join(output,'selected-target-1400.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));}
  }
  await open(precise);for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
  await click('network-calculate');const network=await result('network');assert.equal(network.network.extension,'s4p');
  await click('touchstone-save');const ts=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s4p'),'utf8')}catch{}},'port export');assert.ok(ts.includes('# Hz S RI R 50'));
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#asymmetric-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['left_width','right_width','left_thickness','right_thickness','left_profile','right_profile','left_top_width','right_top_width','target_variable'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width,JSON.stringify(layout));for(const control of layout.controls)assert.ok(control.height>=44&&control.left>=0&&control.right<=width,JSON.stringify(control));layouts.push(layout);
    await writeFile(join(output,`asymmetric-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  for(const [name,value] of Object.entries({...outputs,firstInput,edits,project,goals}))await writeFile(join(output,name+'.json'),JSON.stringify(value,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  assert.ok(actions.every(a=>a.seconds<300));
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'private-native',editableForms:30,actions,layouts,errors,externalRequests:remoteRequests,checks:['explicit forward first use','inactive symmetric fields','three-unit exact inputs','invalid geometry rejection','independent dimension edits','independent profiles and zero thickness','exact A/B project restore','mesh and outer convergence','dimensionless material sweep','left width/right thickness corners','fixed nominal study mesh','length CSV','invalid study bounds','both selected width targets','exact selected-only writeback','four-port export','cancel/restart','four viewport44px controls','shutdown']},null,2));
} catch(error) {
  try {await writeFile(join(output,'requests.json'),JSON.stringify(await cdp?.evaluate('window.domainRequests'),null,2));} catch {}
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
