// Strict setting transformation, variable order and unsupported binding checks.
import assert from 'node:assert/strict';
import {materialPairSettings,applyMaterialPairSettings,applyMaterialSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';
const original=SAVED_EXAMPLES.find(item=>item.id==='pair-target').document;
const before=JSON.stringify(original),settings=materialPairSettings(original);
const drafts=Object.fromEntries(Object.entries(settings.values).map(([key,value])=>[key,String(value)]));
let checks=0;
assert.equal(settings.kind,'pair');assert.equal(Object.keys(settings.values).length,12);
assert.deepEqual(applyMaterialPairSettings(original,drafts),original);checks++;
const edited={...drafts,targetDiff:'101',lowerFirst:'2.2',upperFirst:'5.8',initialFirst:'3.2',lowerSecond:'2.2',upperSecond:'5.8',initialSecond:'3.5',frequency:'2e8'};
const expected=structuredClone(original);expected.targets_ohm.z_diff=101;expected.variables.forEach(v=>v.bounds=[2.2,5.8]);expected.initial=[3.2,3.5];expected.material_evaluation.frequency_hz=2e8;
assert.deepEqual(applyMaterialSettings(original,edited),expected);assert.equal(JSON.stringify(original),before);checks++;
for(const [key,value] of [['targetDiff',''],['targetCommon',' '],['toleranceDiff','NaN'],['toleranceCommon','Infinity'],['targetDiff','0x20'],['targetDiff','1e999'],
  ['targetDiff','0'],['targetCommon','-1'],['toleranceDiff','0'],['toleranceCommon','-1'],['lowerFirst','0'],['lowerSecond','0'],['lowerFirst','7'],['upperSecond','1'],
  ['initialFirst','1'],['initialSecond','7'],['frequency','-1'],['pairBudget','1'],['pairBudget','129'],['pairBudget','2.5']]){
  assert.throws(()=>applyMaterialPairSettings(original,{...drafts,[key]:value}));assert.equal(JSON.stringify(original),before);checks++;
}
for(const [key,value] of [['pairBudget','2'],['pairBudget','128'],['initialFirst','2'],['initialSecond','6'],['frequency','0']]){
  assert.doesNotThrow(()=>applyMaterialPairSettings(original,{...drafts,[key]:value}));checks++;
}
const reversed=structuredClone(original);reversed.variables.reverse();reversed.initial=[3.5,3.2];
assert.match(materialPairSettings(reversed).description,/variable 1 y: axis2/);
const reversedDrafts={...drafts,initialFirst:'4',initialSecond:'5'};
const result=applyMaterialPairSettings(reversed,reversedDrafts);assert.deepEqual(result.initial,[4,5]);assert.deepEqual(result.variables.map(v=>v.name),['y','x']);assert.deepEqual(result.material_variables,original.material_variables);checks++;
for(const mutate of [d=>d.schema='future/1',d=>d.initial=null,d=>d.initial=[3],d=>d.variables.reverse()&&d.variables.pop(),
  d=>d.variables[1].name=d.variables[0].name,d=>d.material_variables.y.path=['axis1','parameters','eps_r'],
  d=>d.material_variables.y.path=['axis2','parameters','tan_delta'],d=>d.material_variables.extra={},
  d=>d.material_evaluation.materials.dielectric.schema='future/1',d=>d.material_evaluation.materials.dielectric.parameters.axis2.kind='debye',
  d=>d.targets_ohm.z0=50,d=>delete d.tolerances_ohm.z_common,d=>d.variables[0].bounds=[null,6],d=>d.initial[1]=null]){
  const doc=structuredClone(original);mutate(doc);assert.equal(materialPairSettings(doc),null);assert.throws(()=>applyMaterialPairSettings(doc,drafts));checks++;
}
for(const example of SAVED_EXAMPLES.filter(item=>item.id!=='pair-target')){assert.equal(materialPairSettings(example.document),null);checks++;}
console.log(JSON.stringify({status:'passed',checks}));
