import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, editableParameters, parameterFields, lengthFields, scales, schematic, studyFields, isPair, isCoated, isNormalFilm, isCoplanar, isUnbacked} from '../ui/model.js';
for(const paired of [false,true]){
 const name=paired?'coupled_conformal_coated_unbacked_coplanar':'conformal_coated_unbacked_coplanar';
 const original={width:.0005000000000123456,substrate_height:.0005,thickness:.000035,top_width:.0004,eps_r:4,tan_delta:.01,coating_thickness:.000020000000000123456,coating_eps_r:3.500000000000123,coating_tan_delta:.0200000000000123,air_height:.004000000000123456,lower_air_height:.006000000000123456,box_width:.012,ground_width:.001,gap:paired?.0003:.0002,...(paired?{ground_gap:.0002000000000123456}:{})};
 function form(unit){
  const values={profile:'tapered',box_mode:'fixed',air_mode:'fixed',lower_air_mode:'fixed'},si={};
  for(const [id,key] of Object.entries(parameterFields(name))){if(original[key]==null)continue;if(lengthFields.includes(id)){si[id]=original[key];values[id]=String(Number((original[key]/scales[unit]).toPrecision(10)));}else values[id]=String(original[key]);}
  return {values,si};
 }
 test(name+' requires engine geometry rather than a planar schematic',()=>{
  assert.ok(isCoated(name)&&isNormalFilm(name)&&isCoplanar(name));assert.equal(isUnbacked(name),true);assert.equal(isPair(name),paired);
  assert.throws(()=>schematic(name,original),/Inspect the engine geometry/);
 });
 test(name+' preserves exact normal thickness through units and edits',()=>{
  for(const unit of ['mm','µm','mil']){
   const {values,si}=form(unit);assert.deepEqual(editableParameters(name,values,unit,original,new Set(),si),original);
   values.coating_thickness=String(.00003/scales[unit]);si.coating_thickness=.00003;
   assert.deepEqual(editableParameters(name,values,unit,original,new Set(['coating_thickness']),si),{...original,coating_thickness:.00003});
   assert.ok(!Object.hasOwn(parameters(name,values,unit),'coating_height'));
  }
 });
 test(name+' normal thickness can be smaller than copper but overhangs cannot',()=>{
  const {values}=form('mm');assert.ok(parameters(name,values,'mm').coating_thickness<original.thickness);
  for(const bad of ['',0,-1,'NaN','Infinity'])assert.throws(()=>parameters(name,{...values,coating_thickness:bad},'mm'));
  assert.throws(()=>parameters(name,{...values,top_width:'.6'},'mm'),/top width/);
  assert.throws(()=>parameters(name,{...values,coating_eps_r:0},'mm'));
  assert.throws(()=>parameters(name,{...values,coating_tan_delta:-1},'mm'));
 });
 test(name+' normal and planar thickness fields remain distinct',()=>{
  const {values}=form('mm');
  assert.ok(parameters(name,{...values,coating_height:-1},'mm').coating_thickness>0);
  const planar=parameters('coated_microstrip',{...values,coating_height:'.2',coating_thickness:-1},'mm');
  assert.equal(planar.coating_height,.0002);assert.ok(!Object.hasOwn(planar,'coating_thickness'));
  const fields=studyFields(name,original);assert.equal(fields.coating_thickness,'Normal coating thickness');assert.equal(fields.coating_eps_r,'Coating permittivity');assert.ok(!Object.hasOwn(fields,'coating_height'));
 });
}

for(const paired of [false,true])test('finite normal-film ground geometry '+paired,()=>{
 const name=paired?'coupled_conformal_coated_unbacked_coplanar':'conformal_coated_unbacked_coplanar';
 const input={width:'.5',height:'.5',thickness:'.035',eps_r:'4',tan_delta:'.01',gap:'.3',ground_gap:'.2',ground_width:'1',coating_thickness:'.02',coating_eps_r:'3.5',coating_tan_delta:'.02'};
 const p=parameters(name,input,'mm');assert.equal(p.gap,.0003);assert.equal(p.ground_width,.001);assert.equal(Object.hasOwn(p,'ground_gap'),paired);
 assert.ok(!Object.hasOwn(p,'lower_air_height'));assert.throws(()=>parameters(name,{...input,ground_width:0},'mm'));
 if(paired)assert.throws(()=>parameters(name,{...input,ground_gap:0},'mm'));
});

for(const paired of [false,true])test('independent lower air controls '+paired,()=>{
 const name=paired?'coupled_conformal_coated_unbacked_coplanar':'conformal_coated_unbacked_coplanar';
 const input={width:'.5',height:'.5',thickness:'.035',eps_r:'4',tan_delta:'.01',gap:'.3',ground_gap:'.2',ground_width:'1',coating_thickness:'.02',coating_eps_r:'3.5',coating_tan_delta:'.02',lower_air_mode:'fixed',lower_air_height:'6'};
 const p=parameters(name,input,'mm');assert.equal(p.lower_air_height,.006);assert.ok(!Object.hasOwn(p,'air_height'));
 const auto=parameters(name,{...input,lower_air_mode:'auto',lower_air_height:-1},'mm');assert.ok(!Object.hasOwn(auto,'lower_air_height'));
 for(const bad of ['',0,-1,'NaN','Infinity'])assert.throws(()=>parameters(name,{...input,lower_air_height:bad},'mm'));
});
