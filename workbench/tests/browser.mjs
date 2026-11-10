// Real browser acceptance; no browser automation package is required.
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile, mkdir, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import assert from 'node:assert/strict';

const output = resolve(process.argv[2] || '.validation/sipi-browser');
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
  await writeFile(join(output,'initial.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  if(webRoot) {
    cdp.blockedWorkerURLs=['*engine.py'];
    await cdp.evaluate('document.querySelector("#calculate").click()');
    await until(()=>cdp.evaluate('document.querySelector("#status").classList.contains("error")'),'missing Worker asset error',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
    cdp.blockedWorkerURLs=[];
  }
  await cdp.evaluate('document.querySelector("[data-template=stripline]").click();document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden || document.querySelector("#status").classList.contains("error")'),'stripline result',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  const z=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  assert.ok(Math.abs(z-50.216)<.6, 'Independent Cohn reference: '+z);
  await cdp.evaluate('document.querySelector("#unit").value="mil";document.querySelector("#unit").dispatchEvent(new Event("change"))');
  const width=await cdp.evaluate('Number(document.querySelector("#width").value)');
  assert.ok(Math.abs(width-0.5/.0254)<1e-7);
  assert.equal(await cdp.evaluate('Number(document.querySelector("#z-value").textContent)'),z);
  await cdp.evaluate('document.querySelector("#unit").value="mm";document.querySelector("#unit").dispatchEvent(new Event("change"));document.querySelector("#design").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#refinement").hidden || document.querySelector("#status").classList.contains("error")'),'width design',300000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  await cdp.evaluate('document.querySelector("#save").click()');
  const saved=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-cross-section.json'),'utf8'));}catch{return null;}},'saved design download');
  assert.equal(saved.schema,'sipi.cross-section/1');
  await cdp.evaluate('document.querySelector("#save-editable").click()');
  const goalEditable=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-editable-design.json'),'utf8'));}catch{}},'editable goal download');
  assert.equal(goalEditable.schema,'sipi.template-section/1');
  assert.deepEqual(goalEditable.cross_section,saved,'Goal export must retain the actual returned geometry and mesh.');
  assert.equal(goalEditable.parameters.width,saved.traces[0].width);
  await until(()=>cdp.evaluate('!document.querySelector("#open").disabled'),'save finished');

  await writeFile(join(output,'designed.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#width").value="0.6";document.querySelector("#width").dispatchEvent(new Event("input"))');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const inputPath=join(profile,'한글 design.json');await writeFile(inputPath,JSON.stringify(saved));
  const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector:'#file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[inputPath]});
  await until(()=>cdp.evaluate('!document.querySelector("#import-note").hidden'),'import');
  assert.equal(await cdp.evaluate('document.querySelector("#inputs").hidden'),true,'Imported geometry must not show stale template dimensions.');
  assert.equal(await cdp.evaluate('document.querySelector("#design").disabled'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#save-editable").disabled'),true);
  await cdp.evaluate('document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden'),'imported solve');
  assert.ok(Math.abs(await cdp.evaluate('Number(document.querySelector("#z-value").textContent)')-50)<.1);
  if(!webRoot) await cdp.evaluate(`window.originalFetch=window.fetch;window.delayNextStart=true;
    window.fetch=(...args)=>{if(window.delayNextStart && args[0]==='/api/job' && args[1]?.method==='POST') {
      window.delayNextStart=false;return new Promise((resolve,reject)=>setTimeout(()=>window.originalFetch(...args).then(resolve,reject),700));
    }return window.originalFetch(...args);}`);
  await cdp.evaluate('document.querySelector("#calculate").click();document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("cancelled")'),'cancel');
  await cdp.evaluate('document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden || document.querySelector("#status").classList.contains("error")'),'restart after cancellation',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  if(!webRoot) await cdp.evaluate('window.fetch=window.originalFetch');
  assert.ok(Math.abs(await cdp.evaluate('Number(document.querySelector("#z-value").textContent)')-50)<.1);
  await cdp.evaluate('document.querySelector("#network-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#network-result").hidden || document.querySelector("#status").classList.contains("error")'),'frequency response',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#network-table tr").length'),41);
  assert.equal(await cdp.evaluate('document.querySelector("#crosstalk-note").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#network-table tr:first-child td").length'),4);
  assert.ok(await cdp.evaluate('document.querySelector("#network-description").textContent.includes("Perfect conductors")'));
  await cdp.evaluate('document.querySelector("#touchstone-save").click()');
  const touchstone=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s2p'),'utf8');}catch{return null;}},'Touchstone download');
  assert.ok(touchstone.includes('[Version] 2.0') && touchstone.includes('[Number of Frequencies] 41'));
  await cdp.evaluate('document.querySelector("#line-length").value="50";document.querySelector("#line-length").dispatchEvent(new Event("input"))');
  assert.equal(await cdp.evaluate('document.querySelector("#network-result").hidden'),true,'Frequency input changes clear the response');
  await cdp.evaluate('document.querySelector("[data-template=coupled_microstrip]").click()');
  assert.equal(await cdp.evaluate('document.querySelector("#save-editable").disabled'),false,'Choosing a template restores editable saving after a geometric import.');
  await cdp.evaluate('document.querySelector("#network-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#network-result").hidden || document.querySelector("#status").classList.contains("error")'),'coupled response',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.ok(await cdp.evaluate('document.querySelector("#network-description").textContent.includes("Sdd21")'));
  assert.equal(await cdp.evaluate('document.querySelector("#crosstalk-note").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#network-table tr:first-child td").length'),6);
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  await cdp.evaluate('document.querySelector("#touchstone-save").click()');
  const coupledFile=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s4p'),'utf8');}catch{return null;}},'four-port download');
  assert.ok(coupledFile.includes('[Number of Ports] 4'));
  await writeFile(join(output,'network.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await rm(join(downloads,'sipi-cross-section.json'));
  await cdp.evaluate('document.querySelector("#save").click()');
  const asymmetric=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-cross-section.json'),'utf8'));}catch{return null;}},'pair document');
  asymmetric.traces[1].width *= .5;
  if(asymmetric.traces[1].top_width !== undefined) asymmetric.traces[1].top_width *= .5;
  const asymmetricPath=join(profile,'asymmetric pair.json');await writeFile(asymmetricPath,JSON.stringify(asymmetric));
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[asymmetricPath]});
  await until(()=>cdp.evaluate('!document.querySelector("#import-note").hidden'),'asymmetric import');
  await cdp.evaluate('document.querySelector("#network-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#network-result").hidden || document.querySelector("#status").classList.contains("error")'),'asymmetric response',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelector("#scalar-summary").hidden'),true);
  assert.ok(await cdp.evaluate('document.querySelector("#scalar-note").textContent.includes("not symmetric")'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#matrices table").length'),3);
  assert.equal(await cdp.evaluate('document.querySelectorAll("#network-table tr:first-child td").length'),6);
  await writeFile(join(output,'asymmetric.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate(`document.querySelector('[data-template=coated_microstrip]').click();
    document.querySelector('#profile').value='tapered';document.querySelector('#profile').dispatchEvent(new Event('input'));
    document.querySelector('#thickness').value='0';document.querySelector('#thickness').dispatchEvent(new Event('input'));
    document.querySelector('#calculate').click()`);
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("positive copper thickness")'),'invalid taper refusal');
  await cdp.evaluate(`document.querySelector('#width').value='.5';document.querySelector('#width').dispatchEvent(new Event('input'));
    document.querySelector('#thickness').value='.1';document.querySelector('#thickness').dispatchEvent(new Event('input'));
    document.querySelector('#calculate').click()`);
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden || document.querySelector("#status").classList.contains("error")'),'coated tapered result',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section polygon").length'),1);
  const coatedZ=await cdp.evaluate('Number(document.querySelector("#z-value").textContent)');
  await rm(join(downloads,'sipi-cross-section.json'));
  await cdp.evaluate('document.querySelector("#save").click()');
  const tapered=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-cross-section.json'),'utf8'));}catch{return null;}},'v2 download');
  assert.equal(tapered.schema,'sipi.cross-section/2');
  assert.equal(tapered.traces[0].top_width,.0004);
  assert.equal(tapered.layers[1].eps_r,3.5);
  const taperPath=join(profile,'tapered coating.json');await writeFile(taperPath,JSON.stringify(tapered));
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[taperPath]});
  await until(()=>cdp.evaluate('!document.querySelector("#import-note").hidden'),'v2 import');
  assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section polygon").length'),1);
  await cdp.evaluate('document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden'),'v2 solve',180000);
  assert.equal(await cdp.evaluate('Number(document.querySelector("#z-value").textContent)'),coatedZ);
  // Show editable fields in the desktop/mobile screenshots and check stale-result handling.
  await cdp.evaluate('document.querySelector("[data-template=coated_microstrip]").click()');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await writeFile(join(output,'coated-taper.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#study-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#study-result").hidden || document.querySelector("#status").classList.contains("error")'),'parameter sweep',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#study-table tr").length'),5);
  await cdp.evaluate(`document.querySelector('#study-mode').value='corners';document.querySelector('#study-mode').dispatchEvent(new Event('input'));
    document.querySelector('#study-count').value='2';document.querySelector('#study-count').dispatchEvent(new Event('input'))`);
  assert.equal(await cdp.evaluate('document.querySelector("#study-result").hidden'),true);
  await cdp.evaluate('document.querySelector("#study-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#study-result").hidden || document.querySelector("#status").classList.contains("error")'),'two-variable corners',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#study-table tr").length'),4);
  await cdp.evaluate(`document.querySelector('#study-mode').value='monte_carlo';document.querySelector('#study-mode').dispatchEvent(new Event('input'));
    document.querySelector('#study-points').value='3';document.querySelector('#study-points').dispatchEvent(new Event('input'));
    document.querySelector('#study-calculate').click()`);
  await until(()=>cdp.evaluate('!document.querySelector("#study-result").hidden || document.querySelector("#status").classList.contains("error")'),'Monte Carlo study',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  assert.equal(await cdp.evaluate('document.querySelectorAll("#study-table tr").length'),3);
  const oldBound=await cdp.evaluate('Number(document.querySelector("#study-low-1").value)');
  await cdp.evaluate(`document.querySelector('#unit').value='mil';document.querySelector('#unit').dispatchEvent(new Event('change'))`);
  assert.ok(Math.abs(await cdp.evaluate('Number(document.querySelector("#study-low-1").value)')-oldBound/.0254)<1e-8);
  await cdp.evaluate('document.querySelector("#study-save").click();document.querySelector("#study-csv").click()');
  const studySaved=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-parameter-study.json'),'utf8'));}catch{return null;}},'study JSON download');
  assert.equal(studySaved.schema,'sipi.parameter-study/1');assert.equal(studySaved.settings.generator,'PCG64');assert.equal(studySaved.settings.seed,42);assert.equal(studySaved.rows.length,3);assert.equal(studySaved.failed,0);
  assert.equal(studySaved.settings.variables[0].parameter,'width');
  const csv=await until(async()=>{try{return await readFile(join(downloads,'sipi-parameter-study.csv'),'utf8');}catch{return null;}},'study CSV download');
  assert.ok(csv.includes('width_m'));assert.equal(csv.trim().split('\n').length,4);
  // Editable inputs preserve exact physical values, hidden arguments and mesh.
  const editableData=spawnSync(process.env.SIPI_PYTHON || 'python',['workbench/tests/editable_cases.py'],{encoding:'utf8',env:{...process.env,OPENBLAS_NUM_THREADS:'1'}});
  assert.equal(editableData.status,0,editableData.stderr);
  const editableCases=JSON.parse(editableData.stdout);
  async function openEditable(value, name='한글 editable.json') {
    const path=join(profile,name);await writeFile(path,typeof value==='string'?value:JSON.stringify(value));
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[path]});
    await until(()=>cdp.evaluate('!document.querySelector("#open").disabled'),'editable validation',180000);
  }
  async function downloadEditable() {
    await rm(join(downloads,'sipi-editable-design.json'),{force:true});
    await cdp.evaluate('document.querySelector("#save-editable").click()');
    const value=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-editable-design.json'),'utf8'));}catch{}},'editable download');
    await until(()=>cdp.evaluate('!document.querySelector("#open").disabled'),'editable save finished');return value;
  }
  for(const sample of editableCases.cases) {
    await openEditable(sample);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
    assert.equal(await cdp.evaluate('document.querySelector("#inputs").hidden'),false);
    assert.equal(await cdp.evaluate('document.querySelector("#design").disabled'),false);
    assert.equal(await cdp.evaluate('document.querySelector("#study-calculate").disabled'),false);
    assert.equal(await cdp.evaluate('document.querySelector("[data-template].selected").dataset.template'),sample.template);
    await cdp.evaluate('for(const unit of ["mil","mm","mil","mm"]) {document.querySelector("#unit").value=unit;document.querySelector("#unit").dispatchEvent(new Event("change"));}');
    assert.deepEqual(await downloadEditable(),sample,'Untouched display and unit toggles must preserve exact inputs.');
  }
  const beforeInvalid=await downloadEditable();
  const corrupt=structuredClone(beforeInvalid);corrupt.parameters.width*=2;
  for(const invalid of [corrupt,editableCases.unsupported,JSON.stringify(beforeInvalid).replace('"schema":','"schema":"duplicate","schema":')]) {
    await openEditable(invalid);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
    assert.deepEqual(await downloadEditable(),beforeInvalid,'Failed imports must preserve the previous editable input.');
  }
  // Cancel while File.text is pending, then deliver the late bytes.
  await cdp.evaluate('window.originalFileText=File.prototype.text;File.prototype.text=function(){const file=this;return new Promise(resolve=>{window.releaseFile=()=>window.originalFileText.call(file).then(resolve)});};');
  const latePath=join(profile,'late.json');await writeFile(latePath,JSON.stringify(goalEditable));
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[latePath]});
  await until(()=>cdp.evaluate('typeof window.releaseFile==="function"'),'pending file read');
  await cdp.evaluate('document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#open").disabled'),'cancel file read');
  await cdp.evaluate('File.prototype.text=window.originalFileText;window.releaseFile()');
  assert.deepEqual(await downloadEditable(),beforeInvalid,'Late file bytes must not replace the current input.');
  await openEditable(goalEditable);
  await cdp.evaluate('document.querySelector("#unit").value="mm";document.querySelector("#unit").dispatchEvent(new Event("change"));for(const [id,value] of [["target","50"],["lower",".4"],["upper",".6"],["tolerance",".1"]]) {const element=document.getElementById(id);element.value=value;element.dispatchEvent(new Event("input"));}document.querySelector("#design").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#refinement").hidden || document.querySelector("#status").classList.contains("error")'),'reopened target',300000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  const reopenedGoal=await downloadEditable();
  assert.equal(reopenedGoal.parameters.width,reopenedGoal.cross_section.traces[0].width);
  await cdp.evaluate('document.querySelector("#width").value=".55";document.querySelector("#width").dispatchEvent(new Event("input"))');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const edited=await downloadEditable();
  assert.equal(edited.parameters.width,.00055);assert.deepEqual(edited.cross_section.mesh,reopenedGoal.cross_section.mesh);
  assert.deepEqual({...edited.parameters,width:reopenedGoal.parameters.width},reopenedGoal.parameters);
  await cdp.evaluate('document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden || document.querySelector("#status").classList.contains("error")'),'edited solve',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false);
  await cdp.evaluate('for(const [id,value] of [["study-mode","sweep"],["study-variable-1","width"],["study-low-1",".54"],["study-high-1",".56"],["study-points","2"]]) {const element=document.getElementById(id);element.value=value;element.dispatchEvent(new Event("input"));}document.querySelector("#study-calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#study-result").hidden || document.querySelector("#status").classList.contains("error")'),'reopened study',300000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  await writeFile(join(output,'editable-design.json'),JSON.stringify(edited,null,2));
  await writeFile(join(output,'editable.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await writeFile(join(output,'study.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  // Input projects preserve exact variants and pre-existing records.
  const projectFile=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector:'#project-file'});
  async function openProject(value, name='입력 프로젝트.json') {
    const path=join(profile,name);await writeFile(path,typeof value==='string'?value:JSON.stringify(value));
    await cdp.call('DOM.setFileInputFiles',{nodeId:projectFile.nodeId,files:[path]});
    await until(()=>cdp.evaluate('!document.querySelector("#project-open").disabled'),'project open',180000);
  }
  async function saveProject() {
    await rm(join(downloads,'sipi-project.json'),{force:true});
    await cdp.evaluate('document.querySelector("#project-save").click()');
    const result=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-project.json'),'utf8'));}catch{}},'project download',180000);
    await until(()=>cdp.evaluate('!document.querySelector("#project-save").disabled'),'project save finished');return result;
  }
  async function selectDesign(id) {
    await cdp.evaluate(`document.querySelector('#project-design').value=${JSON.stringify(id)};document.querySelector('#project-design').dispatchEvent(new Event('change'));`);
    await until(()=>cdp.evaluate('!document.querySelector("#project-open").disabled'),'project switch',180000);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  await cdp.evaluate('document.querySelector("#project-duplicate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#project-duplicate").disabled'),'initial duplicate',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#project-design").options.length'),2);
  const firstProject=await saveProject();
  const [a,b]=firstProject.designs.map(d=>d.design_id);
  assert.deepEqual(JSON.parse(firstProject.designs[0].source_text),edited);
  assert.equal(firstProject.designs[0].source_text,firstProject.designs[1].source_text);
  await cdp.evaluate('document.querySelector("#width").value=".6";document.querySelector("#width").dispatchEvent(new Event("input"))');
  await selectDesign(a);
  assert.equal(await cdp.evaluate('Number(document.querySelector("#width").value)'),.55);
  await selectDesign(b);
  assert.equal(await cdp.evaluate('Number(document.querySelector("#width").value)'),.6);
  const variants=await saveProject();
  assert.equal(JSON.parse(variants.designs[0].source_text).parameters.width,.00055);
  assert.equal(JSON.parse(variants.designs[1].source_text).parameters.width,.0006);
  for(const d of variants.designs) {assert.deepEqual(JSON.parse(d.source_text).cross_section.mesh,edited.cross_section.mesh);assert.deepEqual(d.records,[]);}
  await openProject(variants);
  assert.equal(await cdp.evaluate('document.querySelector("#project-design").value'),a);
  await selectDesign(b);
  const corruptProject=structuredClone(variants);corruptProject.title='digest mismatch';
  for(const invalid of [corruptProject,editableCases.unsupported_project,JSON.stringify(variants).replace('"schema":','"schema":"duplicate","schema":')]) {
    await openProject(invalid);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#project-design").value'),b);
    assert.deepEqual(await saveProject(),variants,'Rejected projects must retain all variants.');
  }
  await cdp.evaluate('window.releaseFile=null;window.originalFileText=File.prototype.text;File.prototype.text=function(){const file=this;return new Promise(resolve=>{window.releaseFile=()=>window.originalFileText.call(file).then(resolve)});};');
  const lateProject=join(profile,'late project.json');await writeFile(lateProject,editableCases.recorded_project_text);
  await cdp.call('DOM.setFileInputFiles',{nodeId:projectFile.nodeId,files:[lateProject]});
  await until(()=>cdp.evaluate('typeof window.releaseFile==="function"'),'pending project read');
  await cdp.evaluate('document.querySelector("#cancel").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#project-open").disabled'),'cancel project read');
  await cdp.evaluate('File.prototype.text=window.originalFileText;window.releaseFile()');
  assert.deepEqual(await saveProject(),variants,'Late project bytes must not replace current variants.');
  await openProject(editableCases.recorded_project_text);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false);
  assert.deepEqual(await saveProject(),editableCases.recorded_project,'Existing exact records and selection survive reopening.');
  assert.equal(await readFile(join(downloads,'sipi-project.json'),'utf8'),editableCases.recorded_project_text,
    'Raw canonical project text preserves numeric representation inside existing records.');
  await openProject(editableCases.recorded_project); // Deliberate JS numeric reserialization.
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
  await saveProject();
  assert.equal(await readFile(join(downloads,'sipi-project.json'),'utf8'),editableCases.recorded_project_text,
    'A digest-changing reserialization must be rejected without replacing the raw project.');
  await cdp.evaluate('document.querySelector("#width").value=".6";document.querySelector("#width").dispatchEvent(new Event("input"));document.querySelector("#project-label").value="변형 B";');
  const updatedRecord=await saveProject();
  assert.equal(updatedRecord.designs[0].selected_run_id,null);
  assert.deepEqual(updatedRecord.designs[0].records,editableCases.recorded_project.designs[0].records);
  await cdp.evaluate('document.querySelector("#calculate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#result").hidden || document.querySelector("#status").classList.contains("error")'),'project solve',180000);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false);
  assert.deepEqual(await saveProject(),updatedRecord,'New workbench results must not fabricate saved records.');
  await cdp.evaluate('document.querySelector("#project-duplicate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#project-duplicate").disabled'),'recorded duplicate',180000);
  const copiedRecord=await saveProject();assert.deepEqual(copiedRecord.designs[1].records,[]);
  assert.deepEqual(copiedRecord.designs[0].records,editableCases.recorded_project.designs[0].records);
  await writeFile(join(output,'project.json'),JSON.stringify(copiedRecord,null,2));
  await writeFile(join(output,'project.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  // Use controls for the buried pair, including its differential target and A/B files.
  await cdp.evaluate(`document.querySelector('#unit').value='mm';document.querySelector('#unit').dispatchEvent(new Event('change'));
    document.querySelector('[data-template=coupled_stripline]').click();
    for(const [id,value] of [['profile','rectangular'],['width','.5'],['height','1'],['gap','.2'],['thickness','0'],['eps_r','4'],['tan_delta','0']]) {
      const field=document.getElementById(id);field.value=value;field.dispatchEvent(new Event('input'));
    }`);
  assert.equal(await cdp.evaluate('document.querySelector("#height-label").textContent'),'Plane spacing');
  assert.equal(await cdp.evaluate('document.querySelector("#gap-field").hidden'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#ground-field").hidden'),true);
  assert.ok(await cdp.evaluate('document.querySelector("#target-label").textContent.includes("Differential")'));
  assert.equal(await cdp.evaluate('document.querySelector("#cross-section").textContent.match(/GROUND PLANE/g).length'),2);
  async function buriedAction(button, outputSelector, label, timeout=300000) {
    await cdp.evaluate(`document.querySelector(${JSON.stringify(button)}).click()`);
    await until(()=>cdp.evaluate(`!document.querySelector(${JSON.stringify(outputSelector)}).hidden || document.querySelector('#status').classList.contains('error')`),label,timeout);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  await buriedAction('#calculate','#result','buried pair analysis');
  assert.equal(await cdp.evaluate('document.querySelector("#z-label").textContent'),'Differential impedance');
  await cdp.evaluate(`for(const [id,value] of [['target','80'],['lower','.4'],['upper','.6'],['tolerance','.1']]) {
    const field=document.getElementById(id);field.value=value;field.dispatchEvent(new Event('input'));
  }`);
  await buriedAction('#design','#refinement','buried pair target');
  const buriedGoal=await downloadEditable();
  assert.equal(buriedGoal.template,'coupled_stripline');assert.equal(buriedGoal.parameters.substrate_height,undefined);
  assert.equal(buriedGoal.parameters.plane_spacing,.001);assert.equal(buriedGoal.cross_section.box.top,'ground');
  assert.equal(buriedGoal.parameters.width,buriedGoal.cross_section.traces[0].width);
  await cdp.evaluate('document.querySelector("#frequency-points").value="3"');
  await buriedAction('#network-calculate','#network-result','buried pair network');
  assert.ok(await cdp.evaluate('document.querySelector("#network-description").textContent.includes("Sdd21")'));
  await rm(join(downloads,'sipi-line.s4p'),{force:true});
  await cdp.evaluate('document.querySelector("#touchstone-save").click()');
  const buriedNetwork=await until(async()=>{try{return await readFile(join(downloads,'sipi-line.s4p'),'utf8');}catch{}},'buried four-port file');
  assert.ok(buriedNetwork.includes('[Number of Ports] 4'));
  await cdp.evaluate(`for(const [id,value] of [['study-mode','sweep'],['study-variable-1','eps_r'],['study-low-1','3.6'],['study-high-1','4.4'],['study-points','2']]) {
    const field=document.getElementById(id);field.value=value;field.dispatchEvent(new Event('input'));
  }`);
  await buriedAction('#study-calculate','#study-result','buried pair study');
  assert.ok(await cdp.evaluate('document.querySelector("#study-summary").textContent.includes("z_diff")'));
  await rm(join(downloads,'sipi-parameter-study.json'),{force:true});
  await cdp.evaluate('document.querySelector("#study-save").click()');
  const buriedStudy=await until(async()=>{try{return JSON.parse(await readFile(join(downloads,'sipi-parameter-study.json'),'utf8'));}catch{}},'buried study file');
  assert.equal(buriedStudy.quantity,'z_diff');assert.equal(buriedStudy.failed,0);
  assert.ok(Math.abs(buriedStudy.rows[0].impedance*Math.sqrt(3.6)/(buriedStudy.rows[1].impedance*Math.sqrt(4.4))-1)<1e-10);
  await cdp.evaluate('document.querySelector("#project-label").value="Buried pair A"');
  const buriedProject=await saveProject();
  const buriedId=await cdp.evaluate('document.querySelector("#project-design").value');
  assert.deepEqual(JSON.parse(buriedProject.designs.find(item=>item.design_id===buriedId).source_text),buriedGoal);
  await cdp.evaluate('document.querySelector("#project-duplicate").click()');
  await until(()=>cdp.evaluate('!document.querySelector("#project-duplicate").disabled'),'buried duplicate',180000);
  const buriedB=await cdp.evaluate('document.querySelector("#project-design").value');
  await cdp.evaluate('document.querySelector("#width").value=".55";document.querySelector("#width").dispatchEvent(new Event("input"));document.querySelector("#project-label").value="Buried pair B"');
  const pairVariants=await saveProject(), pairProjectRaw=await readFile(join(downloads,'sipi-project.json'),'utf8');
  await openProject(pairProjectRaw);await selectDesign(buriedId);
  assert.deepEqual(await downloadEditable(),buriedGoal);
  await selectDesign(buriedB);
  assert.deepEqual(await downloadEditable(),JSON.parse(pairVariants.designs.find(item=>item.design_id===buriedB).source_text));
  await writeFile(join(output,'buried-pair-project.json'),pairProjectRaw);
  await writeFile(join(output,'buried-pair.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth <= innerWidth'),true,'mobile horizontal overflow');
  await writeFile(join(output,'mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#exit").click()');
  await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'shutdown');
  if (!webRoot) await until(()=>server.exitCode!==null,'server shutdown');
  const parity=[], parityFailures=[];
  if (webRoot) {
    assert.deepEqual(apiRequests,[],'Browser mode must not send a model to a server API.');
    const native=spawnSync(process.env.SIPI_PYTHON || 'python',['workbench/tests/native_cases.py'],{env:{...process.env,OPENBLAS_NUM_THREADS:'1'},encoding:'utf8',timeout:120000});
    assert.equal(native.status,0,native.stderr);
    const cases=JSON.parse(native.stdout);
    await cdp.evaluate('window.parityWorker=new Worker("./worker.js");window.workerSequence=0;window.workerCall=input=>new Promise((resolve,reject)=>{const id=++window.workerSequence;window.parityWorker.onmessage=e=>{if(e.data.id===id)resolve(e.data)};window.parityWorker.onerror=e=>reject(Error(e.message));window.parityWorker.postMessage({id,input})})');
    function compare(actual,expected,path='line') {
      if(typeof expected==='number') { const error=Math.abs(actual-expected)/Math.max(Math.abs(expected),Math.abs(actual),1e-30);if(!(error<=1e-6))parityFailures.push({path,actual,expected,relative_error:error});return error; }
      if(Array.isArray(expected)) return Math.max(0,...expected.map((v,i)=>compare(actual[i],v,`${path}[${i}]`)));
      if(expected && typeof expected==='object') return Math.max(0,...Object.keys(expected).map(k=>compare(actual[k],expected[k],`${path}.${k}`)));
      assert.deepEqual(actual,expected,path);return 0;
    }
    for(const sample of cases) {
      const result=await cdp.evaluate(`window.workerCall(${JSON.stringify(sample.input)})`);
      assert.equal(result.status,'complete',result.message);
      if(sample.input.action==='study') {
        const actual=result.result.study,expected=sample.result.study;
        assert.deepEqual(actual.settings,expected.settings);
        assert.equal(actual.failed,0);
        let relative=0;
        for(let i=0;i<expected.rows.length;i++) {
          assert.deepEqual(actual.rows[i].parameters,expected.rows[i].parameters);
          relative=Math.max(relative,compare(actual.rows[i].line,expected.rows[i].line,'study.line'),compare(actual.rows[i].impedance,expected.rows[i].impedance,'study.impedance'));
        }
        parity.push({template:sample.input.template,action:'study',mode:sample.input.study.mode,max_relative_error:relative,runtime:result.result.runtime});
      } else if(sample.input.action==='network') {
        let absolute=0;
        const actual=result.result.network, expected=sample.result.network;
        for(const key of ['real','imag']) for(let f=0;f<expected[key].length;f++) for(let i=0;i<expected[key][f].length;i++) for(let j=0;j<expected[key][f][i].length;j++) absolute=Math.max(absolute,Math.abs(actual[key][f][i][j]-expected[key][f][i][j]));
        assert.deepEqual(actual.ports,expected.ports);
        if(expected.crosstalk) {
          assert.deepEqual(actual.crosstalk.next_ports,[2,1]);assert.deepEqual(actual.crosstalk.fext_ports,[4,1]);
          for(const key of ['next_db','fext_db']) for(let i=0;i<expected.crosstalk[key].length;i++) {
            const error=Math.abs(10**(actual.crosstalk[key][i]/20)-10**(expected.crosstalk[key][i]/20));
            if(!(error<=1e-7)) parityFailures.push({crosstalk:key,amplitude_error:error});
          }
        }
        if(!(absolute<=1e-7)) parityFailures.push({template:sample.input.template,network_absolute_error:absolute});
        parity.push({template:sample.input.template,action:'network',max_absolute_error:absolute,runtime:result.result.runtime});
      } else {
        parity.push({template:sample.input.template,max_relative_error:compare(result.result.line,sample.result.line,sample.input.template),runtime:result.result.runtime});
      }
    }
    await cdp.evaluate('window.parityWorker.terminate()');
  }
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot) assert.ok(workerTargets.length>=4,'Observe failed, retried, restarted and parity Worker network contexts.');
  await writeFile(join(output,'report.json'),JSON.stringify({status:parityFailures.length?'failed':'passed',mode:webRoot?'browser-worker':'local-native',stripline_z0:z,externalRequests:remoteRequests,apiRequests:apiRequests.length,workerTargets,errors,parity,parityFailures,checks:['six editable form exact save/reopen and unit invariance','buried pair form/80 ohm target/4port/TEM sweep/A-B raw project resume','editable mismatch/duplicate/unsupported refusal','late file read cancellation','reopened goal/edit/analyze/study','asymmetric imported pair matrices/network without even-odd claim','single-ended NEXT/FEXT port mapping','sweep/corners/Monte Carlo','study CSV/JSON download and unit conversion','tapered geometry and v2 save/import','planar coating','invalid taper refusal','frequency sweep','2/4-port Touchstone download','network stale results','render','solve','unit conversion','target width/refinement','stale results','JSON save/import','cancel and restart','mobile','shutdown','page and Worker network observation',...(webRoot?['missing asset error and retry']:[])]},null,2));
  assert.deepEqual(parityFailures,[],'Browser/native parity must meet the preregistered relative 1e-6 threshold.');
  console.log('Browser acceptance passed: solve, target, JSON save/import, cancel, mobile, shutdown; no external HTTP requests.');
} catch(error) {
  let application=null;
  try {application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden,calculateDisabled:document.querySelector("#calculate")?.disabled})');} catch {}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',mode:webRoot?'browser-worker':'local-native',failure:error.message,application,errors,remoteRequests,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));
  throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse()) if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
