import {spawn} from 'node:child_process';
import {mkdtemp,readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import assert from 'node:assert/strict';
import {assertRegisteredForms} from './registered-forms.mjs';
const output=resolve(process.argv[2]); await mkdir(output,{recursive:true});
const webRoot=process.argv[3] ? resolve(process.argv[3]) : null;
const profile=await mkdtemp(join(tmpdir(),'sipi-extended-'));
const errors=[],remoteRequests=[],apiRequests=[],workerTargets=[],owned=[];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn,label,timeout=120000){const end=Date.now()+timeout;while(Date.now()<end){const v=await fn();if(v)return v;await pause(120);}throw Error('Timed out: '+label);}
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
let cdp,serverLog='';const checks=[];
try {
  const args=webRoot?['-u','-m','http.server','0','--bind','127.0.0.1','--directory',webRoot]:['-u','workbench/desktop/main.py','--no-browser'];
  const server=spawn(process.env.SIPI_PYTHON,args,{env:{...process.env,OPENBLAS_NUM_THREADS:'1'},stdio:['ignore','pipe','pipe']});owned.push(server);
  server.stdout.on('data',d=>serverLog+=d);server.stderr.on('data',d=>serverLog+=d);
  const url=await until(()=>{if(server.exitCode!==null)throw Error('Server exited before binding');return serverLog.match(webRoot?/http:\/\/127\.0\.0\.1:\d+\//:/http:\/\/127\.0\.0\.1:\d+\/#token=[\w-]+/)?.[0]},'server');
  const chrome=spawn(process.env.CHROME||'/usr/bin/chromium',['--headless=new','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-background-networking','--no-first-run','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});owned.push(chrome);
  const port=await until(async()=>{try{return (await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]}catch{return null}},'browser');
  const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();cdp=new CDP(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
  await cdp.call('Runtime.enable');await cdp.call('Network.enable');await cdp.call('Page.enable');
  await cdp.call('Page.navigate',{url});
  await until(()=>cdp.evaluate('document.readyState==="complete" && !!document.querySelector("#network-input-save")'),'page');
  await cdp.evaluate(`window.downloads=[];const previous=URL.createObjectURL;URL.createObjectURL=b=>{b.text().then(text=>window.downloads.push(text));return previous(b)};`);
  await cdp.evaluate(`window.completedResults=[];
    const observed=new WeakSet(),post=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(m,...rest){if(!observed.has(this)){observed.add(this);this.addEventListener('message',e=>{if(e.data.status==='complete')window.completedResults.push(e.data.result)})}return post.call(this,m,...rest)};
    const original=window.fetch;window.fetch=(url,options)=>original(url,options).then(async response=>{if(url==='/api/job'&&options?.method==='GET'){const v=await response.clone().json();if(v.status==='complete')window.completedResults.push(v.result)}return response});`);
  const cases=JSON.parse(await readFile(process.env.SIPI_FORM_CASES || process.env.SIPI_EXTENDED_CASES,'utf8'));
  async function load(path){
    const node=await cdp.call('Runtime.evaluate',{expression:'document.querySelector("#file")'});
    await cdp.call('DOM.setFileInputFiles',{objectId:node.result.objectId,files:[path]});
    await until(()=>cdp.evaluate('!document.querySelector("#save-editable").disabled'),'open finished');
    const status=await cdp.evaluate('document.querySelector("#status").textContent');assert.ok(!status.toLowerCase().includes('error'),status);
  }
  async function download(id,raw=false){
    const before=await cdp.evaluate('window.downloads.length');await cdp.evaluate(`document.getElementById(${JSON.stringify(id)}).click()`);
    await until(()=>cdp.evaluate(`window.downloads.length>${before}`),'download '+id);
    await until(()=>cdp.evaluate('!document.querySelector("#save-editable").disabled'),'save finished');
    const text=await cdp.evaluate(`window.downloads[${before}]`);return raw ? text : JSON.parse(text);
  }
  async function click(id){
    await cdp.evaluate(`document.getElementById(${JSON.stringify(id)}).click()`);
    await until(()=>cdp.evaluate('!document.querySelector("#save-editable").disabled'),'action '+id,310000);
    assert.equal(await cdp.evaluate('document.querySelector("#status").classList.contains("error")'),false,await cdp.evaluate('document.querySelector("#status").textContent'));
  }
  async function geometry(doc){
    assert.match(await cdp.evaluate('document.querySelector("#preview-label").textContent'),/Engine geometry/);
    const result=await cdp.evaluate('window.completedResults.at(-1).document');assert.deepEqual(result,JSON.parse(JSON.stringify(doc))); // CDP serializes negative zero as zero.
    assert.equal(await cdp.evaluate('document.querySelectorAll("#cross-section [data-region]").length'),(doc.dielectric_regions??[]).length);
  }
  await assertRegisteredForms(cdp);
  for(const item of cases){
    // Each button must start a valid editable request without a saved file.
    await cdp.evaluate(`document.querySelector('[data-template="${item.name}"]').click()`);
    await click('geometry-inspect');const defaults=await download('save-editable');assert.equal(defaults.template,item.name);
    const choices=await cdp.evaluate('[1,2].map(i=>document.getElementById("study-variable-"+i).value)');assert.ok(choices.every(Boolean));
    await load(item.path);
    for(const unit of ['µm','mil','mm']){
      await cdp.evaluate(`document.querySelector('#unit').value=${JSON.stringify(unit)};document.querySelector('#unit').dispatchEvent(new Event('change',{bubbles:true}));`);
      assert.deepEqual(await download('save-editable'),item.input);
    }
    await click('geometry-inspect');await geometry(item.input.cross_section);
    await load(item.network_path);assert.deepEqual(await download('network-input-save'),item.network_input);
    await click('network-calculate');const result=await cdp.evaluate('window.completedResults.at(-1)');
    if(item.direct.line.forward_launch){
      assert.equal(result.line.forward_launch.quantity,'z_diff_forward');assert.ok(!('z_diff' in result.line));
      assert.equal(await cdp.evaluate('document.querySelector("#eps-metric").hidden && document.querySelector("#delay-metric").hidden'),true);
    } else {
      const key=item.direct.line.names.length===1?'z0':'z_diff';
      assert.ok(Math.abs(result.line[key]-item.direct.line[key])<=1e-9*item.direct.line[key]);
      assert.ok(!('forward_launch' in result.line));
      assert.equal(await cdp.evaluate('document.querySelector("#uniform-height-field").hidden && !document.querySelector("#layered-height-fields").hidden'),true);
      assert.match(await cdp.evaluate('document.querySelector("#layered-height-note").textContent'),/Both substrate heights exclude copper/);
    }
    for(const key of ['C','C0','C_loss','L'])for(let i=0;i<item.direct.line.names.length;i++)for(let j=0;j<item.direct.line.names.length;j++)assert.ok(Math.abs(result.line[key][i][j]-item.direct.line[key][i][j])<=1e-9*Math.max(1e-30,Math.abs(item.direct.line[key][i][j])));
    const text=await download('touchstone-save',true);
    const numbers=t=>t.split('[Network Data]')[1].split('[End]')[0].trim().split(/\s+/).map(Number);
    const actual=numbers(text),expected=numbers(item.direct.network.touchstone);assert.equal(actual.length,expected.length);assert.ok(actual.every(Number.isFinite));
    actual.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<=1e-10*Math.max(1,Math.abs(expected[i]))));
    assert.deepEqual(await download('network-input-save'),item.network_input);
    checks.push({template:item.name,status:'passed',networkNumbers:actual.length,units:3});
  }
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  const layout=await cdp.evaluate(`({width:innerWidth,scroll:document.documentElement.scrollWidth,buttons:[...document.querySelectorAll('[data-template]')].map(b=>{const r=b.getBoundingClientRect();return {kind:b.dataset.template,height:r.height,left:r.left,right:r.right}})})`);
  assert.ok(layout.scroll<=390,JSON.stringify(layout));for(const r of layout.buttons){assert.ok(r.height>=44&&r.left>=0&&r.right<=390,JSON.stringify(r));}
  await writeFile(join(output,'extended-mobile.png'),Buffer.from((await cdp.call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true})).data,'base64'));
  await cdp.evaluate('document.querySelector("#exit").click()');await until(()=>cdp.evaluate('document.querySelector("#status").textContent.includes("Application closed")'),'close');
  if(!webRoot) await until(()=>server.exitCode===0,'host exit');
  assert.deepEqual(errors,[]);assert.deepEqual(remoteRequests,[]);if(webRoot)assert.deepEqual(apiRequests,[]);
  await writeFile(join(output,'report.json'),JSON.stringify({status:'passed',runtime:webRoot?'worker':'native',checks,layout,errors,remoteRequests,workerTargets},null,2));
} catch(error){
  let state=null;try{state=await cdp?.evaluate('({status:document.querySelector("#status")?.textContent})')}catch{}
  await writeFile(join(output,'failure.json'),JSON.stringify({error:error.message,state,checks,errors,serverLog:serverLog.replace(/#token=[\w-]+/g,'#token=[redacted]')},null,2));throw error;
} finally {cdp?.ws.close();for(const p of owned.reverse())if(p.exitCode===null)p.kill();await pause(400);await rm(profile,{recursive:true,force:true});}
