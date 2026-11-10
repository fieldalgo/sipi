import test from 'node:test';
import assert from 'node:assert/strict';
import {editableParameters, parameters, scales, schematic, studyFields, isStripline, isPair} from '../ui/model.js';

const p={width:.0003000000000123456, plane_spacing:.001, trace_height:.0003000000000123456,
 thickness:.000035, eps_r:4, tan_delta:0, top_width:null, box_width:.006};
function form(unit) {
 const si={width:p.width,height:p.plane_spacing,trace_height:p.trace_height,thickness:p.thickness};
 const values={profile:'rectangular',eps_r:'4',tan_delta:'0',box_mode:'auto'};
 for(const [key,value] of Object.entries(si))values[key]=String(Number((value/scales[unit]).toPrecision(10)));
 return {values,si};
}
test('offset single remains a distinct one-signal two-plane contract',()=>{
 const {values}=form('mm');
 assert.ok(isStripline('offset_stripline'));assert.equal(isPair('offset_stripline'),false);
 const fixed=parameters('offset_stripline',values,'mm'), model=schematic('offset_stripline',fixed);
 assert.equal(model.traces.length,1);assert.equal(model.traces[0].name,'signal');
 assert.equal(model.traces[0].y,fixed.trace_height);assert.equal(model.box.top,'ground');
 assert.equal(model.layers.length,1);assert.ok(!('substrate_height' in fixed) && !('air_height' in fixed));
 assert.equal(studyFields('offset_stripline',p).trace_height,'Bottom-face height');
 const centred=parameters('stripline',values,'mm');
 assert.ok(!('trace_height' in centred));assert.equal(schematic('stripline',centred).traces[0].y,(p.plane_spacing-p.thickness)/2);
});
test('exact saved offset survives display units and changes only on explicit edits',()=>{
 for(const unit of ['mm','µm','mil','µm','mm']) {
  const {values,si}=form(unit);
  assert.deepEqual(editableParameters('offset_stripline',values,unit,p,new Set(),si),p);
  si.trace_height=.0004000000000123456;values.trace_height=String(si.trace_height/scales[unit]);
  assert.deepEqual(editableParameters('offset_stripline',values,unit,p,new Set(['trace_height']),si),{...p,trace_height:si.trace_height});
  values.height=String(.0012/scales[unit]);si.height=.0012;
  assert.deepEqual(editableParameters('offset_stripline',values,unit,p,new Set(['height']),si),{...p,plane_spacing:.0012});
 }
});
test('a required fixed height cannot be omitted or reset to an automatic placement',()=>{
 const {values}=form('mm');values.placement='centred';
 assert.ok(parameters('offset_stripline',values,'mm').trace_height>0);
 for(const value of [undefined,null,'',0,-1,'NaN']) {
  assert.throws(()=>parameters('offset_stripline',{...values,trace_height:value},'mm'),/positive/);
 }
});
