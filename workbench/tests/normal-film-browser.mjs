// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const paired=process.env.SIPI_NORMAL_PAIR==='1';
const template=paired?'coupled_conformal_coated_microstrip':'conformal_coated_microstrip';
const quantity=paired?'z_diff':'z0',extension=paired?'s4p':'s2p';
const output = resolve(process.argv[2] || '.validation/sipi-normal-film-browser');
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

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/normal_film_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const fixtures=JSON.parse(fixtureRun.stdout),precise=fixtures[template];
  assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),23);
  await choose(template);
  assert.equal(await cdp.evaluate('document.querySelector("#coating-height-field").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#coating-thickness-field").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section [data-region]").length'),0);
  await click('geometry-inspect');assert.equal(await cdp.evaluate('window.domainRequests.at(-1).action'),'document');
  async function inspect(doc){
    const got=await cdp.evaluate(`(()=>{const svg=document.querySelector('#cross-section'),w=${doc.box.width},h=${doc.layers.reduce((a,l)=>a+l.thickness,0)};
      const regions=[...svg.querySelectorAll('[data-region]')].map(n=>({name:n.dataset.region,points:[...n.points].map(p=>[p.x,p.y])}));
      return {regions,tag:document.querySelector('#preview-label').textContent};})()`);
    assert.match(got.tag,/Engine geometry/);assert.equal(got.regions.length,doc.dielectric_regions.length);
    for(let i=0;i<got.regions.length;i++){
      const row=got.regions[i],region=doc.dielectric_regions[i];assert.equal(row.name,region.name);assert.equal(row.points.length,region.vertices.length);
      for(let j=0;j<row.points.length;j++){
        const [x,y]=region.vertices[j],want=[65+(x/doc.box.width+.5)*630,245-y/doc.layers.reduce((a,l)=>a+l.thickness,0)*210];
        row.points[j].forEach((v,k)=>assert.ok(Math.abs(v-want[k])<1e-4,'SVG float coordinate'));
      }
    }
  }
  await open(precise);await inspect(precise.cross_section);
  for(const unit of ['µm','mil','mm']){await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.deepEqual(await save(),precise);await inspect(precise.cross_section);}
  await set('coating_thickness','.025');assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section [data-region]").length'),0);
  await click('geometry-inspect');const changed=await save();assert.equal(changed.parameters.coating_thickness,.000025);await inspect(changed.cross_section);
  await set('coating_thickness','');await click('geometry-inspect',true);assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section [data-region]").length'),0);
  await open(precise);await set('project-label','Normal film A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Normal film B');await set('coating_thickness','.025');const alternative=await save();
  const projectB=await save('project-save','sipi-project.json');await open(await readFile(join(downloads,'sipi-project.json'),'utf8'),'#project-file');
  assert.deepEqual(await save(),precise);await inspect(precise.cross_section);await switchDesign(idB);assert.deepEqual(await save(),alternative);await inspect(alternative.cross_section);
  assert.equal(projectA.designs.length,1);assert.equal(projectB.designs.length,2);
  await open(precise);await click('calculate');const physical=await cdp.evaluate('window.completedResults.at(-1)');assert.ok(physical.line[quantity]>0);await inspect(physical.document);
  await click('comparison-pin');await set('air_height','8');await set('box_width','16');await click('calculate');const outer=await cdp.evaluate('window.completedResults.at(-1)');
  assert.ok(Math.abs(outer.line[quantity]/physical.line[quantity]-1)<.01);assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  await open(precise);await set('coating_eps_r','1');await set('coating_tan_delta','0');await click('calculate');const air=await cdp.evaluate('window.completedResults.at(-1)');assert.ok(air.line[quantity]>physical.line[quantity]);
  await open(precise);
  for(const [id,value] of [['study-mode','corners'],['study-count','2'],['study-variable-1','coating_thickness'],['study-low-1','.018'],['study-high-1','.022'],['study-variable-2','coating_eps_r'],['study-low-2','3.2'],['study-high-2','3.8']])await set(id,value);
  await click('study-calculate');const study=await save('study-save','sipi-parameter-study.json');assert.equal(study.quantity,quantity);assert.equal(study.failed,0);assert.equal(study.rows.length,4);
  for(const row of study.rows){assert.deepEqual(row.document.mesh,precise.cross_section.mesh);assert.equal(row.impedance,row.line[quantity]);assert.equal(row.document.dielectric_regions[0].eps_r,row.parameters.coating_eps_r);}
  await set('study-low-1','0');await click('study-calculate',true);
  await set('top_width','.6');await click('calculate',true);await open(precise);
  await set('air_mode','auto');await click('domain-inspect');const domain=await cdp.evaluate('window.completedResults.at(-1).document');
  const expectedAir=domain.layers.at(-1).thickness-precise.parameters.thickness-precise.parameters.coating_thickness;
  await set('air_mode','fixed');const fixedAir=await save();assert.ok(Math.abs(fixedAir.parameters.air_height-expectedAir)<1e-17);
  await choose('coated_microstrip');await set('coating_thickness','-1');await set('coating_height','.2');const planar=await save();assert.ok(!Object.hasOwn(planar.parameters,'coating_thickness'));
  await open(precise);for(const [id,value] of [['profile','rectangular'],['thickness','0'],['eps_r','1'],['tan_delta','0'],['coating_thickness','.02'],['coating_eps_r','1'],['coating_tan_delta','0'],['box_width','48'],['air_height','24']])await set(id,value);
  const vacuum=await save();await click('calculate');const vacuumResult=await cdp.evaluate('window.completedResults.at(-1)');
  const target=paired?185.86449893041012:126.42602383113227;
  assert.ok(Math.abs(vacuumResult.line[quantity]/target-1)<.02);
  for(const [id,value] of [['lower','.4'],['upper','.6'],['target',String(target)],['tolerance','1']])await set(id,value);
  await click('mesh-auto');await click('design');const goal=await cdp.evaluate('window.completedResults.at(-1)');
  assert.equal(Object.hasOwn(await cdp.evaluate('window.domainRequests.at(-1)'),'mesh'),false);
  assert.ok(Math.abs(goal.design.residual)<=1&&Math.abs(goal.design.refined_residual)<=1);assert.ok(Math.abs(goal.design.width/.0005-1)<.04);
  assert.equal(goal.line[quantity],goal.design.impedance);const designed=await save();assert.deepEqual(designed.cross_section.mesh,goal.document.mesh);assert.equal(designed.parameters.width,goal.design.width);
  for(const key of ['air_height','box_width','coating_thickness','coating_eps_r','coating_tan_delta',...(paired?['gap']:[])])assert.equal(designed.parameters[key],vacuum.parameters[key]);await inspect(goal.document);
  await open(precise);for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
  await click('network-calculate');const network=await cdp.evaluate('window.completedResults.at(-1)');assert.equal(network.network.extension,extension);
  await click('touchstone-save');const touchstone=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.'+extension),'utf8')}catch{}},'port export');assert.ok(touchstone.includes('# Hz S RI R 50'));
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:1000,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#coating-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['coating_thickness','coating_eps_r','coating_tan_delta'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44&&control.left>=0&&control.right<=width,JSON.stringify(control));layouts.push(layout);await inspect(precise.cross_section);
    await writeFile(join(output,`normal-film-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  for(const [name,value] of Object.entries({project:projectB,physical,outer,air,vacuum:vacuumResult,goal,network,study,design:designed}))await writeFile(join(output,name+'.json'),JSON.stringify(value,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',actions,editableForms:23,layouts,errors,externalRequests:remoteRequests,checks:['normal and planar fields separate','engine vertices displayed without JS geometry inference','exact normal thickness through three units','edit invalidates old geometry','invalid input keeps preview uninspected','A/B exact project restore','mesh and domain checks','film air limit ordering','normal thickness/material corners','invalid film study and overhang refusal','air clearance auto/fixed transport','inactive field isolation','independent vacuum panel target and both mesh residuals','two/four port export','cancel/restart','four viewport controls','shutdown']},null,2));
  console.log('Normal film form acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
