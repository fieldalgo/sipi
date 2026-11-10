import test from 'node:test';
import assert from 'node:assert/strict';
import {editableParameters, parameters, scales, schematic, studyFields} from '../ui/model.js';

const original={width:.0003000000000123456,gap:.0003,plane_spacing:.001,trace_height:.0003000000000123456,eps_r:4,thickness:.000035,tan_delta:0,top_width:null,box_width:.006};
function form(p,unit='mm') {
  const si={width:p.width,gap:p.gap,height:p.plane_spacing,thickness:p.thickness,trace_height:p.trace_height ?? .0003};
  const values={profile:'rectangular',placement:p.trace_height==null?'centred':'fixed',eps_r:'4',tan_delta:'0',box_mode:'auto'};
  for(const [key,value] of Object.entries(si))values[key]=String(Number((value/scales[unit]).toPrecision(10)));
  return {values,si};
}
test('precise placement survives units and changes only through explicit edits',()=>{
 for(const unit of ['mm','µm','mil','µm','mm']) {
  const {values,si}=form(original,unit);
  assert.deepEqual(editableParameters('coupled_stripline',values,unit,original,new Set(),si),original);
  si.trace_height=.0004000000000123456;values.trace_height=String(Number((si.trace_height/scales[unit]).toPrecision(10)));
  assert.deepEqual(editableParameters('coupled_stripline',values,unit,original,new Set(['trace_height']),si),{...original,trace_height:si.trace_height});
  values.placement='centred';
  const reset=editableParameters('coupled_stripline',values,unit,original,new Set(['placement']),si);
  assert.deepEqual(reset,{...original,trace_height:null});
  assert.ok(!Object.hasOwn(studyFields('coupled_stripline',reset),'trace_height'));
  assert.equal(schematic('coupled_stripline',reset).traces[0].y,(original.plane_spacing-original.thickness)/2);
 }
});
test('fresh centred requests omit height; saved null and untouched fixed values remain exact',()=>{
 for(const p of [{...original,trace_height:null},Object.fromEntries(Object.entries(original).filter(([k])=>k!=='trace_height'))]) {
  const {values,si}=form(p);
  assert.deepEqual(editableParameters('coupled_stripline',values,'mm',p,new Set(),si),p);
  assert.ok(!Object.hasOwn(editableParameters('coupled_stripline',values,'mm',null,new Set(),si),'trace_height'));
  values.placement='fixed';
  const fixed=editableParameters('coupled_stripline',values,'mm',p,new Set(['placement']),si);
  assert.equal(fixed.trace_height,si.trace_height);
  assert.equal(studyFields('coupled_stripline',fixed).trace_height,'Bottom-face height');
  assert.ok(schematic('coupled_stripline',fixed).traces.every(t=>t.y===si.trace_height));
 }
});
test('only coupled stripline uses the placement input; invalid active lengths are rejected',()=>{
 const {values,si}=form(original);values.trace_height='-1';
 assert.throws(()=>parameters('coupled_stripline',values,'mm'),/positive/);
 values.placement='centred';assert.ok(!Object.hasOwn(parameters('coupled_stripline',values,'mm'),'trace_height'));
 values.placement='fixed';
 for(const template of ['stripline','microstrip','coupled_microstrip']) {
  assert.ok(!Object.hasOwn(parameters(template,values,'mm'),'trace_height'));
  assert.ok(!Object.hasOwn(studyFields(template,original),'trace_height'));
 }
 values.placement='unknown';assert.throws(()=>parameters('coupled_stripline',values,'mm'),/Unknown/);
});
