// Settings transformations preserve the complete original sampling contract.
import assert from 'node:assert/strict';
import {materialUniformSettings,applyMaterialUniformSettings,applyMaterialSettings,materialGoalSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';
const constant=structuredClone(SAVED_EXAMPLES.find(item=>item.id==='uniform-study').document);
const debye=structuredClone(constant);
debye.material_evaluation=structuredClone(SAVED_EXAMPLES.find(item=>item.id==='debye-target').document.material_evaluation);
debye.material_variables.dk.path=['strengths',0];
let checks=0;
for(const original of [constant,debye]){
  const before=JSON.stringify(original),settings=materialUniformSettings(original);
  assert.equal(settings.kind,'uniform');assert.equal(materialGoalSettings(original),null);checks++;
  const drafts=Object.fromEntries(Object.entries(settings.values).map(([key,value])=>[key,String(value)]));
  assert.deepEqual(applyMaterialUniformSettings(original,drafts),original);checks++;
  const changed=applyMaterialSettings(original,{lower:'1',upper:'5',frequency:'2e8',count:'5',seed:'17',target:'ignored'});
  const expected=structuredClone(original);expected.sampling.variables[0].lower=1;expected.sampling.variables[0].upper=5;expected.sampling.count=5;expected.sampling.seed=17;expected.material_evaluation.frequency_hz=2e8;
  assert.deepEqual(changed,expected);assert.equal(JSON.stringify(original),before);checks++;
  for(const [key,value] of [['lower',''],['lower',' '],['lower','NaN'],['lower','0x10'],['lower','1e999'],['lower','6'],
    ['upper','1'],['frequency','-1'],['count','1'],['count','129'],['count','2.5'],['count','Infinity'],['seed','-1'],['seed','4294967296'],['seed','2.5']]){
    assert.throws(()=>applyMaterialSettings(original,{...drafts,[key]:value}));assert.equal(JSON.stringify(original),before);checks++;
  }
  // Corner/material validity belongs to the engine, not a silent UI clamp.
  const proposal=applyMaterialSettings(original,{...drafts,lower:'-.5',upper:'2'});
  assert.deepEqual([proposal.sampling.variables[0].lower,proposal.sampling.variables[0].upper],[-.5,2]);checks++;
}
for(const change of [d=>d.schema='future/1',d=>d.sampling.kind='normal',d=>d.sampling.variables.push({...d.sampling.variables[0]}),
  d=>d.material_variables.extra={},d=>d.material_variables.dk.path=['tan_delta'],d=>d.material_evaluation.materials.dielectric.schema='future/1',d=>d.sampling.count=null,d=>d.sampling.seed=null]){
  const copy=structuredClone(constant);change(copy);assert.equal(materialUniformSettings(copy),null);checks++;
}
for(const id of ['rlc','material-sweep','constant-target','debye-target','pair-target','correlated-study','normal-study']){
  assert.equal(materialUniformSettings(SAVED_EXAMPLES.find(item=>item.id===id).document),null);checks++;
}
for(const seed of ['0','4294967295']){const original=structuredClone(constant),settings=materialUniformSettings(original),drafts=Object.fromEntries(Object.entries(settings.values).map(([k,v])=>[k,String(v)]));assert.equal(applyMaterialSettings(original,{...drafts,seed}).sampling.seed,Number(seed));checks++;}
console.log(JSON.stringify({status:'passed',checks}));
