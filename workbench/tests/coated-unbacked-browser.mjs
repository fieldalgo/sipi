// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const paired=process.env.SIPI_COATED_PAIR==='1';
const template=paired?'coupled_coated_unbacked_coplanar':'coated_unbacked_coplanar';
const quantity=paired?'z_diff':'z0',extension=paired?'s4p':'s2p';
const output = resolve(process.argv[2] || '.validation/sipi-coated-unbacked-browser');
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

  const fixtureRun=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/editable_cases.py'],{encoding:'utf8'});
  assert.equal(fixtureRun.status,0,fixtureRun.stderr);const fixtures=JSON.parse(fixtureRun.stdout);
  assert.equal(fixtures.cases.length,11);
  const extras=spawnSync(process.env.SIPI_PYTHON||'python',['-c',`import json,sys
from sipi.template_document import TemplateSectionDocument
out=[]
for name in ['unbacked_coplanar','coupled_unbacked_coplanar',sys.argv[1]]:
 p=dict(width=.0005,gap=.0002,ground_width=.001,substrate_height=.0005,eps_r=4,thickness=.000035,top_width=.0004,lower_air_height=.006000000000123456)
 if name.startswith('coupled_'):p.update(gap=.0003,ground_gap=.0002000000000123456)
 if 'coated_' in name:p.update(coating_height=.0001000000000123456,coating_eps_r=3.5,coating_tan_delta=.02)
 out.append(json.loads(TemplateSectionDocument(name,p,mesh=dict(edge_size=4e-6,far_size=.00025,grade=.2)).dumps()))
print(json.dumps(out))`,paired?'coated_unbacked_coplanar':'coupled_coated_unbacked_coplanar'],{encoding:'utf8'});
  assert.equal(extras.status,0,extras.stderr);fixtures.cases.push(...JSON.parse(extras.stdout));assert.equal(fixtures.cases.length,14);
  assert.equal(await cdp.evaluate('document.querySelectorAll("[data-template]").length'),15);
  for(const input of fixtures.cases){await open(input);for(const unit of ['µm','mil','mm']){await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.deepEqual(await save(),input);}}
  await choose(template);
  assert.equal(await cdp.evaluate('document.querySelector("#lower-air-domain-fields").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#coating-fields").hidden'),false);
  for(const [id,value] of [['profile','tapered'],['width','.5'],['height','.5'],['gap',paired?'.3':'.2'],['ground_gap','.2'],['ground_width','1'],['thickness','.035'],['top_width','.4'],['eps_r','4'],['tan_delta','.01'],['coating_height','.1'],['coating_eps_r','3.5'],['coating_tan_delta','.02'],['box_mode','fixed'],['box_width','12'],['air_mode','fixed'],['air_height','6'],['lower_air_mode','fixed'],['lower_air_height','6.000000000123456']])await set(id,value);
  const precise=await save();assert.equal(precise.parameters.lower_air_height,6.000000000123456*1e-3);
  assert.deepEqual(precise.cross_section.layers.map(l=>l.name),['lower_air','substrate','coating','air']);
  for(const boundary of ['bottom','top','sides'])assert.equal(precise.cross_section.box[boundary],'open');
  precise.cross_section.mesh={edge_size:4e-6,far_size:.00025,grade:.2,min_angle:28};await open(precise);
  for(const unit of ['µm','mil','mm']){await cdp.evaluate(`document.querySelector('#unit').value='${unit}';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.deepEqual(await save(),precise);}
  assert.equal(await cdp.evaluate('document.querySelector("#cross-section").textContent.includes("GROUND PLANE")'),false);
  assert.ok(await cdp.evaluate('document.querySelector("#domain-values").textContent.includes("Lower air height")'));
  await set('project-label','Open domain A');const projectA=await save('project-save','sipi-project.json');
  await click('project-duplicate');const idB=await cdp.evaluate('document.querySelector("#project-design").value');
  await set('project-label','Open domain B');await set('lower_air_height','8');const alternative=await save();
  const projectB=await save('project-save','sipi-project.json'),rawProject=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await open(rawProject,'#project-file');assert.deepEqual(await save(),precise);await switchDesign(idB);assert.deepEqual(await save(),alternative);
  assert.equal(projectA.designs.length,1);assert.equal(projectB.designs.length,2);
  await open(precise);await click('calculate');const physical=await cdp.evaluate('window.completedResults.at(-1)');
  assert.equal(physical.document.box.bottom,'open');assert.ok(physical.line[quantity]>0);
  await click('comparison-pin');await set('lower_air_height','12');await click('calculate');const outer=await cdp.evaluate('window.completedResults.at(-1)');
  assert.ok(Math.abs(outer.line[quantity]/physical.line[quantity]-1)<.01);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-table-wrap").hidden'),false);
  await open(precise);await set('coating_eps_r','1');await set('coating_tan_delta','0');await click('calculate');const air=await cdp.evaluate('window.completedResults.at(-1)');
  assert.ok(air.line[quantity]>physical.line[quantity]);
  await open(precise);
  assert.equal(await cdp.evaluate('[...document.querySelector("#study-variable-1").options].some(o=>["lower_air_height","air_height","box_width"].includes(o.value))'),false);
  for(const [id,value] of [['study-mode','corners'],['study-count','2'],['study-variable-1','coating_height'],['study-low-1','.09'],['study-high-1','.11'],['study-variable-2','coating_eps_r'],['study-low-2','3.2'],['study-high-2','3.8']])await set(id,value);
  await click('study-calculate');const study=await save('study-save','sipi-parameter-study.json');
  assert.equal(study.quantity,quantity);assert.equal(study.failed,0);assert.equal(study.rows.length,4);
  for(const row of study.rows){assert.equal(row.document.layers[0].thickness,precise.parameters.lower_air_height);assert.equal(row.document.box.bottom,'open');assert.deepEqual(row.document.mesh,precise.cross_section.mesh);assert.equal(row.impedance,row.line[quantity]);}
  await set('study-low-1','.035');await click('study-calculate',true);
  await set('coating_height','');await click('calculate',true);await set('coating_height','.1');
  await set('lower_air_height','');await click('calculate',true);assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await cdp.evaluate(`document.querySelector('#unit').value='µm';document.querySelector('#unit').dispatchEvent(new Event('change'))`);assert.equal(await cdp.evaluate('document.querySelector("#lower_air_height").value'),'');
  await cdp.evaluate(`document.querySelector('#unit').value='mm';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
  await set('lower_air_mode','auto');const automatic=await save();assert.equal(automatic.parameters.lower_air_height,null);assert.equal(automatic.cross_section.layers[0].thickness,.005);
  await click('domain-inspect');await set('lower_air_mode','fixed');assert.equal((await save()).parameters.lower_air_height,.005);
  await choose('microstrip');await set('lower_air_height','-1');assert.equal(await cdp.evaluate('document.querySelector("#lower-air-domain-fields").hidden'),true);await save();
  await open(precise);
  for(const [id,value] of [['profile','rectangular'],['thickness','0'],['eps_r','1'],['tan_delta','0'],['coating_eps_r','1'],['coating_tan_delta','0'],['box_width','24'],['air_height','12'],['lower_air_height','12']])await set(id,value);
  const vacuum=await save();vacuum.cross_section.mesh={edge_size:4e-6,far_size:.0005,grade:.2,min_angle:28};await open(vacuum);
  await click('calculate');const vacuumResult=await cdp.evaluate('window.completedResults.at(-1)');
  // Explicit coarse forward example; the automatic width target uses its separately qualified policy.
  // Independent neutral free-space panel differential target, with charge/gauge and resolution checks.
  const target=paired?181.05076148507075:115.58150659942925;
  assert.ok(Math.abs(vacuumResult.line[quantity]/target-1)<.02);
  for(const [id,value] of [['lower','.4'],['upper','.6'],['target',String(target)],['tolerance','1']])await set(id,value);
  await click('mesh-auto');await click('design');
  const automaticGoal=await cdp.evaluate('window.completedResults.at(-1)');
  const automaticRequest=await cdp.evaluate('window.domainRequests.at(-1)');
  assert.equal(automaticRequest.action,'design');assert.equal(Object.hasOwn(automaticRequest,'mesh'),false);
  assert.ok(Math.abs(automaticGoal.design.residual)<=1&&Math.abs(automaticGoal.design.refined_residual)<=1);
  assert.ok(Math.abs(automaticGoal.design.width/.0005-1)<.04);
  assert.deepEqual(automaticGoal.document.mesh,{edge_size:1e-6,far_size:.00025625,grade:.15,min_angle:28});
  const automaticDesign=await save();assert.deepEqual(automaticDesign.cross_section.mesh,automaticGoal.document.mesh);
  assert.equal(automaticDesign.parameters.width,automaticGoal.design.width);
  for(const key of ['gap',...(paired?['ground_gap']:[]),'ground_width','lower_air_height','air_height','box_width','coating_height','coating_eps_r','coating_tan_delta'])assert.equal(automaticDesign.parameters[key],vacuum.parameters[key]);
  const goal=automaticGoal,designed=automaticDesign;
  assert.equal(designed.template,template);assert.equal(goal.line[quantity],goal.design.impedance);
  assert.ok(await cdp.evaluate('document.querySelector("#refinement").textContent.includes("Both meet")'));
  await open(precise);
  for(const [id,value] of [['frequency-start','1'],['frequency-stop','1000'],['frequency-points','3'],['line-length','100'],['series-r','2'],['reference-z','50']])await set(id,value);
  await click('network-calculate');const network=await cdp.evaluate('window.completedResults.at(-1)');
  assert.equal(await cdp.evaluate('document.querySelector("#crosstalk-note").hidden'),!paired);
  assert.ok(await cdp.evaluate(`document.querySelector("#network-description").textContent.includes(${JSON.stringify(paired?'Sdd21':'S21')})`));
  await click('touchstone-save');const touchstone=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.'+extension),'utf8')}catch{}},'coated unbacked port export');
  assert.ok(touchstone.includes('# Hz S RI R 50'));await writeFile(join(output,'coated-unbacked-line.'+extension),touchstone);
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');await click('calculate');
  const layouts=[];
  for(const width of [1400,768,390,320]){
    await cdp.call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<600});await cdp.evaluate('document.querySelector("#lower-air-domain-fields").scrollIntoView({block:"center"})');
    const layout=await cdp.evaluate(`(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,controls:['lower_air_mode','lower_air_height'].map(id=>{const r=document.getElementById(id).getBoundingClientRect();return {id,left:r.left,right:r.right,height:r.height}})}))()`);
    assert.ok(layout.scrollWidth<=width);for(const control of layout.controls)assert.ok(control.height>=44&&control.left>=0&&control.right<=width,JSON.stringify(control));layouts.push(layout);
    await writeFile(join(output,`coated-unbacked-${width}.png`),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  for(const [name,value] of Object.entries({project:projectB,physical,outer,air,vacuum:vacuumResult,goal,network,study,design:designed,automaticGoal,automaticDesign}))await writeFile(join(output,name+'.json'),JSON.stringify(value,null,2));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');if(!webRoot)await until(()=>server.exitCode===0,'installed host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'installed-native',actions,editableForms:15,layouts,errors,externalRequests:remoteRequests,checks:['old thirteen and other coated form exact inputs and new lower air through three units','lower-air auto/fixed and no backplane drawing','open finite side-ground domain','A/B project exact restore','lower-air domain sensitivity and comparison','coating height/permittivity corners with fixed mesh','coating air limit ordering','invalid lower air and study bounds','hidden lower-air isolation','vacuum independent target and both mesh gates','automatic target preserves resolved edge/growth, explicit mode and saved selected mesh','declared scalar/two-port or differential/four-port response','cancel/restart','four viewports/44px controls','normal shutdown']},null,2));
  console.log('Coated unbacked form acceptance passed.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,actions,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
