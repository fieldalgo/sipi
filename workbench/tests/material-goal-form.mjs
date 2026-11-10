// Input transformation checks, independent of browser controls and solvers.
import assert from 'node:assert/strict';
import {materialGoalSettings,applyMaterialGoalSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';

let checks=0;
for(const id of ['constant-target','debye-target']){
  const original=SAVED_EXAMPLES.find(item=>item.id===id).document;
  const before=JSON.stringify(original),settings=materialGoalSettings(original);
  const drafts=Object.fromEntries(Object.entries(settings.values).map(([key,value])=>[key,String(value)]));
  assert.deepEqual(applyMaterialGoalSettings(original,drafts),original);checks++;
  const changed=applyMaterialGoalSettings(original,{target:'51',tolerance:'1',lower:'2.5',upper:'7.5',frequency:'2e8',budget:'48'});
  const expected=structuredClone(original);expected.target_ohm=51;expected.bounds=[2.5,7.5];expected.material_evaluation.frequency_hz=2e8;expected.max_evaluations=48;
  assert.deepEqual(changed,expected);assert.equal(JSON.stringify(original),before);checks++;
  for(const [field,value] of [['target',''],['target',' '],['target','NaN'],['target','Infinity'],['target','0x20'],['target','1e999'],
    ['target','0'],['tolerance','-1'],['lower','0'],['lower','9'],['upper','1'],['frequency','-1'],['budget','2'],['budget','129'],['budget','3.5']]){
    assert.throws(()=>applyMaterialGoalSettings(original,{...drafts,[field]:value}));assert.equal(JSON.stringify(original),before);checks++;
  }
}
for(const example of SAVED_EXAMPLES.filter(item=>!['constant-target','debye-target'].includes(item.id))){
  assert.equal(materialGoalSettings(example.document),null);checks++;
}
for(const mutate of [d=>d.schema='future/1',d=>d.material_variables.material.path=['tan_delta'],d=>d.material_variables.extra={},d=>d.material_evaluation.materials.dielectric.schema='future/1',d=>d.bounds=[null,8]]){
  const doc=structuredClone(SAVED_EXAMPLES[1].document);mutate(doc);assert.equal(materialGoalSettings(doc),null);checks++;
}
console.log(JSON.stringify({status:'passed',checks}));
