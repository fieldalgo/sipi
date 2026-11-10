// Use recorded real executions; no solver or replacement values in the view.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {materialResultView} from '../ui/material-results.js';
const fixtures=JSON.parse(await readFile(process.argv[2],'utf8'));
const mesh=JSON.parse(await readFile(process.argv[3],'utf8')).execution;
let checks=0;
for(const {name,execution} of fixtures){
  const before=JSON.stringify(execution),view=materialResultView(execution);
  assert.equal(view.failed,true);assert.match(view.title,/not accepted/);assert.ok(view.note.includes(execution.error.message));
  assert.deepEqual(view.tables[2].rows,execution.error.history.map((row,i)=>[i,row.stage,row.parameter,row.value]));
  assert.equal(JSON.stringify(execution),before);checks++;
  if(name==='refinement'){assert.equal(view.tables[2].rows.at(-1)[1],'refinement');checks++;}
  for(const change of [v=>v.schema='future/1',v=>v.input.schema='future/1',v=>v.status='complete',v=>v.result={},
    v=>v.error.type='UnknownError',v=>v.error.unit='F/m',v=>v.error.message=null,v=>v.error.history=null,
    v=>v.error.history[0].value=null,v=>v.error.history[0].value=Infinity,v=>v.error.history[0].parameter=NaN,
    v=>v.error.history[0].stage='unknown',v=>v.error.history[0].stage='refinement',v=>v.error.parameter=false,
    v=>v.input.target_ohm=null,v=>v.input.bounds=[4,2]]){
    const copy=structuredClone(execution);change(copy);assert.equal(materialResultView(copy),null);checks++;
  }
}
const view=materialResultView(mesh);assert.equal(view.failed,true);assert.match(view.note,/0 completed evaluations/);
assert.deepEqual(view.tables.at(-1).rows,[[1,'search',.0002,null,'MeshSizeLimitError']]);assert.equal(view.tables.length,3);checks++;
for(const change of [v=>v.error.attempts=2,v=>v.error.stage='unknown',v=>v.error.input.schema='future/1',v=>v.error.cause_type=null,
  v=>v.error.history=[{parameter:.0002,value:50,stage:'refinement'}]]){
  const copy=structuredClone(mesh);change(copy);assert.equal(materialResultView(copy),null);checks++;
}
console.log(JSON.stringify({status:'passed',checks}));
