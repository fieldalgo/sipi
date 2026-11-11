export const scales = {mm: 1e-3, 'µm': 1e-6, mil: 25.4e-6};
export const lengthFields = ['width', 'top_width', 'height', 'lower_height', 'upper_height', 'trace_height', 'offset', 'thickness', 'gap', 'ground_gap', 'ground_width', 'coating_height', 'coating_thickness', 'box_width', 'air_height', 'lower_air_height', 'lower', 'upper'];
export const labels = {layered_coplanar_stripline: 'Two-dielectric coplanar', coupled_layered_coplanar_stripline: 'Two-dielectric coplanar pair', layered_stripline: 'Two-dielectric stripline', coupled_layered_stripline: 'Two-dielectric pair', broadside_stripline: 'Broadside pair', coplanar_stripline: 'Coplanar stripline', coupled_coplanar_stripline: 'Coplanar stripline pair', conformal_coated_unbacked_coplanar: 'Normal-film unbacked coplanar', coupled_conformal_coated_unbacked_coplanar: 'Normal-film unbacked pair', conformal_coated_grounded_coplanar: 'Normal-film grounded coplanar', coupled_conformal_coated_grounded_coplanar: 'Normal-film grounded pair', conformal_coated_microstrip: 'Normal-film microstrip', coupled_conformal_coated_microstrip: 'Normal-film pair', coated_unbacked_coplanar: 'Coated unbacked coplanar', coupled_coated_unbacked_coplanar: 'Coated unbacked pair',coupled_unbacked_coplanar: 'Unbacked coplanar pair', unbacked_coplanar: 'Unbacked coplanar', microstrip: 'Microstrip', stripline: 'Stripline', offset_stripline: 'Offset stripline', coupled_microstrip: 'Coupled pair', coupled_stripline: 'Coupled stripline', grounded_coplanar: 'Grounded coplanar', coupled_grounded_coplanar: 'Coupled coplanar', coated_microstrip: 'Planar coated microstrip', coupled_coated_microstrip: 'Planar coated pair', coated_grounded_coplanar: 'Planar coated coplanar', coupled_coated_grounded_coplanar: 'Planar coated coplanar pair'};
export const isLayeredInterface = template => ['layered_coplanar_stripline', 'coupled_layered_coplanar_stripline', 'layered_stripline', 'coupled_layered_stripline'].includes(template);
export const isStripline = template => ['layered_coplanar_stripline', 'coupled_layered_coplanar_stripline', 'layered_stripline', 'coupled_layered_stripline', 'broadside_stripline', 'stripline', 'coupled_stripline', 'offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template);
export const isPair = template => ['coupled_layered_coplanar_stripline', 'coupled_layered_stripline', 'broadside_stripline', 'coupled_coplanar_stripline', 'coupled_conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_grounded_coplanar', 'coupled_conformal_coated_microstrip', 'coupled_coated_unbacked_coplanar', 'coupled_unbacked_coplanar', 'coupled_microstrip', 'coupled_stripline', 'coupled_grounded_coplanar', 'coupled_coated_microstrip', 'coupled_coated_grounded_coplanar'].includes(template);
export const isUnbacked = template => ['conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar', 'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'unbacked_coplanar', 'coupled_unbacked_coplanar'].includes(template);
export const isCoplanar = template => ['layered_coplanar_stripline', 'coupled_layered_coplanar_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline', 'conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar', 'conformal_coated_grounded_coplanar', 'coupled_conformal_coated_grounded_coplanar', 'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'coupled_unbacked_coplanar', 'unbacked_coplanar', 'grounded_coplanar', 'coupled_grounded_coplanar', 'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar'].includes(template);
export const isNormalFilm = template => ['conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar', 'conformal_coated_grounded_coplanar', 'coupled_conformal_coated_grounded_coplanar', 'conformal_coated_microstrip', 'coupled_conformal_coated_microstrip'].includes(template);
export const isCoated = template => ['conformal_coated_unbacked_coplanar', 'coupled_conformal_coated_unbacked_coplanar', 'conformal_coated_grounded_coplanar', 'coupled_conformal_coated_grounded_coplanar', 'conformal_coated_microstrip', 'coupled_conformal_coated_microstrip', 'coated_unbacked_coplanar', 'coupled_coated_unbacked_coplanar', 'coated_microstrip', 'coupled_coated_microstrip', 'coated_grounded_coplanar', 'coupled_coated_grounded_coplanar'].includes(template);

// Explicit refinement of resolved settings; never mutate a saved design.
export function refinedMesh(mesh) {
  const keys = ['edge_size', 'far_size', 'grade', 'min_angle'];
  if (!mesh || Object.keys(mesh).length !== keys.length || keys.some(key => !Number.isFinite(mesh[key]))) throw new Error('Inspect a valid resolved mesh first.');
  const out = {...mesh, edge_size: mesh.edge_size / 2, far_size: mesh.far_size / 2, grade: mesh.grade / 2};
  if (out.edge_size <= 0 || out.far_size <= 0 || out.grade < 0 || !(out.min_angle > 0 && out.min_angle < 34)) throw new Error('This mesh cannot be refined further.');
  return out;
}

export function parameterFields(template) {
  return {...(isLayeredInterface(template) ? {lower_height: 'lower_height', upper_height: 'upper_height', lower_eps_r: 'lower_eps_r', upper_eps_r: 'upper_eps_r', lower_tan_delta: 'lower_tan_delta', upper_tan_delta: 'upper_tan_delta'} : {}), ...(template === 'broadside_stripline' ? {offset: 'offset'} : {}), width: 'width', top_width: 'top_width', thickness: 'thickness',
    height: isStripline(template) ? 'plane_spacing' : 'substrate_height', trace_height: 'trace_height',
    gap: 'gap', ground_gap: 'ground_gap', ground_width: 'ground_width', box_width: 'box_width', air_height: 'air_height', lower_air_height: 'lower_air_height', coating_height: 'coating_height', coating_thickness: 'coating_thickness',
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
      if (!Number.isFinite(value) || (id !== 'offset' && (id === 'thickness' && template !== 'broadside_stripline' ? value < 0 : value <= 0))) throw new Error(`${id} must be a valid length.`);
      entered[key] = value;
    }
  }
  if (!original) return entered;
  const out = {...original};
  for (const id of changed) {
    const key = fields[id];
    if (Object.hasOwn(entered, key)) out[key] = entered[key];
  }
  if (changed.has('profile') && template !== 'broadside_stripline') out.top_width = entered.top_width ?? null;
  if (template === 'coupled_stripline' && changed.has('placement')) out.trace_height = entered.trace_height ?? null;
  for (const [mode, key] of [['box_mode', 'box_width'], ...(!isStripline(template) ? [['air_mode', 'air_height']] : []), ...(isUnbacked(template) ? [['lower_air_mode', 'lower_air_height']] : [])]) {
    if (changed.has(mode)) out[key] = entered[key] ?? null;
  }
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
  const out = {width: positive('width') * scales[unit], thickness: positive('thickness', template !== 'broadside_stripline') * scales[unit]};
  if (isLayeredInterface(template)) {
    for (const side of ['lower', 'upper']) {
      out[`${side}_height`] = positive(`${side}_height`) * scales[unit];
      out[`${side}_eps_r`] = positive(`${side}_eps_r`);
      if (out[`${side}_eps_r`] < 1) throw new Error(`${side}_eps_r must be at least one.`);
      out[`${side}_tan_delta`] = positive(`${side}_tan_delta`, true);
    }
  } else {
    out.eps_r = positive('eps_r'); out.tan_delta = positive('tan_delta', true);
    out[isStripline(template) ? 'plane_spacing' : 'substrate_height'] = positive('height') * scales[unit];
  }
  if (['offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template)) out.trace_height = positive('trace_height') * scales[unit];
  if (template === 'coupled_stripline') {
    const placement = values.placement ?? 'centred';
    if (!['centred', 'fixed'].includes(placement)) throw new Error('Unknown vertical placement.');
    if (placement === 'fixed') out.trace_height = positive('trace_height') * scales[unit];
  }
  if (isPair(template) || isCoplanar(template)) out.gap = positive('gap') * scales[unit];
  if (isCoplanar(template)) out.ground_width = positive('ground_width') * scales[unit];
  if (isPair(template) && isCoplanar(template)) out.ground_gap = positive('ground_gap') * scales[unit];
  if (template === 'broadside_stripline') {
    if ((values.profile ?? 'rectangular') !== 'rectangular') throw new Error('Broadside conductors require a rectangular profile.');
    const raw = values.offset;
    const offset = typeof raw === 'number' ? raw : (typeof raw === 'string' && raw.trim() ? Number(raw) : NaN);
    if (!Number.isFinite(offset)) throw new Error('offset must be finite; use a signed horizontal length.');
    out.offset = offset * scales[unit];
  }
  if (values.profile === 'tapered') {
    out.top_width = positive('top_width') * scales[unit];
    if (out.thickness <= 0) throw new Error('A tapered trace needs positive copper thickness.');
  }
  if (isCoated(template)) {
    if (isNormalFilm(template)) out.coating_thickness = positive('coating_thickness') * scales[unit];
    else out.coating_height = positive('coating_height') * scales[unit];
    out.coating_eps_r = positive('coating_eps_r');
    out.coating_tan_delta = positive('coating_tan_delta', true);
    if (isNormalFilm(template) && out.top_width > out.width) throw new Error('Normal films require top width no greater than bottom width.');
    if (!isNormalFilm(template) && out.coating_height <= out.thickness) throw new Error('Coating height must exceed copper thickness.');
  }
  for (const [mode, key] of [['box_mode', 'box_width'], ...(!isStripline(template) ? [['air_mode', 'air_height']] : []), ...(isUnbacked(template) ? [['lower_air_mode', 'lower_air_height']] : [])]) {
    const selected = values[mode] ?? 'auto';
    if (!['auto', 'fixed'].includes(selected)) throw new Error(`Unknown ${key} mode.`);
    if (selected === 'fixed') out[key] = positive(key) * scales[unit];
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
  if (isLayeredInterface(template)) {
    delete fields.eps_r; delete fields.plane_spacing;
    Object.assign(fields, {lower_height: 'Lower layer height', upper_height: 'Upper layer height (includes copper)',
      lower_eps_r: 'Lower permittivity', upper_eps_r: 'Upper permittivity'});
  }
  if (p.top_width != null) fields.top_width = 'Top width';
  if (['coupled_stripline', 'offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template) && p.trace_height != null) fields.trace_height = 'Bottom-face height';
  if ('gap' in p) fields.gap = template === 'broadside_stripline' ? 'Vertical metal-face gap' : 'Bottom gap';
  if (template === 'broadside_stripline') fields.offset = 'Horizontal offset';
  if ('ground_gap' in p) fields.ground_gap = 'Signal–ground gap';
  if ('ground_width' in p) fields.ground_width = 'Ground width';
  if ('coating_height' in p) { fields.coating_height = 'Coating height'; fields.coating_eps_r = 'Coating permittivity'; }
  if ('coating_thickness' in p) { fields.coating_thickness = 'Normal coating thickness'; fields.coating_eps_r = 'Coating permittivity'; }
  return fields;
}

export function studyScale(name, unit) {
  return ['eps_r', 'coating_eps_r', 'lower_eps_r', 'upper_eps_r'].includes(name) ? 1 : scales[unit];
}

// This is only a drawing model. The Python template creates all solver inputs.
export function schematic(template, p) {
  if (isNormalFilm(template)) throw new Error('Inspect the engine geometry for normal films.');
  const h = isLayeredInterface(template) ? p.lower_height + p.upper_height : (p.substrate_height ?? p.plane_spacing);
  const strip = isStripline(template);
  const lowerAir = isUnbacked(template) ? (p.lower_air_height ?? 10 * h) : 0;
  const y = isLayeredInterface(template) ? p.lower_height : strip ? (p.trace_height ?? (h - p.thickness) / 2) : h + lowerAir;
  const signal = {name: 'signal', x: 0, width: p.width, top_width: p.top_width ?? p.width, y, thickness: p.thickness, ground: false};
  let traces = [signal];
  if (template === 'broadside_stripline') {
    traces = [{...signal, name: 'positive', x: -p.offset / 2, y: h / 2 - p.gap / 2 - p.thickness},
      {...signal, name: 'negative', x: p.offset / 2, y: h / 2 + p.gap / 2}];
  } else if (isPair(template)) {
    const x = (p.width + p.gap) / 2;
    traces = [{...signal, name: 'positive', x: -x}, {...signal, name: 'negative', x}];
  }
  if (isCoplanar(template)) {
    const x = isPair(template) ? p.width + p.gap / 2 + p.ground_gap + p.ground_width / 2 : (p.width + p.ground_width) / 2 + p.gap;
    traces.push({...signal, name: 'ground_left', x: -x, width: p.ground_width, top_width: p.ground_width, ground: true}, {...signal, name: 'ground_right', x, width: p.ground_width, top_width: p.ground_width, ground: true});
  }
  const layers = isLayeredInterface(template) ? [{name: 'lower', thickness: p.lower_height, eps_r: p.lower_eps_r}, {name: 'upper', thickness: p.upper_height, eps_r: p.upper_eps_r}] : [...(isUnbacked(template) ? [{name: 'lower_air', thickness: lowerAir, eps_r: 1}] : []), {name: strip ? 'dielectric' : 'substrate', thickness: h, eps_r: p.eps_r}];
  if (isCoated(template)) layers.push({name: 'planar coating', thickness: p.coating_height, eps_r: p.coating_eps_r});
  if (!strip) layers.push({name: 'air', thickness: Math.max(h * 1.1, p.thickness * 1.5), eps_r: 1});
  return {layers, traces, box: {width: Math.max(h * 5, ...traces.map(t => (Math.abs(t.x) + Math.max(t.width, t.top_width) / 2) * 2.5)), bottom: isUnbacked(template) ? 'open' : 'ground', top: strip ? 'ground' : 'open', sides: 'open'}};
}

// Display-only comparison of completed, ordered cross-section summaries.
export function compareLines(baseline, current) {
  const reject = reason => ({compatible: false, reason, rows: []});
  const names = baseline?.names;
  if (!Array.isArray(names) || ![1, 2].includes(names.length) ||
      !Array.isArray(current?.names) || names.length !== current.names.length ||
      names.some((name, i) => typeof name !== 'string' || name !== current.names[i]))
    return reject('Comparison requires the same ordered names for one or two signals.');
  const matrices = [['C', 'C', 'pF/m', 1e12], ['L', 'L', 'nH/m', 1e9], ['G_1GHz', 'G at 1 GHz', 'mS/m', 1e3]];
  for (const [key] of matrices) for (const line of [baseline, current]) {
    if (!Array.isArray(line[key]) || line[key].length !== names.length ||
        line[key].some(row => !Array.isArray(row) || row.length !== names.length || row.some(value => !Number.isFinite(value))))
      return reject('Both results must contain finite C, L and G matrices with matching dimensions.');
  }
  const rows = [];
  function add(key, label, unit, factor, before, after) {
    const delta = after - before;
    rows.push({key, label, unit, baseline: before * factor, current: after * factor,
      delta: delta * factor, percent: before === 0 ? null : 100 * delta / Math.abs(before)});
  }
  if (!baseline.scalar_summary_unavailable && !current.scalar_summary_unavailable) {
    const scalars = names.length === 1 ? [['z0', 'Characteristic impedance', 'Ω', 1], ['eps_eff', 'Effective permittivity', '1', 1], ['delay', 'Propagation delay', 'ns/m', 1e9]] :
      [['z_diff', 'Differential impedance', 'Ω', 1], ['z_common', 'Common-mode impedance', 'Ω', 1], ['z_even', 'Even-mode impedance', 'Ω', 1], ['z_odd', 'Odd-mode impedance', 'Ω', 1], ['eps_eff_even', 'Even-mode permittivity', '1', 1], ['eps_eff_odd', 'Odd-mode permittivity', '1', 1]];
    for (const [key, label, unit, factor] of scalars)
      if (Number.isFinite(baseline[key]) && Number.isFinite(current[key])) add(key, label, unit, factor, baseline[key], current[key]);
  }
  for (const [key, label, unit, factor] of matrices)
    for (let i = 0; i < names.length; i++) for (let j = 0; j < names.length; j++)
      add(`${key}:${i}:${j}`, `${label} [${names[i]}, ${names[j]}]`, unit, factor, baseline[key][i][j], current[key][i][j]);
  if (rows.some(row => ['baseline', 'current', 'delta', 'percent'].some(key => row[key] !== null && !Number.isFinite(row[key]))))
    return reject('The displayed difference exceeds the finite numeric range.');
  return {compatible: true, reason: '', rows};
}

// Display coordinates only; physical geometry validation belongs to the engine.
export function polygonDrawing(vertices) {
  if (!Array.isArray(vertices) || vertices.length < 3 || vertices.length > 16384)
    throw new Error('A displayed polygon needs 3–16384 vertices.');
  let left = Infinity, right = -Infinity, bottom = Infinity, top = -Infinity;
  const points = vertices.map(point => {
    if (!Array.isArray(point) || point.length !== 2 || !point.every(Number.isFinite))
      throw new Error('Polygon display coordinates must be finite numbers.');
    const [x, y] = point;
    left = Math.min(left, x); right = Math.max(right, x);
    bottom = Math.min(bottom, y); top = Math.max(top, y);
    return [x, y];
  });
  return {points, left, right, bottom, top};
}

export function checkDrawing(model) {
  if (!model || !Array.isArray(model.layers) || !Array.isArray(model.traces) ||
      !model.layers.length || !model.traces.length ||
      model.layers.length > 64 || model.traces.length > 64)
    throw new Error('The geometry preview supports 1–64 layers and conductors.');
  if (!Number.isFinite(model.box?.width) || model.box.width <= 0 ||
      model.layers.some(layer => !Number.isFinite(layer.thickness) || layer.thickness <= 0) ||
      !Number.isFinite(model.layers.reduce((sum, layer) => sum + layer.thickness, 0)))
    throw new Error('The geometry preview needs finite positive dimensions.');
  const regions = model.dielectric_regions ?? [];
  if (!Array.isArray(regions) || regions.length > 64)
    throw new Error('The geometry preview supports at most 64 local dielectric regions.');
  for (const region of regions) polygonDrawing(region.vertices);
  for (const trace of model.traces) {
    if (trace.kind === 'polygon') polygonDrawing(trace.vertices);
    else if (![trace.x, trace.y, trace.width, trace.thickness, trace.top_width ?? trace.width].every(Number.isFinite) ||
        trace.width <= 0 || (trace.top_width ?? trace.width) <= 0 || trace.thickness < 0)
      throw new Error('The geometry preview needs finite conductor dimensions.');
  }
}

// Display bounds only. The engine supplies and validates all geometry vertices.
export function drawingWindow(model, detail = false) {
  checkDrawing(model);
  if (typeof detail !== 'boolean') throw new Error('Unknown geometry view.');
  const full = {left: -model.box.width / 2, right: model.box.width / 2,
    bottom: 0, top: model.layers.reduce((sum, layer) => sum + layer.thickness, 0)};
  if (!detail) return {...full, detail: false, clipped: []};
  const boxes = model.traces.map(trace => trace.kind === 'polygon'
    ? polygonDrawing(trace.vertices)
    : {left: trace.x - Math.max(trace.width, trace.top_width ?? trace.width) / 2,
      right: trace.x + Math.max(trace.width, trace.top_width ?? trace.width) / 2,
      bottom: trace.y, top: trace.y + trace.thickness});
  const films = (model.dielectric_regions ?? []).map(region => polygonDrawing(region.vertices));
  let left = Math.min(...boxes.map(b => b.left)), right = Math.max(...boxes.map(b => b.right));
  let bottom = Math.min(...boxes.map(b => b.bottom), ...films.map(b => b.bottom));
  let top = Math.max(...boxes.map(b => b.top), ...films.map(b => b.top));
  const dx = Math.max((right - left) * .08, model.box.width * 1e-6);
  const dy = Math.max((top - bottom) * .3, full.top * .002);
  left = Math.max(full.left, left - dx); right = Math.min(full.right, right + dx);
  bottom = Math.max(full.bottom, bottom - dy); top = Math.min(full.top, top + dy);
  if (![left, right, bottom, top].every(Number.isFinite) || left >= right || bottom >= top)
    throw new Error('The conductor detail does not have finite display bounds.');
  const clipped = ['left', 'right', 'bottom', 'top'].filter(key =>
    key === 'left' || key === 'bottom' ? ({left, bottom})[key] > full[key] : ({right, top})[key] < full[key]);
  return {left, right, bottom, top, detail: true, clipped};
}
