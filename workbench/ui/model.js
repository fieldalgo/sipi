export const scales = {mm: 1e-3, mil: 25.4e-6};
export const lengthFields = ['width', 'top_width', 'height', 'thickness', 'gap', 'ground_width', 'coating_height', 'lower', 'upper'];
export const labels = {microstrip: 'Microstrip', stripline: 'Stripline', coupled_microstrip: 'Coupled pair', coupled_stripline: 'Coupled stripline', grounded_coplanar: 'Grounded coplanar', coated_microstrip: 'Planar coated microstrip'};
export const isStripline = template => ['stripline', 'coupled_stripline'].includes(template);
export const isPair = template => ['coupled_microstrip', 'coupled_stripline'].includes(template);

// Explicit refinement of resolved settings; never mutate a saved design.
export function refinedMesh(mesh) {
  const keys = ['edge_size', 'far_size', 'grade', 'min_angle'];
  if (!mesh || Object.keys(mesh).length !== keys.length || keys.some(key => !Number.isFinite(mesh[key]))) throw new Error('Inspect a valid resolved mesh first.');
  const out = {...mesh, edge_size: mesh.edge_size / 2, far_size: mesh.far_size / 2, grade: mesh.grade / 2};
  if (out.edge_size <= 0 || out.far_size <= 0 || out.grade < 0 || !(out.min_angle > 0 && out.min_angle < 34)) throw new Error('This mesh cannot be refined further.');
  return out;
}

export function parameterFields(template) {
  return {width: 'width', top_width: 'top_width', thickness: 'thickness',
    height: isStripline(template) ? 'plane_spacing' : 'substrate_height',
    gap: 'gap', ground_width: 'ground_width', coating_height: 'coating_height',
    eps_r: 'eps_r', tan_delta: 'tan_delta', coating_eps_r: 'coating_eps_r',
    coating_tan_delta: 'coating_tan_delta'};
}

// Display rounding and unit changes must not become physical input edits.
// Original parameters also retain inputs which have no field in this form.
export function editableParameters(template, values, unit, original, changed, lengthSI) {
  const entered = parameters(template, values, unit);
  const fields = parameterFields(template);
  for (const id of lengthFields) {
    const key = fields[id];
    if (key in entered && Object.hasOwn(lengthSI, id)) {
      const value = lengthSI[id];
      if (!Number.isFinite(value) || (id === 'thickness' ? value < 0 : value <= 0)) throw new Error(`${id} must be a valid length.`);
      entered[key] = value;
    }
  }
  if (!original) return entered;
  const out = {...original};
  for (const id of changed) {
    const key = fields[id];
    if (Object.hasOwn(entered, key)) out[key] = entered[key];
  }
  if (changed.has('profile')) out.top_width = entered.top_width ?? null;
  return out;
}

export function parameters(template, values, unit) {
  if (!(template in labels) || !(unit in scales)) throw new Error('Unknown template or unit.');
  const positive = (key, allowZero = false) => {
    const raw = values[key];
    const v = typeof raw === 'number' ? raw : (typeof raw === 'string' && raw.trim() ? Number(raw) : NaN);
    if (!Number.isFinite(v) || (allowZero ? v < 0 : v <= 0)) throw new Error(`${key} must be ${allowZero ? 'nonnegative' : 'positive'} and finite.`);
    return v;
  };
  const out = {width: positive('width') * scales[unit], thickness: positive('thickness', true) * scales[unit], eps_r: positive('eps_r'), tan_delta: positive('tan_delta', true)};
  out[isStripline(template) ? 'plane_spacing' : 'substrate_height'] = positive('height') * scales[unit];
  if (isPair(template) || template === 'grounded_coplanar') out.gap = positive('gap') * scales[unit];
  if (template === 'grounded_coplanar') out.ground_width = positive('ground_width') * scales[unit];
  if (values.profile === 'tapered') {
    out.top_width = positive('top_width') * scales[unit];
    if (out.thickness <= 0) throw new Error('A tapered trace needs positive copper thickness.');
  }
  if (template === 'coated_microstrip') {
    out.coating_height = positive('coating_height') * scales[unit];
    out.coating_eps_r = positive('coating_eps_r');
    out.coating_tan_delta = positive('coating_tan_delta', true);
    if (out.coating_height <= out.thickness) throw new Error('Coating height must exceed copper thickness.');
  }
  return out;
}

export function format(value, digits = 3) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
}

export function convert(value, from, to) {
  return Number(value) * scales[from] / scales[to];
}

export function studyFields(template, p) {
  const fields = {width: 'Bottom width', eps_r: 'Substrate permittivity',
    [isStripline(template) ? 'plane_spacing' : 'substrate_height']: isStripline(template) ? 'Plane spacing' : 'Substrate height', thickness: 'Copper thickness'};
  if (p.top_width != null) fields.top_width = 'Top width';
  if ('gap' in p) fields.gap = 'Bottom gap';
  if ('coating_height' in p) { fields.coating_height = 'Coating height'; fields.coating_eps_r = 'Coating permittivity'; }
  return fields;
}

export function studyScale(name, unit) {
  return ['eps_r', 'coating_eps_r'].includes(name) ? 1 : scales[unit];
}

// This is only a drawing model. The Python template creates all solver inputs.
export function schematic(template, p) {
  const h = p.substrate_height ?? p.plane_spacing;
  const strip = isStripline(template);
  const y = strip ? (p.trace_height ?? (h - p.thickness) / 2) : h;
  const signal = {name: 'signal', x: 0, width: p.width, top_width: p.top_width ?? p.width, y, thickness: p.thickness, ground: false};
  let traces = [signal];
  if (isPair(template)) {
    const x = (p.width + p.gap) / 2;
    traces = [{...signal, name: 'positive', x: -x}, {...signal, name: 'negative', x}];
  } else if (template === 'grounded_coplanar') {
    const x = (p.width + p.ground_width) / 2 + p.gap;
    traces.push({...signal, name: 'ground_left', x: -x, width: p.ground_width, top_width: p.ground_width, ground: true}, {...signal, name: 'ground_right', x, width: p.ground_width, top_width: p.ground_width, ground: true});
  }
  const layers = [{name: strip ? 'dielectric' : 'substrate', thickness: h, eps_r: p.eps_r}];
  if (template === 'coated_microstrip') layers.push({name: 'planar coating', thickness: p.coating_height, eps_r: p.coating_eps_r});
  if (!strip) layers.push({name: 'air', thickness: Math.max(h * 1.1, p.thickness * 1.5), eps_r: 1});
  return {layers, traces, box: {width: Math.max(h * 5, ...traces.map(t => (Math.abs(t.x) + Math.max(t.width, t.top_width) / 2) * 2.5)), bottom: 'ground', top: strip ? 'ground' : 'open', sides: 'open'}};
}
