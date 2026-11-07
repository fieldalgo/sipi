import test from 'node:test';
import assert from 'node:assert/strict';
import {parameters, scales, convert, schematic} from '../ui/model.js';

const values = {width: '0.5', height: '1', thickness: '0.035', gap: '0.2', ground_width: '1', eps_r: '4', tan_delta: '0.02'};

test('display units produce identical SI geometry', () => {
  for (const template of ['microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar']) {
    const mm = parameters(template, values, 'mm');
    const milValues = Object.fromEntries(Object.entries(values).map(([k,v]) => [k, ['eps_r','tan_delta'].includes(k) ? v : convert(v, 'mm', 'mil')]));
    const mil = parameters(template, milValues, 'mil');
    for (const key in mm) assert.ok(Math.abs(mm[key] - mil[key]) < 1e-15);
    assert.equal(mm.width, .0005);
  }
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
