// Normal input editing keeps the sampler, bindings and unbounded sample domain.
import assert from 'node:assert/strict';
import {materialNormalSettings,applyMaterialNormalSettings,applyMaterialSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';
const constant=SAVED_EXAMPLES.find(e=>e.id==='normal-study').document;
const debye=structuredClone(constant);debye.material_evaluation.materials.dielectric=structuredClone(SAVED_EXAMPLES.find(e=>e.id==='debye-target').document.material_evaluation.materials.dielectric);debye.material_variables.dk.path=['strengths',0];
let checks=0;
for(const original of [constant,debye]){
  const before=JSON.stringify(original),settings=materialNormalSettings(original);
  assert.equal(settings.kind,'normal');assert.equal(Object.keys(settings.values).length,5);
  const drafts=Object.fromEntries(Object.entries(settings.values).map(([key,value])=>[key,String(value)]));
  assert.deepEqual(applyMaterialNormalSettings(original,drafts),original);checks++;
  const edited=applyMaterialSettings(original,{mean:'2',std:'2',count:'4',seed:'9',frequency:'1e8'});
  const expected=structuredClone(original);expected.sampling.count=4;expected.sampling.variables[0].mean=2;expected.sampling.variables[0].std=2;
  assert.deepEqual(edited,expected);assert.equal(JSON.stringify(original),before);checks++;
  for(const [key,value] of [['mean',''],['mean',' '],['mean','NaN'],['std','Infinity'],['mean','0x10'],['mean','1e999'],['std','0'],['std','-1'],
    ['count','1'],['count','129'],['count','3.5'],['seed','-1'],['seed','4294967296'],['seed','2.5'],['frequency','-1']]){
    assert.throws(()=>applyMaterialNormalSettings(original,{...drafts,[key]:value}));assert.equal(JSON.stringify(original),before);checks++;
  }
  for(const [key,value] of [['mean','-2'],['mean','0'],['count','2'],['count','128'],['seed','0'],['seed','4294967295'],['frequency','0']]){
    const result=applyMaterialNormalSettings(original,{...drafts,[key]:value});assert.equal(materialNormalSettings(result).values[key],Number(value));checks++;
  }
}
for(const example of SAVED_EXAMPLES.filter(e=>e.id!=='normal-study')){assert.equal(materialNormalSettings(example.document),null);checks++;}
for(const mutate of [d=>d.schema='future/1',d=>d.sampling.kind='uniform',d=>d.sampling.correlation=[[.5]],d=>d.sampling.correlation=[[1,0]],
  d=>d.sampling.variables.push({...d.sampling.variables[0],name:'other'}),d=>d.material_variables.other={},d=>d.material_variables.dk.path=['tan_delta'],
  d=>d.sampling.seed=null,d=>d.sampling.variables[0].mean=null,d=>d.material_evaluation.materials.dielectric.kind='unknown']){
  const doc=structuredClone(constant);mutate(doc);assert.equal(materialNormalSettings(doc),null);assert.throws(()=>applyMaterialNormalSettings(doc,{}));checks++;
}
console.log(JSON.stringify({status:'passed',checks}));
