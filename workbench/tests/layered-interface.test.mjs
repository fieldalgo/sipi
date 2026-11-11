import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters,editableParameters,parameterFields,scales,schematic,studyFields,studyScale,isPair,isStripline,isLayeredInterface} from '../ui/model.js';
const names=['layered_stripline','coupled_layered_stripline'];
const p={width:.0003000000000123456,lower_height:.0004000000000123456,upper_height:.0006000000000123456,lower_eps_r:3.8,upper_eps_r:4.5,lower_tan_delta:.01,upper_tan_delta:.02,thickness:.000035,top_width:.0002500000000123456,box_width:.006};
function form(name,unit='mm'){
 const original={...p,...(isPair(name)?{gap:.0002000000000123456}:{})};
 const si=Object.fromEntries(['width','lower_height','upper_height','thickness','top_width','box_width',...(isPair(name)?['gap']:[])].map(k=>[k,original[k]]));
 const values={...original,profile:'tapered',box_mode:'fixed',height:'invalid',eps_r:'invalid',tan_delta:'invalid',offset:'invalid',air_mode:'fixed',air_height:'invalid',placement:'fixed',trace_height:'invalid'};
 for(const [k,v] of Object.entries(si))values[k]=String(Number((v/scales[unit]).toPrecision(10)));
 return {original,si,values};
}
for(const name of names){
 test(name+' uses two independent materials and interface height',()=>{
  assert.ok(isLayeredInterface(name)&&isStripline(name));const {values}=form(name);const out=parameters(name,values,'mm');
  for(const k of ['eps_r','tan_delta','plane_spacing','substrate_height','trace_height','air_height','offset'])assert.equal(Object.hasOwn(out,k),false);
  assert.equal(out.lower_eps_r,3.8);assert.equal(out.upper_eps_r,4.5);assert.equal(out.lower_tan_delta,.01);assert.equal(out.upper_tan_delta,.02);
  for(const [key,value] of [['lower_height','0'],['upper_height',''],['lower_eps_r','.5'],['upper_eps_r',true],['lower_tan_delta','-1'],['upper_tan_delta','NaN']])assert.throws(()=>parameters(name,{...values,[key]:value},'mm'));
  const zero=parameters(name,{...values,profile:'rectangular',thickness:'0'},'mm');assert.equal(zero.thickness,0);assert.equal(Object.hasOwn(zero,'top_width'),false);
 });
 test(name+' keeps exact layer SI and dimensionless study bounds across units',()=>{
  for(const unit of ['µm','mil','mm','mil','mm']){
   const {original,values,si}=form(name,unit);assert.deepEqual(editableParameters(name,values,unit,original,new Set(),si),original);
   si.lower_height=.0004567890123456789;values.lower_height=String(si.lower_height/scales[unit]);
   assert.deepEqual(editableParameters(name,values,unit,original,new Set(['lower_height']),si),{...original,lower_height:si.lower_height});
   assert.equal(studyScale('lower_eps_r',unit),1);assert.equal(studyScale('upper_eps_r',unit),1);assert.equal(studyScale('upper_height',unit),scales[unit]);
  }
  const fields=studyFields(name,form(name).original);for(const k of ['lower_height','upper_height','lower_eps_r','upper_eps_r'])assert.ok(k in fields);
  assert.equal('plane_spacing' in fields,false);assert.equal('eps_r' in fields,false);assert.equal(parameterFields(name).lower_tan_delta,'lower_tan_delta');
 });
 test(name+' draws both dielectric layers and copper above their interface',()=>{
  const {original}=form(name);const d=schematic(name,original);
  assert.deepEqual(d.layers,[{name:'lower',thickness:p.lower_height,eps_r:3.8},{name:'upper',thickness:p.upper_height,eps_r:4.5}]);
  assert.equal(d.box.top,'ground');assert.equal(d.box.bottom,'ground');assert.equal(d.traces.length,isPair(name)?2:1);
  for(const t of d.traces){assert.equal(t.y,p.lower_height);assert.equal(t.thickness,p.thickness);assert.equal(t.top_width,p.top_width);}
 });
}
test('uniform forms ignore inactive two-layer fields',()=>{
 const values={width:.3,height:1,thickness:.035,gap:.2,eps_r:4,tan_delta:0,profile:'rectangular',placement:'centred'};
 const hidden={...values,...Object.fromEntries(['lower_height','upper_height','lower_eps_r','upper_eps_r','lower_tan_delta','upper_tan_delta'].map(x=>[x,'invalid']))};
 for(const name of ['stripline','coupled_stripline'])assert.deepEqual(parameters(name,values,'mm'),parameters(name,hidden,'mm'));
 assert.equal(Object.hasOwn(parameterFields('stripline'),'lower_height'),false);
});
