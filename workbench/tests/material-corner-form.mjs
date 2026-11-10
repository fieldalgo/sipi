import assert from 'node:assert/strict';
import {materialCornerSettings,applyMaterialCornerSettings,applyMaterialSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';
const original=structuredClone(SAVED_EXAMPLES.find(x=>x.id==='corner-study').document);
let checks=0;
for(const reverse of [false,true]){
 const doc=structuredClone(original);if(reverse)doc.sampling.variables.reverse();const before=JSON.stringify(doc),settings=materialCornerSettings(doc);
 assert.equal(settings.kind,'corners');assert.match(settings.description,new RegExp('variable 1 '+(reverse?'y: axis2':'x: axis1')));checks++;
 const drafts=Object.fromEntries(Object.entries(settings.values).map(([k,v])=>[k,String(v)]));assert.deepEqual(applyMaterialCornerSettings(doc,drafts),doc);checks++;
 const input={lowerFirst:'2.8',upperFirst:'3.4',lowerSecond:'4.3',upperSecond:'5.2',frequency:'2e8',count:'ignored',seed:'ignored'};
 const expected=structuredClone(doc);Object.assign(expected.sampling.variables[0],{lower:2.8,upper:3.4});Object.assign(expected.sampling.variables[1],{lower:4.3,upper:5.2});expected.material_evaluation.frequency_hz=2e8;
 assert.deepEqual(applyMaterialSettings(doc,input),expected);assert.equal(JSON.stringify(doc),before);assert.deepEqual(Object.keys(expected.sampling).sort(),['kind','variables']);checks++;
 for(const [key,value] of [['lowerFirst',''],['lowerFirst','NaN'],['lowerFirst','0x10'],['lowerFirst','1e999'],['lowerFirst','8'],['upperFirst','1'],['lowerSecond','8'],['upperSecond','1'],['frequency','-1']]){
  assert.throws(()=>applyMaterialSettings(doc,{...drafts,[key]:value}));assert.equal(JSON.stringify(doc),before);checks++;
 }
 assert.equal(applyMaterialSettings(doc,{...drafts,lowerFirst:'-.5'}).sampling.variables[0].lower,-.5);checks++;
}
for(const change of [d=>d.schema='future/1',d=>d.sampling.kind='normal',d=>d.quantity='future',d=>d.sampling.variables.pop(),d=>d.sampling.variables.push({...d.sampling.variables[0]}),d=>d.sampling.variables[1].name='x',d=>d.material_variables.y.path=['axis1','parameters','eps_r'],d=>d.material_variables.y.region='other',d=>d.material_variables.y.path=['angle_rad'],d=>d.material_evaluation.materials.dielectric.parameters.axis2.kind='debye',d=>d.sampling.variables[0].lower=null]){
 const copy=structuredClone(original);change(copy);assert.equal(materialCornerSettings(copy),null);checks++;
}
for(const item of SAVED_EXAMPLES.filter(x=>x.id!=='corner-study')){assert.equal(materialCornerSettings(item.document),null);checks++;}
console.log(JSON.stringify({status:'passed',checks}));
