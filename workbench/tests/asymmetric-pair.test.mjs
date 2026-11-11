import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, editableParameters, parameterFields, scales, schematic, checkDrawing, studyFields, studyScale, isAsymmetric, isStripline, isPair, compareLines} from '../ui/model.js';
const names=['asymmetric_coupled_microstrip','asymmetric_coupled_stripline'];
function form(name,unit='mm') {
 const buried=isStripline(name);
 const original={left_width:.0004000000000123456,right_width:.0006500000000123456,left_thickness:.000035,right_thickness:.00005,left_top_width:.0003200000000123456,right_top_width:.0005500000000123456,gap:.0002500000000123456,eps_r:4,tan_delta:.02,box_width:.012,...(buried?{plane_spacing:.0010000000000123456}:{substrate_height:.0005000000000123456,air_height:.0060000000000123456})};
 const fields=parameterFields(name),si={};
 for(const id of ['left_width','right_width','left_thickness','right_thickness','left_top_width','right_top_width','gap','height','box_width',...(!buried?['air_height']:[])])si[id]=original[fields[id]];
 const values={...original,left_profile:'tapered',right_profile:'tapered',box_mode:'fixed',air_mode:'fixed',width:'invalid',thickness:'invalid',profile:'invalid',top_width:'invalid',trace_height:'invalid'};
 for(const [k,v] of Object.entries(si))values[k]=String(Number((v/scales[unit]).toPrecision(10)));
 return {original,si,values};
}
for(const name of names) {
 test(name+' uses independent copper dimensions and excludes hidden symmetric inputs',()=>{
  assert.ok(isAsymmetric(name)&&isPair(name));const {values}=form(name),out=parameters(name,values,'mm');
  for(const k of ['width','thickness','top_width','trace_height'])assert.equal(Object.hasOwn(out,k),false);
  for(const k of ['left_width','right_width','left_thickness','right_thickness','left_top_width','right_top_width'])assert.ok(out[k]>0);
  for(const [k,v] of [['left_width',0],['right_width',true],['left_thickness',-1],['right_top_width',''],['left_profile','unknown']])assert.throws(()=>parameters(name,{...values,[k]:v},'mm'));
  const zero=parameters(name,{...values,left_profile:'rectangular',left_thickness:'0'},'mm');assert.equal(zero.left_thickness,0);assert.equal(Object.hasOwn(zero,'left_top_width'),false);
  assert.throws(()=>parameters(name,{...values,left_thickness:0},'mm'));
 });
 test(name+' preserves exact SI, one-side edits and independent profile changes',()=>{
  for(const unit of ['µm','mil','mm','mil']) {
   const {original,si,values}=form(name,unit);assert.deepEqual(editableParameters(name,values,unit,original,new Set(),si),original);
   si.right_width=.0007123456789012345;values.right_width=String(si.right_width/scales[unit]);
   assert.deepEqual(editableParameters(name,values,unit,original,new Set(['right_width']),si),{...original,right_width:si.right_width});
   assert.deepEqual(editableParameters(name,{...values,left_profile:'rectangular'},unit,original,new Set(['left_profile']),si),{...original,left_top_width:null});
   assert.equal(studyScale('left_width',unit),scales[unit]);assert.equal(studyScale('eps_r',unit),1);
  }
 });
 test(name+' exposes separate study dimensions',()=>{
  const p=form(name).original,f=studyFields(name,p);assert.equal('width' in f,false);assert.equal('thickness' in f,false);
  for(const side of ['left','right'])for(const k of ['width','thickness','top_width'])assert.ok(`${side}_${k}` in f);
  const untapered=studyFields(name,{...p,left_top_width:null});assert.equal('left_top_width' in untapered,false);assert.equal('right_top_width' in untapered,true);
 });
 test(name+' draws centred total span and each correct bottom height',()=>{
  const p=form(name).original,d=schematic(name,p);assert.equal(d.traces.length,2);assert.deepEqual(d.traces.map(t=>t.name),['positive','negative']);
  assert.doesNotThrow(()=>checkDrawing(d));assert.ok(d.layers.every(layer=>Number.isFinite(layer.thickness)&&layer.thickness>0));
  const [a,b]=d.traces;assert.equal(a.x,-(p.gap+p.right_width)/2);assert.equal(b.x,(p.gap+p.left_width)/2);
  for(const [side,t] of [['left',a],['right',b]]){
   assert.equal(t.width,p[side+'_width']);assert.equal(t.thickness,p[side+'_thickness']);assert.equal(t.top_width,p[side+'_top_width']);
   assert.equal(t.y,isStripline(name)?(p.plane_spacing-t.thickness)/2:p.substrate_height);
  }
  assert.equal(d.box.bottom,'ground');assert.equal(d.box.top,isStripline(name)?'ground':'open');assert.ok(d.box.width>p.left_width+p.gap+p.right_width);
 });
}
test('forward comparisons keep their explicit launch quantity and matrices',()=>{
 const line={names:['positive','negative'],C:[[1,-.2],[-.2,2]],L:[[3,.1],[.1,4]],G_1GHz:[[.1,0],[0,.2]],z_diff_forward:100,forward_launch:{condition:'Icommon=0'}};
 const result=compareLines(line,{...line,z_diff_forward:101});assert.equal(result.compatible,true);
 const rows=result.rows.filter(r=>r.key==='z_diff_forward');assert.equal(rows.length,1);assert.equal(rows[0].delta,1);assert.equal(rows[0].label,'Forward differential (Ic=0)');
 for(const k of ['z_diff','z_common','eps_eff','delay'])assert.equal(result.rows.some(r=>r.key===k),false);
 const old={...line};delete old.z_diff_forward;delete old.forward_launch;assert.equal(compareLines(line,old).rows.some(r=>r.key==='z_diff_forward'),false);
});
test('ordinary form parameters ignore all inactive unequal dimensions',()=>{
 const values={width:.5,thickness:.035,height:1,gap:.2,eps_r:4,tan_delta:0,profile:'rectangular',placement:'centred'};
 const extra={...values,...Object.fromEntries(['left_width','right_width','left_thickness','right_thickness','left_top_width','right_top_width','left_profile','right_profile'].map(k=>[k,'invalid']))};
 for(const name of ['microstrip','coupled_microstrip','stripline','coupled_stripline'])assert.deepEqual(parameters(name,extra,'mm'),parameters(name,values,'mm'));
});
