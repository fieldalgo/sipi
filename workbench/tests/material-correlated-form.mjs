// Correlation is an explicit input distribution parameter, not a sample statistic.
import assert from 'node:assert/strict';
import {materialCorrelatedSettings,applyMaterialCorrelatedSettings,applyMaterialSettings} from '../ui/material-goal-form.js';
import {SAVED_EXAMPLES} from '../ui/saved-examples.js';
const original=SAVED_EXAMPLES.find(e=>e.id==='correlated-study').document;
const before=JSON.stringify(original),settings=materialCorrelatedSettings(original);
const drafts=Object.fromEntries(Object.entries(settings.values).map(([key,value])=>[key,String(value)]));
let checks=0;
assert.equal(settings.kind,'correlated');assert.equal(Object.keys(settings.values).length,8);assert.deepEqual(applyMaterialCorrelatedSettings(original,drafts),original);checks++;
const edited=applyMaterialSettings(original,{meanFirst:'3.2',stdFirst:'.2',meanSecond:'4.8',stdSecond:'.3',correlation:'-.4',count:'6',seed:'17',frequency:'2e8'});
const expected=structuredClone(original);expected.sampling.variables[0].mean=3.2;expected.sampling.variables[0].std=.2;expected.sampling.variables[1].mean=4.8;expected.sampling.variables[1].std=.3;
expected.sampling.correlation=[[1,-.4],[-.4,1]];expected.sampling.count=6;expected.sampling.seed=17;expected.material_evaluation.frequency_hz=2e8;
assert.deepEqual(edited,expected);assert.equal(JSON.stringify(original),before);checks++;
for(const [key,value] of [['meanFirst',''],['meanSecond',' '],['meanFirst','NaN'],['stdFirst','Infinity'],['meanSecond','0x10'],['meanFirst','1e999'],
  ['stdFirst','0'],['stdSecond','-1'],['correlation','-1.01'],['correlation','1.01'],['count','1'],['count','129'],['count','3.5'],['seed','-1'],['seed','4294967296'],['seed','2.5'],['frequency','-1']]){
  assert.throws(()=>applyMaterialCorrelatedSettings(original,{...drafts,[key]:value}));assert.equal(JSON.stringify(original),before);checks++;
}
for(const [key,value] of [['meanFirst','-2'],['meanSecond','0'],['correlation','-1'],['correlation','0'],['correlation','1'],['count','2'],['count','128'],['seed','0'],['seed','4294967295'],['frequency','0']]){
  const result=applyMaterialCorrelatedSettings(original,{...drafts,[key]:value});assert.equal(materialCorrelatedSettings(result).values[key],Number(value));assert.equal(result.sampling.correlation[0][1],result.sampling.correlation[1][0]);checks++;
}
const reversed=structuredClone(original);reversed.sampling.variables.reverse();assert.match(materialCorrelatedSettings(reversed).description,/variable 1 y: axis2/);
const changed=applyMaterialCorrelatedSettings(reversed,{...drafts,meanFirst:'5.2',meanSecond:'3.4'});assert.equal(changed.sampling.variables[0].name,'y');assert.equal(changed.sampling.variables[0].mean,5.2);assert.equal(changed.sampling.variables[1].name,'x');assert.equal(changed.sampling.variables[1].mean,3.4);assert.deepEqual(changed.material_variables,original.material_variables);checks++;
for(const mutate of [d=>d.schema='future/1',d=>d.sampling.kind='uniform',d=>d.sampling.correlation=[[1]],d=>d.sampling.correlation[0][0]=.9,
  d=>d.sampling.correlation[0][1]=-.2,d=>d.sampling.correlation=[[1,1.1],[1.1,1]],d=>d.sampling.correlation[0][1]=null,
  d=>d.sampling.variables.pop(),d=>d.sampling.variables[1].name=d.sampling.variables[0].name,d=>d.material_variables.extra={},
  d=>d.material_variables.y.path=['axis1','parameters','eps_r'],d=>d.material_variables.y.path=['axis2','parameters','tan_delta'],
  d=>d.material_evaluation.materials.dielectric.schema='future/1',d=>d.material_evaluation.materials.dielectric.parameters.axis2.kind='debye',
  d=>d.sampling.seed=null,d=>d.sampling.variables[0].mean=null]){
  const doc=structuredClone(original);mutate(doc);assert.equal(materialCorrelatedSettings(doc),null);assert.throws(()=>applyMaterialCorrelatedSettings(doc,drafts));checks++;
}
for(const example of SAVED_EXAMPLES.filter(e=>e.id!=='correlated-study')){assert.equal(materialCorrelatedSettings(example.document),null);checks++;}
console.log(JSON.stringify({status:'passed',checks}));
