import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, scales, convert, schematic, refinedMesh} from '../ui/model.js';

test('explicit mesh refinement preserves angle and the original resolved settings', () => {
  const original = Object.freeze({edge_size:8e-6, far_size:.00025, grade:.3, min_angle:28});
  const refined = refinedMesh(original);
  assert.deepEqual(refined, {edge_size:4e-6, far_size:.000125, grade:.15, min_angle:28});
  assert.deepEqual(original, {edge_size:8e-6, far_size:.00025, grade:.3, min_angle:28});
  assert.equal(refinedMesh({...original, grade:0}).grade, 0);
  for (const invalid of [null, {}, {...original, edge_size:0}, {...original, edge_size:Number.MIN_VALUE}, {...original, far_size:Infinity}, {...original, grade:-1}, {...original, min_angle:34}, {...original, min_angle:0}, {...original, edge_size:'0.1'}, {...original, extra:1}]) assert.throws(() => refinedMesh(invalid));
});

const values = {width: '0.5', height: '1', thickness: '0.035', gap: '0.2', ground_width: '1', ground_gap:'0.3', eps_r: '4', tan_delta: '0.02'};

test('display units produce identical SI geometry', () => {
  for (const template of ['microstrip', 'stripline', 'coupled_microstrip', 'coupled_stripline', 'grounded_coplanar', 'coupled_grounded_coplanar']) {
    const mm = parameters(template, values, 'mm');
    const milValues = Object.fromEntries(Object.entries(values).map(([k,v]) => [k, ['eps_r','tan_delta'].includes(k) ? v : convert(v, 'mm', 'mil')]));
    const mil = parameters(template, milValues, 'mil');
    for (const key in mm) assert.ok(Math.abs(mm[key] - mil[key]) < 1e-15);
    assert.equal(mm.width, .0005);
  }
});

test('a coupled stripline uses two planes, full spacing and bottom-edge gap', () => {
  const p = parameters('coupled_stripline', values, 'mm');
  assert.equal(p.plane_spacing, .001); assert.equal(p.gap, .0002);
  assert.equal(p.substrate_height, undefined); assert.equal(p.ground_width, undefined);
  const model = schematic('coupled_stripline', p);
  assert.equal(model.layers.length, 1); assert.equal(model.layers[0].eps_r, 4);
  assert.equal(model.box.top, 'ground'); assert.equal(model.box.bottom, 'ground');
  assert.equal(model.traces.length, 2);
  assert.equal(model.traces[0].y, (.001-.000035)/2);
  assert.ok(Math.abs(model.traces[1].x-model.traces[0].x-p.width-p.gap) < 1e-18);
  const offset = schematic('coupled_stripline', {...p, trace_height: .0003, top_width:.0004});
  for(const trace of offset.traces) {assert.equal(trace.y, .0003);assert.equal(trace.top_width, .0004);}
});

test('coplanar pair keeps signal gap separate from finite side-ground gaps', () => {
  const p = parameters('coupled_grounded_coplanar', {...values, profile:'tapered', top_width:'0.4'}, 'mm');
  assert.equal(p.gap,.0002);assert.equal(p.ground_gap,.0003);assert.equal(p.ground_width,.001);
  const model=schematic('coupled_grounded_coplanar',p);
  assert.deepEqual(model.traces.map(t=>t.ground),[false,false,true,true]);
  const [left,right,gl,gr]=model.traces;
  assert.ok(Math.abs(right.x-left.x-p.width-p.gap)<1e-18);
  assert.ok(Math.abs(left.x-left.width/2-(gl.x+gl.width/2)-p.ground_gap)<1e-18);
  assert.ok(Math.abs(gr.x-gr.width/2-(right.x+right.width/2)-p.ground_gap)<1e-18);
  assert.equal(left.top_width,.0004);assert.equal(right.top_width,.0004);
  assert.equal(gl.top_width,gl.width);assert.equal(gr.top_width,gr.width);
  assert.equal(gl.thickness,p.thickness);assert.equal(gr.thickness,p.thickness);
  assert.equal(model.box.bottom,'ground');assert.equal(model.box.top,'open');
});

test('a stripline uses full plane spacing and no surface-only parameters', () => {
  const p = parameters('stripline', values, 'mm');
  assert.equal(p.plane_spacing, .001);
  assert.equal(p.substrate_height, undefined);
  assert.equal(p.gap, undefined);
  const model = schematic('stripline', p);
  assert.equal(model.traces[0].y, (.001 - .000035) / 2);
  assert.equal(model.box.top, 'ground');
});

