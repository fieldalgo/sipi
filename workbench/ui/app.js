import {drawingWindow, checkDrawing, polygonDrawing, scales, lengthFields, labels, isAsymmetric, isLayeredInterface, isStripline, isPair, isCoplanar, isCoated, isNormalFilm, isUnbacked, refinedMesh, compareLines, editableParameters, parameterFields, format, schematic, studyFields, studyScale} from './model.js';
import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const inBrowser = document.documentElement.dataset.runtime === 'browser';
const transport = inBrowser ? new BrowserTransport() : new LocalTransport();
if (inBrowser) document.querySelector('.local').lastChild.textContent = ' Browser workspace';
let template = 'microstrip', unit = 'mm', imported = null, latest = null, busy = false;
let cancelling = false, closed = false, latestNetwork = null, latestStudy = null;
let runSequence = 0;
let geometryDetail = false;
let originalParameters = null, savedMesh = null, resolvedMesh = null, resolvedDomain = null;
let projectText = null, activeDesign = null, baseline = null;
const changedFields = new Set();
// Display changes never become physical edits to target or study bounds.
const studySI = {};
let savedSearchTolerance = null, networkOriginal = null;
const networkChanged = new Set();
const networkKeys = ['start_hz','stop_hz','points','length','z_ref','resistance'];
const networkFactors = [1e6,1e6,1,1e-3,1,1];
const networkFields = ["frequency-start", "frequency-stop", "frequency-points", "line-length", "reference-z", "series-r"];
const allFields = [...lengthFields, 'left_profile', 'right_profile', 'target_variable', 'profile', 'placement', 'box_mode', 'air_mode', 'lower_air_mode', 'eps_r', 'tan_delta', 'lower_eps_r', 'upper_eps_r', 'lower_tan_delta', 'upper_tan_delta', 'coating_eps_r', 'coating_tan_delta', 'target', 'tolerance'];
const lengthSI = Object.fromEntries(lengthFields.map(id => [id, Number($(id).value) * scales[unit]]));

function status(text, error = false) {
  $('status').textContent = text;
  $('status').classList.toggle('error', error);
}

function setBusy(value) {
  busy = value;
  for (const element of document.querySelectorAll('button, input, select')) element.disabled = value;
  $('cancel').disabled = false;
  $('cancel').hidden = !value;
  $('calculate').hidden = value;
  $('exit').disabled = false;
  if (imported) for (const element of $('inputs').elements) element.disabled = true;
  $('design').disabled = value || !!imported;
  $('save-editable').disabled = value || !!imported;
  for (const kind of ['design','study','network']) $(`${kind}-input-save`).disabled = value || !!imported;
  geometryFields(); studyControls();
  projectControls(); meshControls(); comparisonControls();
}

function meshControls() {
  const mesh = savedMesh ?? resolvedMesh;
  $('mesh-mode').textContent = imported ? 'Imported geometry · read only' : savedMesh ? 'Fixed mesh' : 'Automatic mesh';
  $('mesh-values').replaceChildren();
  for (const [key, label, scale, suffix] of [['edge_size', 'Edge size', 1e6, 'µm'], ['far_size', 'Far size', 1e6, 'µm'], ['grade', 'Growth', 1, ''], ['min_angle', 'Minimum angle', 1, '°']]) {
    const term = document.createElement('dt'); term.textContent = label;
    const value = document.createElement('dd'); value.dataset.meshKey = key;
    value.textContent = mesh ? `${Number((mesh[key] * scale).toPrecision(8))} ${suffix}`.trim() : '—';
    $('mesh-values').append(term, value);
  }
  $('mesh-inspect').disabled = busy || closed;
  $('mesh-refine').disabled = busy || closed || !!imported || !mesh;
  $('mesh-auto').disabled = busy || closed || !!imported || !savedMesh;
}

function resolvedAirHeight() {
  const height = resolvedDomain.layers.at(-1).thickness;
  if (imported || !isNormalFilm(template)) return height;
  const top = Math.max(...resolvedDomain.dielectric_regions.flatMap(r => r.vertices.map(p => p[1])));
  return resolvedDomain.layers.reduce((sum, layer) => sum + layer.thickness, 0) - top;
}

function domainControls() {
  $('domain-inputs').hidden = !!imported;
  $('air-domain-fields').hidden = isStripline(template);
  $('lower-air-domain-fields').hidden = !isUnbacked(template);
  $('lower-air-height-field').hidden = $('lower_air_mode').value !== 'fixed';
  $('lower_air_mode').disabled = busy || !!imported || !isUnbacked(template);
  $('box-width-field').hidden = $('box_mode').value !== 'fixed';
  $('air-height-field').hidden = $('air_mode').value !== 'fixed';
  $('box_mode').disabled = busy || !!imported;
  $('air_mode').disabled = busy || !!imported || isStripline(template);
  $('domain-inspect').disabled = busy || closed;
  $('domain-mode').textContent = imported ? 'Imported geometry · bounds read only' : resolvedDomain ? 'Resolved calculation bounds' : 'Bounds not inspected';
  const air = resolvedDomain && !imported && !isStripline(template) ? resolvedAirHeight() : null;
  const lowerAir = resolvedDomain?.layers[0]?.name === 'lower_air' ? resolvedDomain.layers[0].thickness : null;
  const total = resolvedDomain?.layers.reduce((sum, layer) => sum + layer.thickness, 0);
  $('domain-values').replaceChildren();
  for (const [key, label, value] of [['width', 'Box width', resolvedDomain?.box.width], ['height', 'Total height', total], ['air', isNormalFilm(template) && !imported ? 'Upper air clearance' : 'Air layer height', air], ...(isUnbacked(template) || lowerAir !== null ? [['lower_air', 'Lower air height', lowerAir]] : [])]) {
    const term = document.createElement('dt'); term.textContent = label;
    const item = document.createElement('dd'); item.dataset.domainKey = key;
    item.textContent = value == null ? '—' : `${Number((value / scales[unit]).toPrecision(10))} ${unit}`;
    $('domain-values').append(term, item);
  }
}

