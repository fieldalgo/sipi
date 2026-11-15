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
  const installed = process.env.SIPI_PREVIEW_INSTALLED === '1';
  const serverArgs = webRoot ? ['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot] : installed ? ['-m','sipi','gui','--no-browser'] : ['workbench/desktop/main.py','--no-browser'];
  const server = spawn(process.env.SIPI_PYTHON || 'python', serverArgs, {cwd:installed?profile:undefined,env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});
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

  const target=new URL(url);target.pathname='/pair-preview.html';
  await cdp.call('Page.navigate',{url:target.href});
  await until(()=>cdp.evaluate('!!document.querySelector("#section rect")'),'preview drawing');
  assert.equal(await cdp.evaluate('document.querySelector(".pilot a").getAttribute("href")'),'mailto:dev@fieldalgo.com?subject=SIPI%20pilot%20enquiry');
  const edit=async(id,value)=>cdp.evaluate(`document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event('input'))`);
  const click=async id=>cdp.evaluate(`document.getElementById(${JSON.stringify(id)}).click()`);
  const idle=async()=>until(()=>cdp.evaluate('!document.querySelector("#calculate").disabled'),'calculation complete',300000);
  const readDownload=async name=>until(async()=>{try{return JSON.parse(await readFile(join(downloads,name),'utf8'));}catch{return null;}},'download '+name);
  const records=[];
  for(const template of ['coupled_microstrip','coupled_stripline']) {
    if(template==='coupled_stripline') await cdp.evaluate('document.querySelector("#template").value="coupled_stripline";document.querySelector("#template").dispatchEvent(new Event("change"))');
    await click('calculate');await idle();
    assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
    await click('export');const nominal=await readDownload('sipi-pair-calculation.json');await rm(join(downloads,'sipi-pair-calculation.json'));
    assert.equal(nominal.request.template,template);assert.ok(nominal.result.line.z_diff>0 && nominal.result.line.z_common>0);
    records.push({template,kind:'nominal',...nominal});
    await click('keep-a');
    assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#export-comparison").disabled'),true);
    await edit('material-label','B <img src=x onerror=alert(1)>');
    await edit('material-note','Illustrative comparison; no supplier qualification');
    await edit('eps_r',template==='coupled_microstrip'?3.8:4.2);
    await writeFile(join(output,'calculations.json'),JSON.stringify(records,null,2));
    // Keep the ordinary example target; verify both actual mesh gates.
    await click('design');await idle();
    assert.equal(await cdp.evaluate('document.querySelector("#result").parentElement.id'),'design-output');
    assert.equal(await cdp.evaluate('document.querySelector("#width-result").hidden'),false);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false);
    assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
    await click('export');const goal=await readDownload('sipi-pair-calculation.json');await rm(join(downloads,'sipi-pair-calculation.json'));
    assert.ok(Math.abs(goal.result.design.impedance-100)<=.1);
    assert.ok(Math.abs(goal.result.design.refined_impedance-100)<=.1);
    assert.equal(goal.result.document.traces[0].width,goal.result.design.width);
    assert.equal(goal.request.parameters.gap,nominal.request.parameters.gap);
    records.push({template,kind:'goal',...goal});
    await click('export-comparison');const comparison=await readDownload('sipi-pair-comparison.json');await rm(join(downloads,'sipi-pair-comparison.json'));
    assert.equal(comparison.schema,'sipi.preview-comparison/1');
    assert.deepEqual(comparison.a,nominal);assert.deepEqual(comparison.b,goal);
    assert.equal(comparison.b.material.label,'B <img src=x onerror=alert(1)>');
    assert.equal(await cdp.evaluate('document.querySelectorAll("#comparison-rows img").length'),0);
    assert.ok(await cdp.evaluate('document.querySelector("#comparison-rows").textContent.includes("B <img")'));
    assert.ok(await cdp.evaluate('document.querySelectorAll("#comparison-rows .changed").length')>0);
    await writeFile(join(output,template+'-comparison.json'),JSON.stringify(comparison,null,2));
    await writeFile(join(output,'calculations.json'),JSON.stringify(records,null,2));
    await writeFile(join(output,template+'.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
    await click('save');await idle();const saved=await readDownload('sipi-pair-design.json');await rm(join(downloads,'sipi-pair-design.json'));
    assert.equal(saved.schema,'sipi.template-section/1');assert.equal(saved.parameters.width,goal.result.design.width);
    assert.deepEqual(saved.cross_section,goal.result.document);
    await edit('width',.31);assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#export-comparison").disabled'),true);
    assert.ok(await cdp.evaluate('document.querySelector("#comparison-rows").textContent.includes("Awaiting calculation")'));
    const inputPath=join(profile,'pair-input.json');await writeFile(inputPath,JSON.stringify(saved));
    const root=await cdp.call('DOM.getDocument');const file=await cdp.call('DOM.querySelector',{nodeId:root.root.nodeId,selector:'#file'});
    await cdp.call('DOM.setFileInputFiles',{nodeId:file.nodeId,files:[inputPath]});
    await until(()=>cdp.evaluate('document.querySelector("#file-status").textContent.startsWith("Design opened")'),'reopen');
    assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
    assert.equal(await cdp.evaluate('document.querySelector("#material-label").value'),'Imported design — material not identified');
    await click('calculate');await idle();await click('export');const reopened=await readDownload('sipi-pair-calculation.json');await rm(join(downloads,'sipi-pair-calculation.json'));
    assert.deepEqual(reopened.result.document,saved.cross_section);
    assert.deepEqual(reopened.result.line,goal.result.line);
    records.push({template,kind:'reopened',...reopened});
  }
  await writeFile(join(output,'calculations.json'),JSON.stringify(records,null,2));
  // A rejected target is a search-local failure with actual boundary evidence.
  await edit('target',1000);await click('design');await idle();
  assert.equal(await cdp.evaluate('document.querySelector("#design-status").classList.contains("error")'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false);
  assert.equal(await cdp.evaluate('document.querySelector("#failure").parentElement.id'),'design-output');
  assert.equal(await cdp.evaluate('document.querySelector("#range-feedback").hidden'),false);
  const endpoints=await cdp.evaluate('JSON.parse(document.querySelector("#failure-data").textContent)');
  const shown=await cdp.evaluate('[...document.querySelectorAll("#range-rows tr")].map(row=>[...row.cells].map(cell=>cell.textContent))');
  assert.equal(shown.length,2);
  endpoints.forEach((point,i)=>{assert.equal(Number(shown[i][0]),point.parameter*1e3);assert.equal(shown[i][1],point.impedance.toFixed(3));});
  await edit('target',100);
  assert.equal(await cdp.evaluate('document.querySelector("#range-feedback").hidden'),true);
  await edit('thickness',2);await click('calculate');await idle();
  assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#export-comparison").disabled'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#comparison-results").hidden'),false);
  await edit('thickness',.035);await click('calculate');await click('cancel');await idle();
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#export-comparison").disabled'),true);
  await click('calculate');await idle();assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  // Opening a valid engine document outside the narrow preview must not drop settings.
  const unsupported={...records[0].request,action:'template-document',parameters:{...records[0].request.parameters,tan_delta:.02}};
  const unsupportedSaved=await cdp.evaluate(`(async()=>{const {${webRoot?'BrowserTransport':'LocalTransport'}}=await import('./${webRoot?'browser-transport':'transport'}.js');const t=new ${webRoot?'BrowserTransport':'LocalTransport'}();try{return await t.run(${JSON.stringify(unsupported)});}finally{${webRoot?'await t.close();':''}}})()`);
  const unsupportedPath=join(profile,'unsupported.json');await writeFile(unsupportedPath,unsupportedSaved.document_text);
  const doc=await cdp.call('DOM.getDocument');const fileInput=await cdp.call('DOM.querySelector',{nodeId:doc.root.nodeId,selector:'#file'});
  await cdp.call('DOM.setFileInputFiles',{nodeId:fileInput.nodeId,files:[unsupportedPath]});
  await until(()=>cdp.evaluate('document.querySelector("#file-status").classList.contains("error")'),'unsupported settings refusal');
  assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),true);
  await click('calculate');await idle();assert.equal(await cdp.evaluate('document.querySelector("#result").hidden'),false);
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert.ok(await cdp.evaluate('document.documentElement.scrollWidth<=innerWidth'),'No horizontal mobile overflow');
  assert.ok(await cdp.evaluate('[...document.querySelectorAll("input")].filter(x=>x.offsetParent).every(x=>x.getBoundingClientRect().right<=innerWidth)'),'Visible input fields fit on mobile');
  await writeFile(join(output,'mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await click('clear-a');assert.equal(await cdp.evaluate('document.querySelector("#comparison-results").hidden'),true);
  assert.equal(await cdp.evaluate('document.querySelector("#export-comparison").disabled'),true);
  await edit('material-note','Changed after calculation');assert.equal(await cdp.evaluate('document.querySelector("#keep-a").disabled'),true);
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);
  if(webRoot){assert.ok(workerTargets.length);assert.equal(apiRequests.length,0);}
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',mode:webRoot?'browser-worker':'local-native',checks:['two real pair calculations','two 100 ohm goals and independent refined target','exact geometry/mesh save and reopen','identical reopened line','edit invalidation','invalid geometry refusal','cancel and restart','mobile overflow','no external requests'],records:records.length,errors,remoteRequests,workerTargets},null,2));
  await writeFile(join(output,'comparison-checks.json'),JSON.stringify({status:'passed',checks:['immutable A and exact B exports for both templates','selected search geometry retained','material notes bound to calculation','untrusted labels rendered as text','stale B hidden after edits/failure/cancel','A retained until explicit clear','reopen resets unidentified material context']},null,2));
  console.log('Pair preview browser acceptance passed.');
} catch(error) {
  let application=null;try{application=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent,resultHidden:document.querySelector("#result")?.hidden})');}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({status:'failed',error:error.message,application,errors,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {
  cdp?.ws.close();for(const process of owned.reverse())if(process.exitCode===null)process.kill();
  await pause(400);await rm(profile,{recursive:true,force:true});
}
