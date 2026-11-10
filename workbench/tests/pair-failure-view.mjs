// Recorded solver failures drive the view; malformed shapes fall back to raw JSON.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {materialResultView} from '../ui/material-results.js';
const fixtures=JSON.parse(await readFile(process.argv[2],'utf8'));
let checks=0;
for(const {name,execution} of fixtures){
  const before=JSON.stringify(execution),view=materialResultView(execution);
  assert.equal(view.failed,true);assert.match(view.title,/targets not accepted/);assert.ok(view.note.includes(execution.error.message));
  assert.deepEqual(view.tables[0].rows,[['Differential',execution.input.targets_ohm.z_diff,execution.input.tolerances_ohm.z_diff],['Common',execution.input.targets_ohm.z_common,execution.input.tolerances_ohm.z_common]]);
  assert.deepEqual(view.tables[1].rows,execution.input.variables.map(v=>[v.name,...v.bounds]));
  assert.deepEqual(view.tables[2].rows,execution.error.history.map((row,i)=>[i,row.stage,...row.parameters,...row.impedances_ohm]));
  assert.deepEqual(view.tables[3].rows,[[execution.error.stage,...execution.error.failed_parameters]]);
  assert.equal(JSON.stringify(execution),before);checks++;
  if(name==='budget'){assert.match(view.tables[3].caption,/before this evaluation/);assert.equal(view.tables[2].rows.length,1);checks++;}
  if(name==='refinement'){assert.equal(view.tables[2].rows.at(-1)[1],'refinement');checks++;}
  for(const mutate of [v=>v.schema='future/1',v=>v.input.schema='future/1',v=>v.status='complete',v=>v.result={},
    v=>v.error.type='UnknownError',v=>v.error.unit='F/m',v=>v.error.message=null,v=>v.error.stage='optimizer',v=>v.error.stage='search/extraction',
    v=>v.error.cause_type='UnknownError',v=>v.error.history=[],v=>v.error.history=null,v=>v.error.attempts++,
    v=>v.error.history[0].impedances_ohm=[100,null],v=>v.error.history[0].impedances_ohm=[Infinity,34],
    v=>v.error.history[0].parameters=[3,NaN],v=>v.error.history[0].parameters=[1,3],v=>v.error.history[0].stage='unknown',
    v=>v.error.history[0].stage='refinement',v=>v.error.failed_parameters=null,v=>v.error.failed_parameters=[1,3],
    v=>v.error.quantities.reverse(),v=>v.input.targets_ohm.z0=50,v=>v.input.tolerances_ohm.z_common=0,
    v=>v.input.variables[1].name=v.input.variables[0].name,v=>v.input.variables[0].bounds=[4,2],v=>v.input.max_evaluations=1]){
    const copy=structuredClone(execution);mutate(copy);assert.equal(materialResultView(copy),null);checks++;
  }
}
const refinement=structuredClone(fixtures.find(v=>v.name==='refinement').execution);
refinement.error.history.at(-1).stage='search';assert.equal(materialResultView(refinement),null);checks++;
const mismatched=structuredClone(fixtures.find(v=>v.name==='refinement').execution);
mismatched.error.failed_parameters[0]+=1e-5;assert.equal(materialResultView(mismatched),null);checks++;
console.log(JSON.stringify({status:'passed',checks}));
