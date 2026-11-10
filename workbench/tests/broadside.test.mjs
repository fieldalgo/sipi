import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters,editableParameters,parameterFields,scales,schematic,studyFields,isPair,isStripline,isCoplanar} from '../ui/model.js';
const name='broadside_stripline';
const p={width:.0003000000000123456,gap:.0002000000000123456,plane_spacing:.001,thickness:.000035,offset:-.0001000000000123456,eps_r:4,tan_delta:.02,box_width:.006};
function form(unit='mm',offset=p.offset){
 const si={width:p.width,gap:p.gap,height:p.plane_spacing,thickness:p.thickness,offset,box_width:p.box_width};
 const values={profile:'rectangular',eps_r:4,tan_delta:.02,box_mode:'fixed',air_mode:'fixed',air_height:'invalid',placement:'fixed',trace_height:'invalid'};
 for(const [key,value] of Object.entries(si))values[key]=String(Number((value/scales[unit]).toPrecision(10)));
 return {values,si};
}
test('vertical pair uses positive copper and signed finite offset',()=>{
 assert.ok(isPair(name)&&isStripline(name)&&!isCoplanar(name));
 for(const offset of [-.0001,0,.0001]){
  const {values}=form('mm',offset);const out=parameters(name,values,'mm');
  assert.equal(out.offset,offset);assert.ok(out.thickness>0);assert.equal('top_width' in out,false);assert.equal('trace_height' in out,false);assert.equal('air_height' in out,false);
 }
 for(const invalid of ['',undefined,null,true,'NaN','Infinity'])assert.throws(()=>parameters(name,{...form().values,offset:invalid},'mm'),/offset/);
 for(const thickness of ['0',0,-1,''])assert.throws(()=>parameters(name,{...form().values,thickness},'mm'),/thickness/);
 assert.throws(()=>parameters(name,{...form().values,profile:'tapered',top_width:.2},'mm'),/rectangular/);
});
test('exact negative and zero offsets survive unit cycles and unrelated edits',()=>{
 for(const offset of [p.offset,0])for(const unit of ['µm','mil','mm','mil','mm']){
  const original={...p,offset};const {values,si}=form(unit,offset);
  assert.deepEqual(editableParameters(name,values,unit,original,new Set(),si),original);
  assert.deepEqual(editableParameters(name,values,unit,original,new Set(['profile']),si),original);
  si.offset=.0001234567890123456;values.offset=String(si.offset/scales[unit]);
  assert.deepEqual(editableParameters(name,values,unit,original,new Set(['offset']),si),{...original,offset:si.offset});
 }
 assert.equal(parameterFields(name).offset,'offset');
 assert.equal(Object.hasOwn(parameterFields('coupled_stripline'),'offset'),false);
});
test('schematic retains vertical metal-face gap and signed upper-minus-lower offset',()=>{
 for(const offset of [-.0002,0,.0002]){
  const d=schematic(name,{...p,offset}),[lower,upper]=d.traces;
  assert.equal(d.box.top,'ground');assert.equal(d.box.bottom,'ground');assert.equal(d.layers.length,1);
  assert.equal(lower.x,-offset/2);assert.equal(upper.x,offset/2);
  assert.equal(lower.y,p.plane_spacing/2-p.gap/2-p.thickness);assert.equal(upper.y,p.plane_spacing/2+p.gap/2);
  assert.ok(Math.abs(upper.y-lower.y-lower.thickness-p.gap)<1e-18);
  assert.equal(lower.top_width,p.width);assert.equal(upper.top_width,p.width);
 }
 const fields=studyFields(name,p);assert.equal(fields.gap,'Vertical metal-face gap');assert.equal(fields.offset,'Horizontal offset');assert.equal('trace_height' in fields,false);
});
test('prior forms ignore the inactive signed offset field',()=>{
 const values={...form().values,offset:'invalid',placement:'centred'};
 const without={...values};delete without.offset;
 assert.deepEqual(parameters('coupled_stripline',values,'mm'),parameters('coupled_stripline',without,'mm'));
 assert.equal(studyFields('coupled_stripline',{width:.0003,gap:.0002}).gap,'Bottom gap');
});