test('invalid visible numbers never silently become zero or NaN', () => {
  for (const width of ['', ' ', true, 'Infinity', '-1', 'abc']) assert.throws(() => parameters('microstrip', {...values, width}, 'mm'));
  assert.throws(() => parameters('unknown', values, 'mm'));
  assert.throws(() => parameters('microstrip', values, 'cm'));
  assert.equal(scales.mil, 25.4e-6);
  assert.equal(scales['µm'], 1e-6);
});

test('taper and planar coating preserve dimensions and reject impossible profiles', () => {
  const value = {...values, profile: 'tapered', top_width: '.4', coating_height: '.2', coating_eps_r: '3.5', coating_tan_delta: '.01'};
  const p = parameters('coated_microstrip', value, 'mm');
  assert.equal(p.top_width, .0004);
  assert.equal(p.coating_height, .0002);
  assert.equal(p.coating_eps_r, 3.5);
  const model = schematic('coated_microstrip', p);
  assert.equal(model.traces[0].top_width, p.top_width);
  assert.equal(model.layers[1].thickness, .0002);
  assert.equal(model.layers[1].eps_r, 3.5);
  assert.equal(model.layers[2].eps_r, 1);
  const cpw = schematic('grounded_coplanar', parameters('grounded_coplanar', value, 'mm'));
  for (const trace of cpw.traces.filter(t => t.ground)) assert.equal(trace.top_width, trace.width);
  for (const thickness of ['0', '.2']) assert.throws(() => parameters('coated_microstrip', {...value, thickness}, 'mm'));
  const converted = {...value};
  for (const key of ['width','top_width','height','thickness','coating_height']) converted[key] = convert(value[key], 'mm', 'mil');
  const mil = parameters('coated_microstrip', converted, 'mil');
  for (const key in p) assert.ok(Math.abs(p[key] - mil[key]) < 1e-15);
});


test('planar coated pair keeps two signals, a full flat layer and distinct material inputs', () => {
  const v={...values, profile:'tapered', top_width:'.4', coating_height:'.1', coating_eps_r:'3.5', coating_tan_delta:'.01'};
  const p=parameters('coupled_coated_microstrip',v,'mm'), model=schematic('coupled_coated_microstrip',p);
  assert.equal(p.gap,.0002);assert.equal(p.coating_height,.0001);assert.equal(p.coating_tan_delta,.01);
  assert.equal(model.traces.length,2);assert.deepEqual(model.traces.map(t=>t.x),[-.00035,.00035]);
  for(const t of model.traces){assert.equal(t.y,.001);assert.equal(t.top_width,.0004);assert.equal(t.ground,false);}
  assert.equal(model.layers[1].thickness,p.coating_height);assert.equal(model.layers[1].eps_r,3.5);assert.equal(model.layers[2].eps_r,1);
  for(const coating_height of ['',0,.035,-1])assert.throws(()=>parameters('coupled_coated_microstrip',{...v,coating_height},'mm'));
  for(const unit of ['µm','mil']){
    const inputs={...v};for(const key of ['width','top_width','height','thickness','gap','coating_height'])inputs[key]=convert(v[key],'mm',unit);
    const q=parameters('coupled_coated_microstrip',inputs,unit);for(const key in p)assert.ok(Math.abs(p[key]-q[key])<1e-15);
  }
});


test('coated coplanar keeps one tapered signal, two rectangular grounds and a full coating', () => {
  const v={...values,profile:'tapered',top_width:'.4',coating_height:'.1',coating_eps_r:'3.5',coating_tan_delta:'.01'};
  const p=parameters('coated_grounded_coplanar',v,'mm'),m=schematic('coated_grounded_coplanar',p);
  assert.equal(p.gap,.0002);assert.equal(p.ground_width,.001);assert.equal(p.ground_gap,undefined);
  assert.equal(m.traces.length,3);const [signal,...grounds]=m.traces;
  assert.equal(signal.top_width,.0004);assert.equal(signal.ground,false);
  assert.deepEqual(grounds.map(t=>t.x),[-.00095,.00095]);
  for(const t of grounds){assert.equal(t.width,.001);assert.equal(t.top_width,.001);assert.equal(t.ground,true);assert.equal(t.thickness,p.thickness);}
  assert.equal(m.layers[1].thickness,.0001);assert.equal(m.layers[1].eps_r,3.5);assert.equal(m.layers[2].eps_r,1);
  for(const change of [{gap:''},{ground_width:0},{coating_height:'.035'}])assert.throws(()=>parameters('coated_grounded_coplanar',{...v,...change},'mm'));
});
