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
  await writeFile(join(output,'designed.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#width").value="0.6";document.querySelector("#width").dispatchEvent(new Event("input"))');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  const inputPath=join(profile,'한글 design.json');await writeFile(inputPath,JSON.stringify(saved));
  const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector:'#file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[inputPath]});
  await until(()=>cdp.evaluate('!document.querySelector("#import-note").hidden'),'import');
  assert.equal(await cdp.evaluate('document.querySelector("#inputs").hidden'),true,'Imported geometry must not show stale template dimensions.');
  assert.equal(await cdp.evaluate('document.querySelector("#design").disabled'),true);
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
  await cdp.evaluate('document.querySelector("[data-template=coupled_microstrip]").click();document.querySelector("#network-calculate").click()');
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
  await writeFile(join(output,'study.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
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
  await writeFile(join(output,'report.json'),JSON.stringify({status:parityFailures.length?'failed':'passed',mode:webRoot?'browser-worker':'local-native',stripline_z0:z,externalRequests:remoteRequests,apiRequests:apiRequests.length,workerTargets,errors,parity,parityFailures,checks:['asymmetric imported pair matrices/network without even-odd claim','single-ended NEXT/FEXT port mapping','sweep/corners/Monte Carlo','study CSV/JSON download and unit conversion','tapered geometry and v2 save/import','planar coating','invalid taper refusal','frequency sweep','2/4-port Touchstone download','network stale results','render','solve','unit conversion','target width/refinement','stale results','JSON save/import','cancel and restart','mobile','shutdown','page and Worker network observation',...(webRoot?['missing asset error and retry']:[])]},null,2));
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
