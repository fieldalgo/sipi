import test from 'node:test';
import assert from 'node:assert/strict';
import {LocalTransport} from '../ui/transport.js';

function deferred() { let resolve; const promise=new Promise(r=>resolve=r); return {promise,resolve}; }
function setup(t, responder) {
  const originals=new Map();
  for(const [key,value] of Object.entries({location:{hash:''},sessionStorage:{getItem:()=> 'test-session'},fetch:responder})) {
    originals.set(key,Object.getOwnPropertyDescriptor(globalThis,key));
    Object.defineProperty(globalThis,key,{value,configurable:true,writable:true});
  }
  t.after(()=>{for(const [key,descriptor] of originals) {if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key];}});
  return new LocalTransport();
}
const response = value => ({ok:true,json:async()=>value});

for (const operation of ['cancel','close']) test(operation+' waits for an unacknowledged start', async t => {
  const started=deferred(), requests=[];
  const transport=setup(t, async (url, options)=>{
    requests.push([url,options.method]);
    if(url==='/api/job' && options.method==='POST') return started.promise;
    return response({status:'cancelled'});
  });
  const run=transport.run({action:'analyze'});
  const cancelled=assert.rejects(run,error=>error.name==='AbortError');
  const stopping=transport[operation]();
  try { assert.deepEqual(requests,[['/api/job','POST']], 'A stop cannot reach the server before its pending start'); }
  finally {started.resolve(response({status:'running'}));await stopping;await cancelled;}
  assert.deepEqual(requests,[['/api/job','POST'],[operation==='cancel'?'/api/cancel':'/api/shutdown','POST']]);
});

test('a cancelled poll does not read a newer job and the next run succeeds', async t => {
  const requests=[];
  const transport=setup(t,async(url,options)=>{requests.push([url,options.method]);return response(options.method==='GET'?{status:'complete',result:{id:'new'}}:{status:'running'});});
  const old=transport.run({id:'old'});
  const cancelled=assert.rejects(old,error=>error.name==='AbortError');
  await new Promise(resolve=>setTimeout(resolve,20));
  await transport.cancel();
  const newer=transport.run({id:'new'});
  await cancelled;
  assert.deepEqual(await newer,{id:'new'});
  assert.equal(requests.filter(([,method])=>method==='GET').length,1);
});
