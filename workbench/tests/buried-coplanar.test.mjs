import test from 'node:test';
import assert from 'node:assert/strict';
import {editableParameters,parameters,scales,schematic,studyFields,isStripline,isPair,isCoplanar} from '../ui/model.js';
const names=['coplanar_stripline','coupled_coplanar_stripline'];
const p={width:.0003000000000123456,plane_spacing:.001,trace_height:.0004000000000123456,thickness:.000035,eps_r:4,tan_delta:.02,top_width:.00025,box_width:.006,gap:.0003,ground_width:.0008};
function form(pair,unit){
 const si={width:p.width,top_width:p.top_width,height:p.plane_spacing,trace_height:p.trace_height,thickness:p.thickness,gap:p.gap,ground_width:p.ground_width,box_width:p.box_width,...(pair?{ground_gap:.0003}:{})};
 const values={profile:'tapered',eps_r:4,tan_delta:.02,box_mode:'fixed',placement:'centred',air_mode:'fixed',air_height:'bad'};
 for(const [key,value] of Object.entries(si))values[key]=String(Number((value/scales[unit]).toPrecision(10)));
 return {si,values};
}
for(const name of names){const pair=name===names[1];
 test(name+' has two grounded planes and explicit signal/ground heights',()=>{
  const {values}=form(pair,'mm'),q=parameters(name,values,'mm'),m=schematic(name,q);
  assert.ok(isStripline(name)&&isCoplanar(name));assert.equal(isPair(name),pair);
  assert.equal(m.layers.length,1);assert.equal(m.box.top,'ground');assert.equal(m.box.bottom,'ground');assert.equal(m.box.sides,'open');
  assert.equal(m.traces.length,pair?4:3);assert.ok(m.traces.every(t=>t.y===q.trace_height));
  const grounds=m.traces.filter(t=>t.ground);assert.equal(grounds.length,2);assert.ok(grounds.every(t=>t.width===q.ground_width&&t.top_width===q.ground_width));
  const signal=m.traces.filter(t=>!t.ground).at(-1),ground=grounds.at(-1);
  assert.ok(Math.abs(ground.x-ground.width/2-signal.x-signal.width/2-(pair?q.ground_gap:q.gap))<1e-18);
  assert.ok(!('air_height' in q)&&!('substrate_height' in q));
  assert.equal(studyFields(name,q).trace_height,'Bottom-face height');
 });
 test(name+' exact saved inputs survive units and edit one dimension only',()=>{
  const original={...p,...(pair?{ground_gap:.0003}:{})};
  for(const unit of ['mm','µm','mil','µm','mm']){
   const {values,si}=form(pair,unit);assert.deepEqual(editableParameters(name,values,unit,original,new Set(),si),original);
   si.trace_height=.0004500000000123456;values.trace_height=String(si.trace_height/scales[unit]);
   assert.deepEqual(editableParameters(name,values,unit,original,new Set(['trace_height']),si),{...original,trace_height:si.trace_height});
   values.placement='fixed';assert.deepEqual(editableParameters(name,values,unit,original,new Set(['placement']),si),original);
  }
 });
 test(name+' required height and finite clearances cannot be omitted',()=>{
  const {values}=form(pair,'mm');for(const key of ['trace_height','gap','ground_width',...(pair?['ground_gap']:[])])for(const value of [undefined,null,'',0,-1,'NaN'])assert.throws(()=>parameters(name,{...values,[key]:value},'mm'),/positive/);
 });
}
