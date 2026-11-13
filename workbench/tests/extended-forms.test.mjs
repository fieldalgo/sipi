import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {labels,extendedLabels,scales,lengthFields,parameterFields,editableParameters,studyFields,studyScale,isAsymmetric,isPair,isForwardPair,isBroadside,isLayeredBroadside,usesEngineGeometry} from '../ui/model.js';
const reference=JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/template_section/reference.json',import.meta.url)));
reference.cases.push(...JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/layered_microstrip/inputs.json',import.meta.url))).cases);
reference.cases.push(...JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/asymmetric_layered_microstrip/inputs.json',import.meta.url))).cases);
reference.cases.push(...JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/layered_grounded_coplanar/inputs.json',import.meta.url))).cases);
const cases=Object.fromEntries(reference.cases.map(c=>[c.template,c.resolved_parameters]));
assert.deepEqual(Object.keys(labels).sort(),Object.keys(cases).sort());
assert.equal(Object.keys(labels).length,48);assert.equal(Object.keys(extendedLabels).length,12);
for(const name of Object.keys(extendedLabels)) for(const unit of Object.keys(scales)) test(`${name}: exact ${unit} inputs and active study fields`,()=>{
  const p=cases[name],values={},si={};
  for(const [id,key] of Object.entries(parameterFields(name))) {
    const v=p[key];if(v==null)continue;
    values[id]=String(v/(lengthFields.includes(id)?scales[unit]:1));
    if(lengthFields.includes(id))si[id]=v;
  }
  values.profile=p.top_width==null?'rectangular':'tapered';
  for(const side of ['left','right'])values[side+'_profile']=p[side+'_top_width']==null?'rectangular':'tapered';
  values.placement=p.trace_height==null?'centred':'fixed';
  for(const [mode,key] of [['box_mode','box_width'],['air_mode','air_height'],['lower_air_mode','lower_air_height']])values[mode]=p[key]==null?'auto':'fixed';
  const expected=Object.fromEntries(Object.entries(p).filter(([k,v])=>v!==null));
  assert.deepEqual(editableParameters(name,values,unit,null,new Set(),si),expected);
  assert.deepEqual(editableParameters(name,values,unit,p,new Set(),si),p);
  assert.ok(isPair(name)&&isForwardPair(name)&&usesEngineGeometry(name));
  for(const key of Object.keys(studyFields(name,p)))assert.ok(Object.hasOwn(p,key),key);
  if(isLayeredBroadside(name)){assert.ok(isBroadside(name)&&!isAsymmetric(name));assert.equal(studyScale('gap_eps_r',unit),1);}
});
const html=readFileSync(new URL('../ui/index.html',import.meta.url),'utf8');
assert.deepEqual([...html.matchAll(/data-template="([^"]+)"/g)].map(m=>m[1]).sort(),Object.keys(labels).sort());
