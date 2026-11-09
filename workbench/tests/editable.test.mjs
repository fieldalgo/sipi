import test from 'node:test';
import assert from 'node:assert/strict';
import {editableParameters, parameterFields, scales, studyFields} from '../ui/model.js';

const originals = {
  microstrip: {width: .0005000000000123456, thickness: .0000350000000001, eps_r: 4.123456789012345, tan_delta: .0123456789012345, substrate_height: .0010000000000123, top_width: null, air_height: .0067, box_width: .023},
  stripline: {width: .0005, thickness: 0, eps_r: 4, tan_delta: 0, plane_spacing: .001, top_width: null, box_width: .02},
  coupled_microstrip: {width: .0005, thickness: 0, eps_r: 4, tan_delta: 0, substrate_height: .001, gap: .0002, top_width: null, air_height: null, box_width: null},
  grounded_coplanar: {width: .0005, thickness: .000035, eps_r: 4, tan_delta: 0, substrate_height: .001, gap: .0002, ground_width: .003, top_width: null, air_height: .008, box_width: .03},
  coated_microstrip: {width: .0005, thickness: .0001, eps_r: 4, tan_delta: .01, substrate_height: .001, top_width: .0004, coating_height: .0002, coating_eps_r: 3, coating_tan_delta: .02, air_height: .006, box_width: .02},
};
function form(name, p, unit) {
  const values = {profile: p.top_width == null ? 'rectangular' : 'tapered'}, si = {};
  for (const [id, key] of Object.entries(parameterFields(name))) {
    if (p[key] == null) continue;
    if (['eps_r', 'tan_delta', 'coating_eps_r', 'coating_tan_delta'].includes(id)) values[id] = String(p[key]);
    else {si[id] = p[key]; values[id] = String(Number((p[key] / scales[unit]).toPrecision(10)));}
  }
  return {values, si};
}
for (const [name, original] of Object.entries(originals)) {
  test(`${name}: unit/display changes retain every exact parameter`, () => {
    for (const unit of ['mm', 'mil', 'mm']) {
      const {values, si} = form(name, original, unit);
      assert.deepEqual(editableParameters(name, values, unit, original, new Set(), si), original);
      const enteredWidth = .0007;
      values.width = String(enteredWidth / scales[unit]); si.width = enteredWidth;
      assert.deepEqual(editableParameters(name, values, unit, original, new Set(['width']), si), {...original, width: enteredWidth});
    }
  });
}
test('profile changes are explicit; inactive nullable taper is not a study variable', () => {
  const p = originals.microstrip, {values, si} = form('microstrip', p, 'mm');
  assert.ok(!Object.hasOwn(studyFields('microstrip', p), 'top_width'));
  values.profile = 'tapered'; values.top_width = '.4'; si.top_width = .0004;
  const tapered = editableParameters('microstrip', values, 'mm', p, new Set(['profile']), si);
  assert.deepEqual(tapered, {...p, top_width: .0004});
  values.profile = 'rectangular';
  assert.deepEqual(editableParameters('microstrip', values, 'mm', tapered, new Set(['profile']), si), p);
});
test('new form uses exact SI lengths and rejects invalid lengths', () => {
  const p = originals.microstrip, {values, si} = form('microstrip', p, 'mil');
  const got = editableParameters('microstrip', values, 'mil', null, new Set(), si);
  assert.equal(got.width, p.width); assert.equal(got.substrate_height, p.substrate_height);
  assert.throws(() => editableParameters('microstrip', values, 'mil', p, new Set(), {...si, width: NaN}));
});
