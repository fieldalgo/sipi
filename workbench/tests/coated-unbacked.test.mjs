import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, editableParameters, parameterFields, lengthFields, scales, schematic, studyFields, isPair, isCoplanar, isUnbacked, isCoated} from '../ui/model.js';
for(const paired of [false,true]){
 const name=paired?'coupled_coated_unbacked_coplanar':'coated_unbacked_coplanar';
 const original={width:.0005000000000123456,substrate_height:.0005,thickness:.000035,top_width:.0004,gap:paired?.0003:.0002,ground_width:.001,eps_r:4,tan_delta:.01,coating_height:.0001000000000123456,coating_eps_r:3.500000000000123,coating_tan_delta:.0200000000000123,air_height:.006,lower_air_height:.006000000000123456,box_width:.012,...(paired?{ground_gap:.0002}:{})};
 function form(p,unit){
  const values={profile:'tapered',box_mode:'fixed',air_mode:'fixed',lower_air_mode:p.lower_air_height==null?'auto':'fixed'},si={};
  for(const [id,key] of Object.entries(parameterFields(name))){if(p[key]==null)continue;if(lengthFields.includes(id)){si[id]=p[key];values[id]=String(Number((p[key]/scales[unit]).toPrecision(10)));}else values[id]=String(p[key]);}
  return {values,si};
 }
 test(name+' preview keeps film and lower air separate from metal',()=>{
  assert.ok(isCoated(name)&&isCoplanar(name)&&isUnbacked(name));assert.equal(isPair(name),paired);
  for(const lower of [undefined,.006]){
   const p={...original,lower_air_height:lower},m=schematic(name,p),h=lower??.005;
   assert.deepEqual(m.layers.map(x=>x.name),['lower_air','substrate','planar coating','air']);
   assert.equal(m.layers[0].thickness,h);assert.equal(m.layers[2].thickness,p.coating_height);assert.equal(m.layers[2].eps_r,p.coating_eps_r);
   assert.equal(m.box.bottom,'open');assert.ok(m.traces.every(t=>t.y===h+.0005));
   const signals=m.traces.filter(t=>!t.ground),grounds=m.traces.filter(t=>t.ground);assert.equal(signals.length,paired?2:1);assert.equal(grounds.length,2);
   assert.ok(grounds.every(t=>t.width===p.ground_width&&t.top_width===t.width));
   const right=signals.at(-1),gr=grounds[1];assert.ok(Math.abs(gr.x-gr.width/2-right.x-right.width/2-(paired?p.ground_gap:p.gap))<1e-15);
  }
 });
 test(name+' precise film materials and lower air survive all units',()=>{
  for(const shape of ['fixed','omitted','null'])for(const unit of ['mm','µm','mil']){
   const p={...original};if(shape==='omitted')delete p.lower_air_height;if(shape==='null')p.lower_air_height=null;
   const {values,si}=form(p,unit);assert.deepEqual(editableParameters(name,values,unit,p,new Set(),si),p);
   values.coating_height=String(.00012/scales[unit]);si.coating_height=.00012;
   assert.deepEqual(editableParameters(name,values,unit,p,new Set(['coating_height']),si),{...p,coating_height:.00012});
   values.lower_air_mode='auto';values.lower_air_height='';si.lower_air_height=NaN;
   assert.deepEqual(editableParameters(name,values,unit,p,new Set(['lower_air_mode']),si),{...p,lower_air_height:null});
  }
 });
 test(name+' rejects coating through copper and invalid material inputs',()=>{
  const {values}=form(original,'mm');
  for(const bad of ['',0,.035,.02,'NaN','Infinity'])assert.throws(()=>parameters(name,{...values,coating_height:bad},'mm'));
  assert.throws(()=>parameters(name,{...values,coating_eps_r:0},'mm'));
  assert.throws(()=>parameters(name,{...values,coating_tan_delta:-1},'mm'));
  assert.throws(()=>parameters(name,{...values,lower_air_height:''},'mm'));
 });
 test(name+' hidden film and lower-air fields stay inactive on microstrip',()=>{
  const {values}=form(original,'mm');const p=parameters('microstrip',{...values,coating_height:-1,coating_eps_r:0,coating_tan_delta:-1,lower_air_mode:'other',lower_air_height:-1},'mm');
  for(const k of ['coating_height','coating_eps_r','coating_tan_delta','lower_air_height','ground_gap'])assert.ok(!Object.hasOwn(p,k));
 });
 test(name+' studies expose film and ground dimensions but not outer bounds',()=>{
  const fields=studyFields(name,original);assert.equal(fields.coating_height,'Coating height');assert.equal(fields.coating_eps_r,'Coating permittivity');assert.equal(fields.ground_width,'Ground width');assert.equal(Object.hasOwn(fields,'ground_gap'),paired);
  for(const key of ['lower_air_height','air_height','box_width'])assert.ok(!Object.hasOwn(fields,key));
 });
}