function comparisonControls() {
  $('comparison-pin').disabled = busy || closed || !latest?.line;
  $('comparison-clear').disabled = busy || closed || !baseline;
  $('comparison-table-wrap').hidden = true;
  $('comparison-rows').replaceChildren();
  $('comparison-details').hidden = !baseline;
  $('comparison-inputs').textContent = baseline ? JSON.stringify({
    baseline: {label: baseline.label, pinned_at: baseline.pinnedAt, engine: baseline.result.engine, document: baseline.result.document},
    current: latest?.line ? {engine: latest.engine, document: latest.document} : null,
  }, null, 2) : '';
  if (!baseline) {
    $('comparison-status').textContent = 'Calculate, then keep a result as the comparison baseline.';
    return;
  }
  const prefix = `Baseline: ${baseline.label}. `;
  if (!latest?.line) {
    $('comparison-status').textContent = prefix + 'Baseline retained. Calculate the current inputs to compare.';
    return;
  }
  const comparison = compareLines(baseline.result.line, latest.line);
  $('comparison-status').textContent = prefix + (comparison.compatible ? 'Current successful result compared below.' : comparison.reason);
  if (!comparison.compatible) return;
  const number = value => value === null ? '—' : String(Number(value.toPrecision(7)));
  for (const item of comparison.rows) {
    const row = document.createElement('tr'); row.dataset.comparisonKey = item.key;
    for (const value of [`${item.label} (${item.unit})`, number(item.baseline), number(item.current), number(item.delta), number(item.percent)]) {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    $('comparison-rows').append(row);
  }
  $('comparison-table-wrap').hidden = false;
}

function projectControls() {
  for (const id of ['project-duplicate', 'project-save']) $(id).disabled = busy || closed || !!imported;
  $('project-design').disabled = busy || closed || !projectText;
  $('project-label').disabled = busy || closed || !!imported;
  $('project-open').disabled = busy || closed;
}

function showProject() {
  if (!projectText) return;
  const project = JSON.parse(projectText);
  $('project-title').textContent = project.title;
  $('project-design').replaceChildren(...project.designs.map(design => {
    const option = document.createElement('option'); option.value = design.design_id;
    option.textContent = design.label; return option;
  }));
  $('project-design').value = activeDesign;
  const current = project.designs.find(design => design.design_id === activeDesign);
  $('project-label').value = current.label;
  const count = project.designs.reduce((sum, design) => sum + design.records.length, 0);
  $('project-note').textContent = 'Variants keep cross-section inputs and mesh. Save this file to resume later. Target, study, frequency-response settings and new results are not stored.' +
    (count ? ` ${count} existing saved record(s) are retained.` : '');
  projectControls();
}

function supportedProject(text) {
  const project = JSON.parse(text);
  for (const design of project.designs) {
    const input = JSON.parse(design.source_text);
    if (input?.schema !== 'sipi.template-section/1' || !Object.hasOwn(labels, input.template))
      throw new Error(`No editable form for design “${design.label}”. This workspace opens projects using its supported editable templates; the current project is unchanged.`);
  }
  return project;
}

async function projectCall(input, sequence) {
  if (new TextEncoder().encode(JSON.stringify(input)).length > 256*1024)
    throw new Error('Encoded project request exceeds 256 KiB. The current project is unchanged.');
  const result = await transport.run(input);
  if (sequence !== runSequence || closed) throw new DOMException('Project operation cancelled.', 'AbortError');
  return result;
}

async function snapshotProject(sequence) {
  const label = $('project-label').value;
  if (!label.trim()) throw new Error('Enter a design name before saving or switching.');
  const editable = await projectCall(request('template-document'), sequence);
  const id = activeDesign || crypto.randomUUID();
  const input = projectText ? {action:'project-update', project_text:projectText,
    design_id:id, text:editable.document_text, label} : {action:'project-create',
    text:editable.document_text, project_id:crypto.randomUUID(), design_id:id,
    title:'Cross-section designs', label};
  const result = await projectCall(input, sequence);
  return {text:result.project_text, id, editable};
}

async function changeProject(operation, target) {
  if (busy || closed || imported) return;
  if (projectText) $('project-design').value = activeDesign;
  const sequence = ++runSequence;
  setBusy(true);
  try {
    let snapshot = await snapshotProject(sequence);
    let restored = null;
    if (operation === 'duplicate') {
      const id = crypto.randomUUID();
      const result = await projectCall({action:'project-duplicate', project_text:snapshot.text,
        source_id:snapshot.id, design_id:id,
        label:`Design ${JSON.parse(snapshot.text).designs.length + 1}`}, sequence);
      snapshot = {...snapshot, text:result.project_text, id};
      restored = snapshot.editable;
    } else if (operation === 'switch') {
      const design = supportedProject(snapshot.text).designs.find(design => design.design_id === target);
      if (!design) throw new Error('The requested design is unavailable.');
      restored = await projectCall({action:'template-open', text:design.source_text}, sequence);
      snapshot.id = target;
    }
    if (restored) restoreEditable(restored);
    projectText = snapshot.text; activeDesign = snapshot.id; showProject();
    if (operation === 'save') {
      downloadText(projectText, 'sipi-project.json', 'application/json');
      status('Input project saved. Inputs and existing records are retained; new calculation results are not added.');
    } else status('Design ready. Edit its inputs or calculate; save the project file to keep your variants.');
  } catch (error) {
    if (sequence === runSequence && !closed && !cancelling) status(error.message, error.name !== 'AbortError');
  } finally { if (sequence === runSequence && !closed && !cancelling) setBusy(false); }
}

function clearResult() {
  latest = null;
  latestNetwork = null;
  $('network-result').hidden = true;
  $('result').hidden = true;
  $('history').hidden = true;
  latestStudy = null; $('study-result').hidden = true;
  resolvedMesh = null; resolvedDomain = null; meshControls(); domainControls(); comparisonControls();
  status('Inputs changed. Calculate to update the results.');
}

function values() { return Object.fromEntries(allFields.map(id => [id, $(id).value])); }
function currentParameters() { return editableParameters(template, values(), unit, originalParameters, changedFields, lengthSI); }
function request(action) {
  const mode = action.replace(/-document$/, '');
  const network = {};
  if (mode === 'network') {
    for (const id of networkFields) if (!$(id).reportValidity()) throw new Error('Check the frequency response inputs.');
    network.network = {start_hz: Number($('frequency-start').value)*1e6, stop_hz: Number($('frequency-stop').value)*1e6, points: Number($('frequency-points').value), length: Number($('line-length').value)*1e-3, resistance: Number($('series-r').value), z_ref: Number($('reference-z').value)};
    if (networkOriginal) networkFields.forEach((id,i) => { if (!networkChanged.has(id)) network.network[networkKeys[i]] = networkOriginal[networkKeys[i]]; });
  }
  if (imported) return {action, document_text: imported, ...network};
  for (const id of ['box_width', 'air_height']) {
    if (!$(id).disabled && !$(id).checkValidity()) {
      $('domain-settings').open = true; $(id).reportValidity();
      throw new Error('Check the domain bounds.');
    }
  }
  if (!$('inputs').reportValidity()) throw new Error('Check the highlighted input.');
  const input = {action, template, parameters: currentParameters(), ...(savedMesh ? {mesh: {...savedMesh}} : {}), ...network};
  if (mode === 'study') {
    const mode = $('study-mode').value;
    const count = mode === 'sweep' ? 1 : Number($('study-count').value);
    const variables = [];
    for (let i=1; i<=count; i++) {
      for (const suffix of ['low', 'high']) if (!$(`study-${suffix}-${i}`).reportValidity()) throw new Error('Check the study bounds.');
      const parameter = $(`study-variable-${i}`).value, bounds = studySI[i];
      if (bounds?.parameter !== parameter || !Number.isFinite(bounds.low) || !Number.isFinite(bounds.high)) throw new Error('Check the study bounds.');
      variables.push({parameter, lower:bounds.low, upper:bounds.high});
    }
    for (const id of ['study-points','study-seed']) if (!$(id).reportValidity()) throw new Error('Check study samples and seed.');
    input.study = {mode, variables, points:Number($('study-points').value), seed:Number($('study-seed').value)};
  }
  if (mode === 'design') {
    for (const id of ['target', 'lower', 'upper', 'tolerance']) if (!$(id).reportValidity()) throw new Error('Check the target and width bounds.');
    if (![lengthSI.lower, lengthSI.upper].every(value => Number.isFinite(value) && value > 0)) throw new Error('Check the target width bounds.');
    input.design = {target: Number($('target').value), bounds: [lengthSI.lower, lengthSI.upper], tolerance: Number($('tolerance').value)};
    if (isAsymmetric(template)) input.design.variable = $('target_variable').value;
    if (savedSearchTolerance !== null) input.design.search_tolerance = savedSearchTolerance;
  }
  return input;
}

function svgNode(name, attrs, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

// Wrapping changes only display text; the original label stays accessible.
function wrapGeometryLabel(node, text, x, step, maxWidth = 700) {
  const parts = Array.isArray(text) ? text : [text];
  const lines = [];
  node.setAttribute('aria-label', parts.join(' · '));
  for (const part of parts) {
    let rest = part;
    while (rest.length) {
      let low = 1, high = rest.length;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        node.textContent = rest.slice(0, middle);
        if (node.getBBox().width <= maxWidth) low = middle; else high = middle - 1;
      }
      let cut = low;
      const space = rest.lastIndexOf(' ', cut);
      if (cut < rest.length && space > cut / 2) cut = space;
      lines.push(rest.slice(0, cut)); rest = rest.slice(cut).trimStart();
    }
  }
  node.replaceChildren(...lines.map((line, index) =>
    svgNode('tspan', {x, dy: index ? step : 0}, line)));
  return lines.length;
}


function draw(model) {
  const svg = $('cross-section');
  svg.replaceChildren();
  svg.setAttribute('viewBox', '0 0 760 300');
  checkDrawing(model);
  const view = drawingWindow(model, geometryDetail);
  const height = view.top - view.bottom, width = view.right - view.left;
  svg.dataset.geometryView = geometryDetail ? 'detail' : 'full';
  svg.dataset.displayBounds = JSON.stringify(view);
  $('geometry-detail-note').hidden = !geometryDetail;
  $('geometry-detail-note').textContent = geometryDetail
    ? `Conductor detail · axes scaled separately. ${view.clipped.length ? 'Outer boundaries are cropped; use Full domain to see the calculation box.' : 'The complete calculation bounds are visible.'}` : '';
  let geometry = svg;
  if (geometryDetail) {
    const defs = svgNode('defs', {}), clip = svgNode('clipPath', {id: 'geometry-detail-clip'});
    clip.append(svgNode('rect', {x: 65, y: 35, width: 630, height: 210}));
    defs.append(clip); svg.append(defs);
    geometry = svgNode('g', {'clip-path': 'url(#geometry-detail-clip)'}); svg.append(geometry);
  }
  if (!Number.isFinite(height) || !Number.isFinite(width) || height <= 0 || width <= 0) return;
  const x = n => 65 + (n - view.left) / width * 630;
  const y = n => 245 - (n - view.bottom) / height * 210;
  // Size labels in the displayed viewport, independently of physical coordinates.
  const labelSize = geometryDetail ? Math.max(11, 11 * 760 / Math.max(svg.clientWidth, 232)) : 11;
  const labelStep = geometryDetail ? labelSize * 1.6 : 18;
  const layerLabels = [];
  let base = 0;
  model.layers.forEach(layer => {
    if (!Number.isFinite(layer.thickness) || layer.thickness <= 0) return;
    const top = base + layer.thickness;
    const low = Math.max(base, view.bottom), high = Math.min(top, view.top);
    base = top;
    if (high <= low) return;
    const air = layer.eps_r === 1;
    geometry.append(svgNode('rect', {x: 65, y: y(high), width: 630, height: 210 * (high - low) / height, fill: air ? '#f8fafb' : '#dceae8'}));
    layerLabels.push({x: 77, y: y((high + low) / 2) + 4, tip: y((high + low) / 2), anchor: 'start', kind: 'layer', fill: '#597b76', text: `${String(layer.name).slice(0, 30)} · εr ${format(layer.eps_r, 2)}`});
  });
  const regions = model.dielectric_regions ?? [];
  for (const region of regions) {
    const shape = polygonDrawing(region.vertices);
    const node = svgNode('polygon', {points: shape.points.map(([px, py]) => `${x(px)},${y(py)}`).join(' '),
      fill: region.eps_r === 1 ? '#f8fafb' : '#c7d9ed', stroke: '#688bac', 'stroke-width': .5,
      'data-region': region.name});
    node.append(svgNode('title', {}, `${region.name} · εr ${region.eps_r} · tan δ ${region.tan_delta}`));
    geometry.append(node);
  }
  const traceLabels = [];
  for (const trace of model.traces) {
    if (trace.kind === 'polygon') {
      const shape = polygonDrawing(trace.vertices);
      geometry.append(svgNode('polygon', {points: shape.points.map(([px, py]) => `${x(px)},${y(py)}`).join(' '),
        fill: '#b58b51', 'data-trace': trace.name}));
      traceLabels.push({x: x((shape.left + shape.right) / 2), y: y(shape.top) - 13,
        tip: y(shape.top), text: `${trace.ground ? 'GND' : String(trace.name).slice(0, 20)} · span ${format((shape.right - shape.left) / scales[unit])} ${unit}`});
      continue;
    }
    if (![trace.x, trace.y, trace.width, trace.thickness].every(Number.isFinite) || trace.width <= 0 || trace.thickness < 0) continue;
    const h = trace.thickness === 0 ? 4 : trace.thickness / height * 210;
    const topWidth = trace.top_width ?? trace.width;
    if (!Number.isFinite(topWidth) || topWidth <= 0) continue;
    const points = [[trace.x - trace.width/2, trace.y], [trace.x + trace.width/2, trace.y], [trace.x + topWidth/2, trace.y + trace.thickness], [trace.x - topWidth/2, trace.y + trace.thickness]];
    if (topWidth !== trace.width && trace.thickness > 0) geometry.append(svgNode('polygon', {points: points.map(([px, py]) => `${x(px)},${y(py)}`).join(' '), fill:'#b58b51', 'data-trace':trace.name}));
    else geometry.append(svgNode('rect', {x: x(trace.x - trace.width / 2), y: y(trace.y) - h, width: trace.width / width * 630, height: h, fill: '#b58b51', rx: 0.5}));
    traceLabels.push({x: x(trace.x), y: y(trace.y) - h - 13, tip: y(trace.y) - h,
      text: `${trace.ground ? 'GND' : String(trace.name).slice(0, 20)} · ${format(trace.width / scales[unit])} ${unit}`});
  }
  const fullHeight = model.layers.reduce((sum, layer) => sum + layer.thickness, 0);
  for (const [boundary, coordinate] of [['bottom', 0], ['top', fullHeight]]) {
    const py = y(coordinate);
    if (model.box[boundary] === 'ground' && coordinate >= view.bottom && coordinate <= view.top) {
      svg.append(svgNode('rect', {x: 65, y: py, width: 630, height: 5, fill: '#b58b51'}));
      svg.append(svgNode('text', {x: 695, y: py + (boundary === 'bottom' ? 22 : -10), fill: '#a0825c', 'font-size': 10, 'text-anchor': 'end'}, 'GROUND PLANE'));
    }
  }
  // Measure rendered text rather than estimating character widths. Keep the
  // geometry fixed and move crowded labels to a free row, with a leader back
  // to the conductor. Dense imported sections can extend below the drawing.
  const occupied = [...svg.querySelectorAll('text, rect[fill="#b58b51"], polygon[data-trace]')].map(node => node.getBBox());
  let bottom = 300;
  for (const label of [...traceLabels, ...layerLabels]) {
    const node = svgNode('text', {x: label.x, y: label.y, fill: label.fill ?? '#8f714e', 'font-size': labelSize, 'text-anchor': label.anchor ?? 'middle', 'data-geometry-label': label.kind ?? 'trace'}, label.text);
    svg.append(node);
    if (geometryDetail) wrapGeometryLabel(node, label.text, label.x, labelStep);
    const size = node.getBBox();
    const px = label.x + (size.x < 8 ? 8 - size.x : size.x + size.width > 752 ? 752 - size.x - size.width : 0);
    node.setAttribute('x', px);
    for (const span of node.querySelectorAll('tspan')) span.setAttribute('x', px);
    let box;
    for (let attempt = 0; attempt <= 32; attempt++) {
      const offset = attempt === 0 ? 0 : Math.ceil(attempt / 2) * labelStep * (attempt % 2 ? -1 : 1);
      // An invalid edit can draw copper beyond the nominal viewport. Place
      // the fallback below every occupied shape, not at the same blocked row.
      const floor = attempt < 32 ? bottom : occupied.reduce((low, b) => Math.max(low, b.y + b.height + 4), bottom);
      const py = attempt < 32 ? label.y + offset : floor + (geometryDetail ? labelSize + 12 : 18);
      node.setAttribute('y', py);
      box = node.getBBox();
      if (![box.x, box.y, box.width, box.height].every(Number.isFinite)) throw new Error('The geometry labels need finite display bounds.');
      const collision = box.y < 8 || (attempt < 32 && box.y + box.height > 280) ||
        occupied.some(b => box.x < b.x + b.width + 4 && b.x < box.x + box.width + 4 && box.y < b.y + b.height + 4 && b.y < box.y + box.height + 4);
      if (collision) {
        if (attempt === 32) throw new Error('The geometry labels could not be placed in finite display bounds.');
        continue;
      }
      break;
    }
    bottom = Math.max(bottom, box.y + box.height + 12);
    occupied.push(box);
    if (Math.abs(px - label.x) > 1 || Math.abs(Number(node.getAttribute('y')) - label.y) > 1) {
      svg.insertBefore(svgNode('line', {x1: label.x, y1: label.tip, x2: px,
        y2: label.tip < box.y ? box.y - 3 : box.y + box.height + 3,
        stroke: '#a0825c', 'stroke-width': 0.7}), node);
    }
    svg.insertBefore(svgNode('rect', {x: box.x - 3, y: box.y - 2, width: box.width + 6,
      height: box.height + 4, fill: '#ffffff', 'fill-opacity': 0.88, rx: 2}), node);
  }
  for (const region of regions) {
    const py = bottom + (geometryDetail ? labelStep : 12);
    svg.append(svgNode('rect', {x: 65, y: py - 8, width: 9, height: 9,
      fill: region.eps_r === 1 ? '#f8fafb' : '#c7d9ed', stroke: '#688bac', 'stroke-width': .5}));
    const label = svgNode('text', {x: 82, y: py, fill: '#4d6984', 'font-size': labelSize,
      'data-region-label': region.name});
    svg.append(label);
    let lines = 1;
    if (geometryDetail) lines = wrapGeometryLabel(label, [String(region.name).slice(0, 30),
      `εr ${format(region.eps_r, 3)} · tan δ ${format(region.tan_delta, 4)}`], 82, labelStep, 660);
    else label.textContent = `${String(region.name).slice(0, 30)} · εr ${format(region.eps_r, 3)} · tan δ ${format(region.tan_delta, 4)}`;
    bottom = py + (geometryDetail ? (lines - 1) * labelStep + 12 : 12);
  }
  svg.setAttribute('viewBox', `0 0 760 ${bottom}`);
}



function geometryViewControls() {
  const available = !!imported || (isNormalFilm(template) && !!resolvedDomain);
  if (!available) geometryDetail = false;
  $('geometry-view-controls').hidden = !available;
  for (const [id, detail] of [['geometry-full', false], ['geometry-detail', true]]) {
    $(id).disabled = busy || closed || !available;
    $(id).setAttribute('aria-pressed', String(geometryDetail === detail));
  }
}

function preview() {
  geometryViewControls();
  $('drawing-unit').textContent = unit;
  try {
    if (!imported && isNormalFilm(template) && !resolvedDomain) {
      $('cross-section').replaceChildren(svgNode('text', {x: 65, y: 145, fill: '#4d6984', 'font-size': 15}, 'Inspect geometry to view the current coating.'));
      $('cross-section').setAttribute('viewBox', '0 0 760 300');
      $('preview-label').textContent = 'Geometry not inspected';
      $('geometry-detail-note').hidden = true;
      return;
    }
    const model = imported ? JSON.parse(imported) : isNormalFilm(template) ? resolvedDomain : schematic(template, currentParameters());
    $('preview-label').textContent = imported || isNormalFilm(template) ? 'Engine geometry · axes scaled separately' : 'Schematic · not to scale';
    draw(model);
  } catch { $('cross-section').replaceChildren(); $('geometry-detail-note').hidden = true; }
}

function geometryFields() {
  const asymmetric = isAsymmetric(template);
  $('asymmetric-fields').hidden = !asymmetric;
  for (const id of ['uniform-profile-field', 'uniform-width-field', 'uniform-thickness-field']) $(id).hidden = asymmetric;
  for (const side of ['left', 'right']) $(`${side}-top-width-field`).hidden = $(`${side}_profile`).value !== 'tapered';
  $('asymmetric-geometry-note').textContent = isStripline(template) ? 'Each copper midpoint is halfway between the planes. Unequal thicknesses have different bottom heights. The total bottom-width span is centred; the gap is between bottom edges.' : 'Both copper bottom faces are at the substrate surface. Widths, thicknesses and top profiles are independent. The total bottom-width span is centred; the gap is between bottom edges.';
  $('target-variable-field').hidden = !asymmetric;
  $('target_variable').disabled = busy || !!imported || !asymmetric;
  $('target-description').textContent = asymmetric ? 'Choose the left or right bottom width. The other width, both thicknesses, any top widths and the gap stay fixed. Target the real lossless forward Vdiff/Idiff with Icommon=0 at launch; this is not an independent differential eigenmode. Both meshes must meet the requested tolerance.' : 'Search varies the bottom width; a tapered profile keeps its top width fixed. Both the initial and finer mesh must meet the target. Failed checks include evaluation history.';
  const layered = isLayeredInterface(template);
  $('uniform-height-field').hidden = layered;
  $('uniform-dielectric-fields').hidden = layered;
  $('layered-height-fields').hidden = !layered;
  $('layered-dielectric-fields').hidden = !layered;
  const broadside = template === 'broadside_stripline';
  $('broadside-fields').hidden = !broadside;
  $('profile').disabled = busy || !!imported || broadside || asymmetric;
  $('gap-label').textContent = broadside ? 'Vertical metal-face gap' : 'Bottom edge gap';
  $('top-width-field').hidden = asymmetric || $('profile').value !== 'tapered';
  $('placement-fields').hidden = !['coupled_stripline', 'offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template);
  $('placement-mode-field').hidden = ['offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template);
  $('trace-height-field').hidden = !['offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(template) && $('placement').value !== 'fixed';
  $('placement').disabled = busy || !!imported || template !== 'coupled_stripline';
  $('coating-fields').hidden = !isCoated(template);
  const normal = isNormalFilm(template);
  $('upper-air-mode-label').textContent = normal ? 'Upper air clearance' : 'Air layer height';
  $('upper-air-value-label').textContent = normal ? 'Upper air clearance' : 'Air height';
  geometryViewControls();
  $('coating-title').textContent = normal ? 'Normal-thickness coating' : 'Planar coating';
  $('coating-description').textContent = normal ? 'Thickness normal to the substrate and exposed copper tops and sides, including finite side grounds. Corners meet at straight miters. Only signals may taper; top width must not exceed bottom width. Upper air starts above the highest coating.' : 'Height from the substrate surface, including copper. Fills beside and above the trace with a flat top; not a conformal coating.';
  $('coating-height-field').hidden = normal;
  $('coating-thickness-field').hidden = !normal;
  $('geometry-inspect').hidden = !normal || !!imported;
  domainControls();
  // Inactive fields must not block validation of a different template/profile.
  for (const id of ['width', 'thickness', 'left_width', 'right_width', 'left_thickness', 'right_thickness', 'left_top_width', 'right_top_width', 'left_profile', 'right_profile', 'height', 'eps_r', 'tan_delta', 'lower_height', 'upper_height', 'lower_eps_r', 'upper_eps_r', 'lower_tan_delta', 'upper_tan_delta', 'top_width', 'trace_height', 'offset', 'gap', 'ground_gap', 'ground_width', 'box_width', 'air_height', 'lower_air_height', 'coating_height', 'coating_thickness', 'coating_eps_r', 'coating_tan_delta']) {
    $(id).disabled = busy || !!imported || !!$(id).closest('[hidden]');
  }
}

function history(rows) {
  const dimension = isAsymmetric(template) ? $('target_variable').value.replace('_', ' ') : 'width';
  $('history').hidden = !rows?.length;
  $('history-data').textContent = rows?.map((row, i) => `${i + 1}. ${row.stage.padEnd(10)}  ${dimension} ${format(row.parameter / scales[unit], 6)} ${unit}  ${format(row.impedance, 6)} Ω`).join('\n') || '';
}

function render(result) {
  latest = result;
  if (result.network) renderNetwork(result.network);
  if (result.study) renderStudy(result.study, result.runtime);
  const line = result.line;
  comparisonControls();
  if (!line) return;
  $('result').hidden = false;
  const forward = !!line.forward_launch;
  $('eps-metric').hidden = forward; $('delay-metric').hidden = forward;
  const unavailable = line.scalar_summary_unavailable;
  $('scalar-summary').hidden = !!unavailable;
  $('scalar-note').hidden = !unavailable && !forward;
  $('scalar-note').textContent = forward ? 'Real lossless forward Vdiff/Idiff with Icommon=0 at launch. This excludes conductor resistance and dielectric loss from the impedance diagnostic. Coupling is retained; independent differential/common eigenmodes, a scalar effective permittivity and a scalar delay are not inferred. Network calculations retain their supplied losses.' : unavailable ? `Scalar summary unavailable: ${unavailable}. Full matrices remain available.` : '';
  const pair = 'z_diff' in line;
  $('z-label').textContent = forward ? 'Forward differential (Ic=0)' : pair ? 'Differential impedance' : 'Characteristic impedance';
  $('z-value').textContent = format(forward ? line.z_diff_forward : pair ? line.z_diff : line.z0);
  $('eps-label').textContent = pair ? 'Odd-mode permittivity' : 'Effective permittivity';
  $('eps-value').textContent = format(pair ? line.eps_eff_odd : line.eps_eff);
  $('delay-label').textContent = pair ? 'Common-mode impedance' : 'Propagation delay';
  $('delay-value').textContent = format(pair ? line.z_common : line.delay * 1e9);
  $('delay-unit').textContent = pair ? 'Ω' : 'ns/m';
  $('matrices').replaceChildren();
  for (const [key, title, factor] of [['C', 'C · pF/m', 1e12], ['L', 'L · nH/m', 1e9], ['G_1GHz', 'G @ 1 GHz · mS/m', 1e3]]) {
    const panel = document.createElement('div'); panel.className = 'matrix';
    const heading = document.createElement('h3'); heading.textContent = title;
    const table = document.createElement('table'); table.setAttribute('aria-label', `${title}; signal order: ${line.names.join(', ')}`);
    for (const row of line[key]) {
      const tr = document.createElement('tr');
      for (const value of row) { const td = document.createElement('td'); td.textContent = format(value * factor); tr.append(td); }
      table.append(tr);
    }
    panel.append(heading, table); $('matrices').append(panel);
  }
  $('refinement').hidden = !result.design;
  if (result.design) {
    const d = result.design;
    const variable = d.variable ?? 'width', value = d.parameter ?? d.width;
    lengthSI[variable] = value;
    changedFields.add(variable);
    savedMesh = {...result.document.mesh};
    $(variable).value = String(Number((value / scales[unit]).toPrecision(10)));
    const label = variable === 'width' ? 'Width' : variable === 'left_width' ? 'Left width' : 'Right width';
    $('refinement').textContent = `${label} ${format(value / scales[unit], 6)} ${unit} · initial ${format(d.impedance, 5)} Ω · refined ${format(d.refined_impedance, 5)} Ω · mesh change ${format(d.mesh_change, 5)} Ω. Both meet the requested target tolerance.`;
    history(d.history);
  }
  resolvedMesh = {...result.document.mesh}; resolvedDomain = result.document; meshControls(); domainControls();
  // Normal films display the resolved engine geometry; other forms retain their schematic.
  preview();
}

function studyControls() {
  const mode = $('study-mode').value, locked = busy || !!imported;
  const second = mode !== 'sweep' && $('study-count').value === '2';
  $('study-second').hidden = !second;
  $('study-count').disabled = locked || mode === 'sweep';
  $('study-points').disabled = locked || mode === 'corners';
  $('study-seed').disabled = locked || mode !== 'monte_carlo';
  $('study-calculate').disabled = locked;
  for (let i=1;i<=2;i++) {
    const key = $(`study-variable-${i}`).value;
    const label = studyScale(key,unit) === 1 ? 'dimensionless' : unit;
    $(`study-unit-${i}`).textContent=label; $(`study-unit-upper-${i}`).textContent=label;
    for (const prefix of ['variable','low','high']) $(`study-${prefix}-${i}`).disabled = locked || (i===2 && !second);
  }
}

function displayStudyBounds(i, displayUnit = unit) {
  const key = $(`study-variable-${i}`).value, bounds = studySI[i];
  for (const side of ['low', 'high']) {
    const value = bounds?.parameter === key ? bounds[side] : NaN;
    $(`study-${side}-${i}`).value = Number.isFinite(value) ? String(Number((value / studyScale(key, displayUnit)).toPrecision(10))) : '';
  }
}

function resetStudyBounds(i) {
  try {
    const p = currentParameters(), key = $(`study-variable-${i}`).value, value = p[key];
    studySI[i] = {parameter:key,
      low:['eps_r','coating_eps_r','lower_eps_r','upper_eps_r'].includes(key) ? Math.max(1, value*.9) : value*.9,
      high:value === 0 ? .05*scales.mm : value*1.1};
    if (template === 'broadside_stripline' && key === 'offset') {
      const span = value === 0 ? .05 * scales.mm : Math.abs(value) * .1;
      studySI[i] = {parameter: key, low: value - span, high: value + span};
    }
    displayStudyBounds(i);
  } catch { /* Invalid nominal inputs are reported by the ordinary request path. */ }
}

function rememberStudyBound(i, side) {
  const parameter = $(`study-variable-${i}`).value, raw = $(`study-${side}-${i}`).value.trim();
  if (studySI[i]?.parameter !== parameter) studySI[i] = {parameter, low:NaN, high:NaN};
  studySI[i][side] = raw ? Number(raw)*studyScale(parameter, unit) : NaN;
}

function refreshStudyOptions(reset=false) {
  let p; try {p=currentParameters();} catch {return;}
  const choices=studyFields(template,p);
  for (let i=1;i<=2;i++) {
    const select=$(`study-variable-${i}`), previous=select.value;
    select.replaceChildren();
    for (const [key,label] of Object.entries(choices)) {const option=document.createElement('option');option.value=key;option.textContent=label;select.append(option);}
    select.value=previous in choices ? previous : i===1 ? (isAsymmetric(template) ? 'left_width' : 'width') : isLayeredInterface(template) ? 'lower_eps_r' : 'eps_r';
    if (reset || previous !== select.value) resetStudyBounds(i);
  }
}

function renderStudy(study, runtime) {
  latestStudy={...study, runtime:runtime ?? null}; $('study-result').hidden=false;
  const names=study.settings.variables.map(v=>v.parameter), s=study.summary;
  $('study-summary').textContent=s ? `${study.rows.length} samples · ${study.quantity} ${format(s.minimum)}–${format(s.maximum)} Ω · mean ${format(s.mean)} Ω · sample SD ${format(s.sample_std)} Ω. Sample statistics, not a guaranteed process range or yield.` : `${study.failed} sample(s) failed. No aggregate statistics; inspect the errors and refine the inputs or mesh.`;
  $('study-head').replaceChildren(); $('study-table').replaceChildren();
  const header=document.createElement('tr');
  for (const name of [...names.map(n=>`${n} (${studyScale(n,unit)===1?'1':unit})`),'Impedance (Ω)','Status']) {const cell=document.createElement('th');cell.textContent=name;header.append(cell);}
  $('study-head').append(header);
  for(const sample of study.rows) {
    const row=document.createElement('tr');
    for(const value of [...names.map(n=>format(sample.parameters[n]/studyScale(n,unit),6)),format(sample.impedance),sample.status==='complete'?'Complete':sample.error]) {const cell=document.createElement('td');cell.textContent=value;row.append(cell);}
    $('study-table').append(row);
  }
}

function studyCSV(study) {
  const names=study.settings.variables.map(v=>v.parameter);
  const quote=value=>'"'+String(value ?? '').replaceAll('"','""')+'"';
  const rows=[['sample',...names.map(n=>n+(['eps_r','coating_eps_r','lower_eps_r','upper_eps_r'].includes(n)?'_1':'_m')),study.quantity+'_ohm','status','error']];
  study.rows.forEach((row,i)=>rows.push([i+1,...names.map(n=>row.parameters[n]),row.impedance,row.status,row.error]));
  return rows.map(row=>row.map(quote).join(',')).join('\r\n')+'\r\n';
}

function renderNetwork(network) {
  latestNetwork = network;
  $('network-result').hidden = false;
  $('network-description').textContent = `${network.transmission} · ${network.settings.length*1000} mm · ${network.settings.resistance === 0 ? 'Perfect conductors (R = 0)' : `Supplied series R ${network.settings.resistance} Ω/m`} · ${network.ports.join(', ')}`;
  const coupled = !!network.crosstalk;
  for(const element of document.querySelectorAll('.crosstalk-only')) element.hidden=!coupled;
  $('crosstalk-note').hidden=!coupled;
  $('network-table').replaceChildren();
  network.frequency.forEach((f, i) => {
    const row = document.createElement('tr');
    const cells=[f/1e6, network.insertion_loss_db[i], network.return_loss_db[i], network.phase_deg[i]];
    if(coupled) cells.push(network.crosstalk.next_db[i], network.crosstalk.fext_db[i]);
    for (const v of cells) {
      const td = document.createElement('td'); td.textContent = format(v, 4); row.append(td);
    }
    $('network-table').append(row);
  });
  const svg = $('network-plot'); svg.replaceChildren();
  const low = Math.min(0, ...network.insertion_loss_db), high = Math.max(1, ...network.insertion_loss_db);
  const x = i => 65+i/(network.frequency.length-1)*590;
  const y = v => 175-(v-low)/(high-low)*145;
  svg.append(svgNode('path', {d: 'M65 25V175H655', stroke:'#93a6aa', fill:'none'}));
  svg.append(svgNode('polyline', {points: network.insertion_loss_db.map((v,i)=>`${x(i)},${y(v)}`).join(' '), stroke:'#147d70', 'stroke-width':2, fill:'none'}));
  for (const [px,py,text] of [[8,35,`${format(high,2)} dB`],[8,178,`${format(low,2)} dB`],[65,203,`${format(network.frequency[0]/1e6,1)} MHz`],[550,203,`${format(network.frequency.at(-1)/1e6,1)} MHz`]]) svg.append(svgNode('text',{x:px,y:py,fill:'#4e666b','font-size':11},text));
}

function downloadText(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function download(value) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + '\n'], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'sipi-cross-section.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function run(action) {
  if (busy) return;
  const sequence = ++runSequence;
  try {
    const input = request(['mesh-inspect', 'domain-inspect', 'geometry-inspect'].includes(action) ? 'document' : action);
    if (!['document', 'template-document', 'design-document', 'study-document', 'network-document', 'mesh-inspect', 'domain-inspect', 'geometry-inspect'].includes(action)) clearResult();
    setBusy(true);
    status(action === 'study' ? 'Calculating every sampled cross-section…' : action === 'network' ? 'Calculating the cross-section and frequency response…' : action === 'design' ? 'Searching the width range, then checking a finer mesh…' : action === 'analyze' ? (inBrowser ? 'Preparing the browser engine and calculating… The first load can take longer.' : 'Meshing the cross-section and solving locally…') : 'Validating the design file…');
    const result = await transport.run(input);
    if (sequence !== runSequence || closed) return;
    resolvedMesh = {...result.document.mesh}; resolvedDomain = result.document; meshControls(); domainControls();
    if (!imported && isNormalFilm(template)) preview();
    if (action === 'geometry-inspect') {
      status('Geometry inspected without solving. The coating uses the engine vertices; axes are scaled separately.');
    }
    else if (action === 'mesh-inspect') {
      status('Mesh settings inspected without solving or changing the design. Refinement is an explicit input change.');
    }
    else if (action === 'domain-inspect') {
      status('Domain bounds inspected without solving or changing inputs. Vary bounds and compare results to check boundary sensitivity.');
    }
    else if (['design-document','study-document','network-document'].includes(action)) {
      downloadText(result.document_text, `sipi-${action.split('-')[0]}-input.json`, 'application/json');
      status('Analysis input saved. Open this file to restore the section and settings, or run it in Saved analysis.');
    }
    else if (action === 'template-document') {
      downloadText(result.document_text, 'sipi-editable-design.json', 'application/json');
      status('Editable design saved with its parameters and resolved mesh.');
    }
    else if (action === 'document') { download(result.document); status('Design saved with its resolved mesh settings.'); }
    else { render(result); if (result.study?.failed) status('Study incomplete: failed samples are retained; summary statistics are withheld.', true); else status('Calculation complete. Check mesh and domain convergence before using these values.'); }
  } catch (error) {
    if (sequence === runSequence && !closed && !cancelling) { status(error.message, error.name !== 'AbortError'); history(error.history); }
  } finally { if (sequence === runSequence && !closed && !cancelling) setBusy(false); }
}

function chooseTemplate(name) {
    savedSearchTolerance = null; networkOriginal = null; networkChanged.clear();
    template = name; imported = null; geometryDetail = false;
    resolvedMesh = null; resolvedDomain = null;
    originalParameters = null; savedMesh = null; changedFields.clear();
    $('box_mode').value = 'auto'; $('air_mode').value = 'auto'; $('lower_air_mode').value = 'auto';
    $('placement').value = ['offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(name) ? 'fixed' : 'centred';
    if (isAsymmetric(name)) {
      const buried = isStripline(name);
      const defaults = {left_width: buried ? .3e-3 : .4e-3, right_width: buried ? .5e-3 : .65e-3,
        left_thickness: 35e-6, right_thickness: 50e-6, left_top_width: buried ? .25e-3 : .32e-3,
        right_top_width: buried ? .45e-3 : .55e-3, height: buried ? 1e-3 : .5e-3, gap: buried ? .4e-3 : .25e-3};
      for (const [id, value] of Object.entries(defaults)) {lengthSI[id] = value; $(id).value = String(Number((value / scales[unit]).toPrecision(10)));}
      $('eps_r').value = '4'; $('tan_delta').value = '.02';
      $('left_profile').value = 'rectangular'; $('right_profile').value = 'rectangular'; $('target_variable').value = 'left_width';
    }
    if (name === 'broadside_stripline') {
      $('profile').value = 'rectangular';
      if (lengthSI.thickness === 0) {
        lengthSI.thickness = 35e-6;
        $('thickness').value = String(Number((lengthSI.thickness / scales[unit]).toPrecision(10)));
      }
    }
    if (['offset_stripline', 'coplanar_stripline', 'coupled_coplanar_stripline'].includes(name)) {
      lengthSI.trace_height = (lengthSI.height - lengthSI.thickness) / 2;
      $('trace_height').value = String(Number((lengthSI.trace_height / scales[unit]).toPrecision(10)));
    }
    $('import-note').hidden = true;
    $('inputs').hidden = false;
    for (const element of $('inputs').elements) element.disabled = false;
    for (const b of document.querySelectorAll('[data-template]')) {
      b.classList.toggle('selected', b.dataset.template === name); b.setAttribute('aria-pressed', String(b.dataset.template === name));
    }
    $('height-label').textContent = isStripline(template) ? 'Plane spacing' : 'Substrate height';
    $('gap-field').hidden = !(isPair(template) || isCoplanar(template));
    $('ground-field').hidden = !isCoplanar(template);
    $('ground-gap-field').hidden = !(isPair(template) && isCoplanar(template));
    $('target-label').firstChild.textContent = isAsymmetric(template) ? 'Forward differential, Ic=0 (Ω)' : isPair(template) ? 'Differential target (Ω)' : 'Target impedance (Ω)';
    $('design').disabled = false;
    $('save-editable').disabled = busy;
    geometryFields(); refreshStudyOptions(true); studyControls(); clearResult(); preview(); projectControls();
}

function restoreEditable(restored) {
  geometryDetail = false;
  if (!Object.hasOwn(labels, restored.template)) throw new Error('No editable form is available for this template.');
  chooseTemplate(restored.template);
  originalParameters = {...restored.parameters};
  savedMesh = {...restored.document.mesh};
  meshControls();
  for (const [id, key] of Object.entries(parameterFields(template))) {
    const v = originalParameters[key];
    if (v == null) continue;
    if (lengthFields.includes(id)) { lengthSI[id] = v; $(id).value = String(Number((v / scales[unit]).toPrecision(10))); }
    else $(id).value = String(v);
  }
  $('profile').value = originalParameters.top_width == null ? 'rectangular' : 'tapered';
  if (isAsymmetric(template)) for (const side of ['left', 'right']) $(`${side}_profile`).value = originalParameters[`${side}_top_width`] == null ? 'rectangular' : 'tapered';
  $('placement').value = originalParameters.trace_height == null ? 'centred' : 'fixed';
  $('box_mode').value = originalParameters.box_width == null ? 'auto' : 'fixed';
  $('air_mode').value = originalParameters.air_height == null ? 'auto' : 'fixed';
  $('lower_air_mode').value = originalParameters.lower_air_height == null ? 'auto' : 'fixed';
  resolvedDomain = restored.document;
  geometryFields(); refreshStudyOptions(true); studyControls(); preview();
}
for (const button of document.querySelectorAll('[data-template]')) {
  button.addEventListener('click', () => chooseTemplate(button.dataset.template));
}
$('inputs').addEventListener('submit', event => event.preventDefault());
for (const id of allFields) $(id).addEventListener('input', () => {
  if (id === 'placement' && $('placement').value === 'fixed') {
    const value = (lengthSI.height - lengthSI.thickness) / 2;
    lengthSI.trace_height = value;
    $('trace_height').value = String(Number((value / scales[unit]).toPrecision(10)));
  }
  if (['box_mode', 'air_mode', 'lower_air_mode'].includes(id) && $(id).value === 'fixed' && resolvedDomain) {
    const field = id === 'box_mode' ? 'box_width' : id === 'lower_air_mode' ? 'lower_air_height' : 'air_height';
    const value = id === 'box_mode' ? resolvedDomain.box.width : id === 'lower_air_mode' ? resolvedDomain.layers[0].thickness : resolvedAirHeight();
    lengthSI[field] = value; $(field).value = String(Number((value / scales[unit]).toPrecision(10)));
  }
  if (lengthFields.includes(id)) {
    const raw = $(id).value.trim();
    lengthSI[id] = raw ? Number(raw) * scales[unit] : NaN;
  }
  changedFields.add(id);
  geometryFields(); refreshStudyOptions(); studyControls(); clearResult(); preview();
});
$('unit').addEventListener('change', () => {
  const next = $('unit').value;
  for (const id of lengthFields) $(id).value = String(Number((lengthSI[id] / scales[next]).toPrecision(10)));
  for (let i=1; i<=2; i++) displayStudyBounds(i, next);
  unit = next; studyControls();
  for (const label of document.querySelectorAll('.unit-label')) label.textContent = unit;
  preview();
  if (latest) render(latest);
  domainControls();
});
$('calculate').addEventListener('click', () => run('analyze'));
$('comparison-pin').addEventListener('click', () => {
  if (busy || closed || !latest?.line) return;
  baseline = {result: structuredClone(latest), label: `${$('project-label').value} · ${imported ? 'Imported geometry' : labels[template]}`, pinnedAt: new Date().toISOString()};
  comparisonControls();
});
$('comparison-clear').addEventListener('click', () => {
  if (busy || closed) return;
  baseline = null; comparisonControls();
});
$('mesh-inspect').addEventListener('click', () => run('mesh-inspect'));
$('domain-inspect').addEventListener('click', () => run('domain-inspect'));
$('geometry-inspect').addEventListener('click', () => run('geometry-inspect'));
let observedDrawingWidth = 0;
new ResizeObserver(entries => {
  const width = Math.round(entries[0].contentRect.width);
  if (width !== observedDrawingWidth) {
    observedDrawingWidth = width;
    if (geometryDetail) preview();
  }
}).observe($('cross-section'));
for (const [id, detail] of [['geometry-full', false], ['geometry-detail', true]]) {
  $(id).addEventListener('click', () => {
    if (busy || closed || (!imported && (!isNormalFilm(template) || !resolvedDomain))) return;
    geometryDetail = detail; preview();
  });
}
$('mesh-refine').addEventListener('click', () => {
  if (busy || closed || imported) return;
  try {
    const next = refinedMesh(savedMesh ?? resolvedMesh);
    savedMesh = next; clearResult();
    status('Fixed mesh refined: edge size, far size and growth halved. Recalculate and check convergence; this does not certify accuracy.');
  } catch (error) { status(error.message, true); }
});
$('mesh-auto').addEventListener('click', () => {
  if (busy || closed || imported) return;
  savedMesh = null; clearResult();
  status('Automatic mesh restored. Width targets use their finer initial mesh; saved designs resolve and retain actual settings.');
});
$('network-calculate').addEventListener('click', () => run('network'));
for (const kind of ['design','study','network']) $(`${kind}-input-save`).addEventListener('click', () => run(kind+'-document'));
$('tolerance').addEventListener('input', () => { savedSearchTolerance = null; });
$('touchstone-save').addEventListener('click', () => { if (latestNetwork) downloadText(latestNetwork.touchstone, `sipi-line.${latestNetwork.extension}`, 'text/plain'); });
for (const id of networkFields) $(id).addEventListener('input', () => { networkChanged.add(id); latestNetwork = null; if (latest) latest = {...latest, network: undefined}; $('network-result').hidden = true; status('Frequency inputs changed. Recalculate the response.'); });
$('study-calculate').addEventListener('click', () => run('study'));
$('study-save').addEventListener('click', () => { if(latestStudy) downloadText(JSON.stringify(latestStudy,null,2)+'\n','sipi-parameter-study.json','application/json'); });
$('study-csv').addEventListener('click', () => { if(latestStudy) downloadText(studyCSV(latestStudy),'sipi-parameter-study.csv','text/csv'); });
for (const id of ['study-mode','study-points','study-seed','study-count','study-variable-1','study-variable-2','study-low-1','study-high-1','study-low-2','study-high-2']) $(id).addEventListener('input', () => {
  if(id.startsWith('study-variable')) resetStudyBounds(Number(id.at(-1)));
  const bound = /^study-(low|high)-([12])$/.exec(id);
  if (bound) rememberStudyBound(Number(bound[2]), bound[1]);
  studyControls(); latestStudy=null; if(latest) latest={...latest,study:undefined}; $('study-result').hidden=true;
});
$('design').addEventListener('click', () => run('design'));
$('save').addEventListener('click', () => latest ? download(latest.document) : run('document'));
$('save-editable').addEventListener('click', () => run('template-document'));
$('open').addEventListener('click', () => $('file').click());
$('file').addEventListener('change', async () => {
  const file = $('file').files[0];
  $('file').value = '';
  if (!file || busy || closed) return;
  const sequence = ++runSequence;
  setBusy(true);
  try {
    if (file.size > 200 * 1024) throw new Error('Design files must be smaller than 200 KiB.');
    const text = await file.text(); const value = JSON.parse(text);
    if (sequence !== runSequence || closed) return;
    const analysisKind = /^sipi\.impedance-design\//.test(value?.schema) ? 'design' : /^sipi\.impedance-study\//.test(value?.schema) ? 'study' : value?.schema === 'sipi.quasistatic-line/1' ? 'network' : null;
    if (analysisKind) {
      if (projectText) throw new Error('Analysis settings cannot replace a section-only project. Use a separate workspace or Saved analysis.');
      const restored = await transport.run({action: analysisKind+'-open', text});
      if (sequence !== runSequence || closed) return;
      restoreEditable(restored);
      if (analysisKind === 'design') {
        const d=restored.design; $('target').value=String(d.target); $('tolerance').value=String(d.tolerance);
        savedSearchTolerance=d.search_tolerance;
        if (d.variable) $('target_variable').value=d.variable;
        for (const [i,id] of ['lower','upper'].entries()) {lengthSI[id]=d.bounds[i]; $(id).value=String(d.bounds[i]/scales[unit]);}
      } else if (analysisKind === 'study') {
        const d=restored.study; $('study-mode').value=d.mode; $('study-count').value=String(d.variables.length);
        $('study-points').value=String(d.points); $('study-seed').value=String(d.seed);
        d.variables.forEach((v,index) => {const i=index+1; $(`study-variable-${i}`).value=v.parameter; studySI[i]={parameter:v.parameter,low:v.lower,high:v.upper}; $(`study-low-${i}`).value=String(v.lower/studyScale(v.parameter,unit)); $(`study-high-${i}`).value=String(v.upper/studyScale(v.parameter,unit));});
        studyControls();
      } else {
        networkOriginal={...restored.network}; networkChanged.clear();
        networkFields.forEach((id,i) => {$(id).value=String(restored.network[networkKeys[i]]/networkFactors[i]);});
      }
      status(`Loaded ${file.name}. Section, mesh and ${analysisKind} settings restored without calculating.`);
      return;
    }
    if (value?.schema === 'sipi.template-section/1') {
      status('Validating the editable design…');
      const restored = await transport.run({action: 'template-open', text});
      if (sequence !== runSequence || closed) return;
      restoreEditable(restored);
      status(`Loaded ${file.name}. Edit the dimensions, calculate, or run a target search or study. Saved mesh settings are retained.`);
      return;
    }
    if (!['sipi.cross-section/1', 'sipi.cross-section/2', 'sipi.cross-section/3'].includes(value?.schema)) throw new Error('Choose a sipi.cross-section/1, /2 or /3 JSON design.');
    if (projectText) throw new Error('A geometry-only import cannot replace an editable project design. Open an editable design, or use a separate workspace.');
    if (value.schema === 'sipi.cross-section/3') {
      status('Validating polygon geometry…');
      const restored = await transport.run({action: 'document', document_text: text});
      if (sequence !== runSequence || closed) return;
      checkDrawing(restored.document);
    }
    imported = text; geometryDetail = false;
    originalParameters = null; savedMesh = null; changedFields.clear();
    clearResult(); preview();
    $('import-note').hidden = false;
    $('inputs').hidden = true;
    for (const b of document.querySelectorAll('[data-template]')) { b.classList.remove('selected'); b.setAttribute('aria-pressed', 'false'); }
    status(`Loaded ${file.name}. Calculate to validate and solve the imported design.`);
  } catch (error) { if (sequence === runSequence && !closed && !cancelling) status(error.message, true); }
  finally { if (sequence === runSequence && !closed && !cancelling) setBusy(false); }
});
$('project-duplicate').onclick = () => changeProject('duplicate');
$('project-save').onclick = () => changeProject('save');
$('project-design').onchange = () => changeProject('switch', $('project-design').value);
$('project-open').onclick = () => $('project-file').click();
$('project-file').onchange = async () => {
  const file = $('project-file').files[0]; $('project-file').value = '';
  if (!file || busy || closed) return;
  const sequence = ++runSequence; setBusy(true);
  try {
    if (file.size > 200*1024) throw new Error('Project files must be at most 200 KiB.');
    const text = await file.text();
    if (sequence !== runSequence || closed) return;
    const opened = await projectCall({action:'project-open', project_text:text}, sequence);
    const project = supportedProject(opened.project_text), first = project.designs[0];
    const restored = await projectCall({action:'template-open', text:first.source_text}, sequence);
    restoreEditable(restored);
    projectText = opened.project_text; activeDesign = first.design_id; showProject();
    status(`Opened ${file.name}. The first design is selected. Inputs and existing records are retained.`);
  } catch (error) {
    if (sequence === runSequence && !closed && !cancelling) status(error.message, error.name !== 'AbortError');
  } finally { if (sequence === runSequence && !closed && !cancelling) setBusy(false); }
};
$('cancel').addEventListener('click', async () => {
  const sequence = ++runSequence;
  cancelling = true;
  $('cancel').disabled = true;
  try { await transport.cancel(); if(sequence === runSequence && !closed) status('Calculation cancelled.'); }
  catch (error) { if(sequence === runSequence && !closed) status(error.message, true); }
  finally { cancelling = false; if(sequence === runSequence && !closed) setBusy(false); }
});
$('exit').addEventListener('click', async () => {
  ++runSequence;
  closed = true;
  try { await transport.close(); status('Application closed. You can close this browser tab.'); for (const element of document.querySelectorAll('button,input,select')) element.disabled = true; }
  catch (error) { closed = false; status(error.message, true); setBusy(false); }
});
geometryFields(); refreshStudyOptions(true); studyControls(); preview(); projectControls(); meshControls(); comparisonControls();
