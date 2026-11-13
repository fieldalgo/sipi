import test from 'node:test';
import assert from 'node:assert/strict';
import {registeredInput} from './registered-forms.mjs';
import {layeredSurfaceLabels,scales,lengthFields,parameterFields,editableParameters,studyFields,isAsymmetric,isLayeredSurface,isLayeredInterface,isStripline,isPair,isForwardPair,usesEngineGeometry,schematic} from '../ui/model.js';
for(const name of Object.keys(layeredSurfaceLabels))for(const unit of Object.keys(scales))test(`${name}: ${unit} keeps both substrate layers below copper`,()=>{
 const p=registeredInput(name).parameters,values={},si={};
 for(const [id,key] of Object.entries(parameterFields(name))){if(p[key]==null)continue;values[id]=String(p[key]/(lengthFields.includes(id)?scales[unit]:1));if(lengthFields.includes(id))si[id]=p[key];}
 Object.assign(values,{profile:p.top_width==null?'rectangular':'tapered',box_mode:'fixed',air_mode:'fixed'});
 for(const side of ['left','right'])values[side+'_profile']=p[side+'_top_width']==null?'rectangular':'tapered';
 assert.deepEqual(editableParameters(name,values,unit,p,new Set(),si),p);
 assert.deepEqual(editableParameters(name,values,unit,null,new Set(),si),Object.fromEntries(Object.entries(p).filter(([,v])=>v!==null)));
 assert.ok(isLayeredSurface(name)&&!isLayeredInterface(name)&&!isStripline(name)&&usesEngineGeometry(name));
 assert.equal(isPair(name),name.startsWith('coupled_')||name.startsWith('asymmetric_'));assert.equal(isForwardPair(name),isAsymmetric(name));
 const fields=studyFields(name,p);for(const key of Object.keys(fields))assert.ok(Object.hasOwn(p,key),key);
 assert.match(fields.upper_height,/excludes copper/);assert.ok(!('substrate_height' in fields)&&!('eps_r' in fields));
 assert.throws(()=>schematic(name,p),/engine geometry/);
 values.upper_height=String(.8e-3/scales[unit]);si.upper_height=.8e-3;
 assert.deepEqual(editableParameters(name,values,unit,p,new Set(['upper_height']),si),{...p,upper_height:.8e-3});
});
