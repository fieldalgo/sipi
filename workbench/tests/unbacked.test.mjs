import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, editableParameters, parameterFields, scales, schematic, studyFields, isPair, isCoplanar, isUnbacked} from '../ui/model.js';
const name='unbacked_coplanar';
const original={width:.0005000000000123456,substrate_height:.0005,thickness:.000035,top_width:.0004,gap:.0002,ground_width:.001,eps_r:4,tan_delta:.01,air_height:.006,lower_air_height:.006000000000123456,box_width:.012};
function form(p,unit) {
 const values={profile:'tapered',box_mode:'fixed',air_mode:'fixed',lower_air_mode:p.lower_air_height==null?'auto':'fixed'},si={};
 for(const [id,key] of Object.entries(parameterFields(name))){if(p[key]==null)continue;if(['eps_r','tan_delta'].includes(id))values[id]=String(p[key]);else{si[id]=p[key];values[id]=String(Number((p[key]/scales[unit]).toPrecision(10)));}}
 return {values,si};
}
test('unbacked preview has lower air, no backplane and rectangular side grounds',()=>{
 assert.ok(isCoplanar(name)&&isUnbacked(name)&&!isPair(name));
 for(const lower of [undefined,.006]){
  const p={...original,lower_air_height:lower}, m=schematic(name,p),h=lower??.005;
  assert.deepEqual(m.layers.map(x=>x.name),['lower_air','substrate','air']);assert.equal(m.layers[0].thickness,h);
  assert.equal(m.box.bottom,'open');assert.equal(m.box.top,'open');assert.equal(m.box.sides,'open');
  assert.ok(m.traces.every(t=>t.y===h+.0005));assert.equal(m.traces.filter(t=>t.ground).length,2);
  assert.ok(m.traces.filter(t=>t.ground).every(t=>t.width===.001&&t.top_width===t.width));
 }
});
test('exact lower air survives units and explicit reset without changing other inputs',()=>{
 for(const shape of ['fixed','omitted','null'])for(const unit of ['mm','µm','mil']){
  const p={...original};if(shape==='omitted')delete p.lower_air_height;if(shape==='null')p.lower_air_height=null;
  const {values,si}=form(p,unit);
  assert.deepEqual(editableParameters(name,values,unit,p,new Set(),si),p);
  values.lower_air_mode='fixed';si.lower_air_height=.008000000000123456;values.lower_air_height=String(si.lower_air_height/scales[unit]);
  assert.deepEqual(editableParameters(name,values,unit,p,new Set(['lower_air_mode']),si),{...p,lower_air_height:si.lower_air_height});
  values.lower_air_mode='auto';values.lower_air_height='';si.lower_air_height=NaN;
  assert.deepEqual(editableParameters(name,values,unit,p,new Set(['lower_air_mode']),si),{...p,lower_air_height:null});
 }
});
test('lower air rejects blank/invalid fixed values but stays inactive on other templates',()=>{
 const {values}=form(original,'mm');
 for(const bad of ['',0,-1,'NaN','Infinity'])assert.throws(()=>parameters(name,{...values,lower_air_height:bad},'mm'));
 assert.throws(()=>parameters(name,{...values,lower_air_mode:'other'},'mm'));
 const inactive={...values,lower_air_mode:'other',lower_air_height:'-1'};
 for(const template of ['microstrip','grounded_coplanar'])assert.ok(!Object.hasOwn(parameters(template,inactive,'mm'),'lower_air_height'));
});
test('outer air is a convergence control, not a manufacturing study variable',()=>{
 const fields=studyFields(name,original);assert.equal(fields.gap,'Bottom gap');assert.equal(fields.ground_width,'Ground width');
 for(const key of ['lower_air_height','air_height','box_width','ground_gap'])assert.ok(!Object.hasOwn(fields,key));
});
