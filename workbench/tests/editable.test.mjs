import test from 'node:test';
import assert from 'node:assert/strict';
import {editableParameters, parameterFields, scales, studyFields, isStripline} from '../ui/model.js';

const originals = {
  microstrip: {width: .0005000000000123456, thickness: .0000350000000001, eps_r: 4.123456789012345, tan_delta: .0123456789012345, substrate_height: .0010000000000123, top_width: null, air_height: .0067, box_width: .023},
  stripline: {width: .0005, thickness: 0, eps_r: 4, tan_delta: 0, plane_spacing: .001, top_width: null, box_width: .02},
  offset_stripline: {width:.0005000000000123456, thickness:.000035, eps_r:4, tan_delta:.01, plane_spacing:.001, top_width:.0004, box_width:.02, trace_height:.0003000000000123456},
  coupled_stripline: {width: .0005000000000123456, thickness: .000035, eps_r: 4, tan_delta: .01, plane_spacing: .001, gap: .0002000000000123456, top_width: .0004, box_width: .02, trace_height: .0003},
  coupled_microstrip: {width: .0005, thickness: 0, eps_r: 4, tan_delta: 0, substrate_height: .001, gap: .0002, top_width: null, air_height: null, box_width: null},
  grounded_coplanar: {width: .0005, thickness: .000035, eps_r: 4, tan_delta: 0, substrate_height: .001, gap: .0002, ground_width: .003, top_width: null, air_height: .008, box_width: .03},
  coupled_grounded_coplanar: {width:.0005000000000123456, thickness:.000035, eps_r:4, tan_delta:.01, substrate_height:.001, gap:.0003, ground_gap:.0002000000000123456, ground_width:.003, top_width:.0004, air_height:.0067, box_width:.03},
  coupled_coated_microstrip: {width:.0005000000000123456, gap:.0003000000000123456, thickness:.000035, top_width:.0004, substrate_height:.0005, eps_r:4, tan_delta:.01, coating_height:.0001000000000123456, coating_eps_r:3.5, coating_tan_delta:.02, air_height:.006, box_width:.012},
  coated_grounded_coplanar: {width:.0005000000000123456, gap:.0002000000000123456, ground_width:.0010000000000123456, thickness:.000035, top_width:.0004, substrate_height:.0005, eps_r:4, tan_delta:.01, coating_height:.0001000000000123456, coating_eps_r:3.5, coating_tan_delta:.02, air_height:.006, box_width:.012},
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
    for (const unit of ['mm', 'µm', 'mil', 'µm', 'mm']) {
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

test('coplanar ground controls preserve the other exact inputs and expose studies', () => {
  const p=originals.coupled_grounded_coplanar;
  for(const unit of ['mm','µm','mil']) {
    const {values,si}=form('coupled_grounded_coplanar',p,unit);
    values.ground_gap=String(.0004/scales[unit]);si.ground_gap=.0004;
    assert.deepEqual(editableParameters('coupled_grounded_coplanar',values,unit,p,new Set(['ground_gap']),si),{...p,ground_gap:.0004});
  }
  const fields=studyFields('coupled_grounded_coplanar',p);
  assert.equal(fields.ground_gap,'Signal–ground gap');assert.equal(fields.ground_width,'Ground width');
  assert.equal(studyFields('microstrip',originals.microstrip).ground_gap,undefined);
});


for (const [name, original] of Object.entries(originals)) {
  test(`${name}: domain controls retain omitted/null/exact inputs and explicitly reset`, () => {
    const keys=isStripline(name) ? ['box_width'] : ['box_width','air_height'];
    for (const shape of ['original','omitted','null']) for (const unit of ['mm','µm','mil']) {
      const p={...original};
      if(shape==='omitted')for(const key of keys)delete p[key];
      if(shape==='null')for(const key of keys)p[key]=null;
      const {values,si}=form(name,p,unit);
      values.box_mode=p.box_width==null?'auto':'fixed';values.air_mode=p.air_height==null?'auto':'fixed';
      assert.deepEqual(editableParameters(name,values,unit,p,new Set(),si),p);
      const changed=new Set();
      for(const key of keys){const mode=key==='box_width'?'box_mode':'air_mode';values[mode]='fixed';
        si[key]=key==='box_width'?.02400000000012345:.00800000000012345;values[key]=String(Number((si[key]/scales[unit]).toPrecision(10)));changed.add(mode);}
      const edited=editableParameters(name,values,unit,p,changed,si);
      assert.deepEqual(edited,{...p,...Object.fromEntries(keys.map(k=>[k,si[k]]))});
      for(const key of keys)values[key==='box_width'?'box_mode':'air_mode']='auto';
      assert.deepEqual(editableParameters(name,values,unit,edited,changed,si),{...p,...Object.fromEntries(keys.map(k=>[k,null]))});
    }
  });
}

test('inactive domain fields cannot add air to stripline or block automatic bounds', () => {
  const p=originals.microstrip,{values,si}=form('microstrip',p,'mm');
  Object.assign(values,{box_mode:'auto',air_mode:'auto',box_width:'',air_height:'-1'});
  assert.deepEqual(editableParameters('microstrip',values,'mm',p,new Set(),si),p);
  for(const key of ['box_width','air_height']) {
    const mode=key==='box_width'?'box_mode':'air_mode';values[mode]='fixed';
    assert.throws(()=>editableParameters('microstrip',values,'mm',p,new Set([mode]),si),/positive/);values[mode]='auto';
  }
  const st=form('stripline',originals.stripline,'mm');
  Object.assign(st.values,{box_mode:'auto',air_mode:'fixed',air_height:'-1'});
  assert.deepEqual(editableParameters('stripline',st.values,'mm',originals.stripline,new Set(['air_mode']),st.si),originals.stripline);
});
