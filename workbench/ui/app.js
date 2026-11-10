import {scales, lengthFields, labels, isStripline, isPair, isCoplanar, refinedMesh, editableParameters, parameterFields, format, schematic, studyFields, studyScale} from './model.js';
import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const inBrowser = document.documentElement.dataset.runtime === 'browser';
const transport = inBrowser ? new BrowserTransport() : new LocalTransport();
if (inBrowser) document.querySelector('.local').lastChild.textContent = ' Browser workspace';
let template = 'microstrip', unit = 'mm', imported = null, latest = null, busy = false;
let cancelling = false, closed = false, latestNetwork = null, latestStudy = null;
let runSequence = 0;
let originalParameters = null, savedMesh = null, resolvedMesh = null;
let projectText = null, activeDesign = null;
const changedFields = new Set();
const networkFields = ["frequency-start", "frequency-stop", "frequency-points", "line-length", "reference-z", "series-r"];
const allFields = [...lengthFields, 'profile', 'eps_r', 'tan_delta', 'coating_eps_r', 'coating_tan_delta', 'target', 'tolerance'];
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
  geometryFields(); studyControls();
  projectControls(); meshControls();
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
  resolvedMesh = null; meshControls();
  status('Inputs changed. Calculate to update the results.');
}

function values() { return Object.fromEntries(allFields.map(id => [id, $(id).value])); }
function currentParameters() { return editableParameters(template, values(), unit, originalParameters, changedFields, lengthSI); }
function request(action) {
  const network = {};
  if (action === 'network') {
    for (const id of networkFields) if (!$(id).reportValidity()) throw new Error('Check the frequency response inputs.');
    network.network = {start_hz: Number($('frequency-start').value)*1e6, stop_hz: Number($('frequency-stop').value)*1e6, points: Number($('frequency-points').value), length: Number($('line-length').value)*1e-3, resistance: Number($('series-r').value), z_ref: Number($('reference-z').value)};
  }
  if (imported) return {action, document_text: imported, ...network};
  if (!$('inputs').reportValidity()) throw new Error('Check the highlighted input.');
  const input = {action, template, parameters: currentParameters(), ...(savedMesh ? {mesh: {...savedMesh}} : {}), ...network};
  if (action === 'study') {
    const mode = $('study-mode').value;
    const count = mode === 'sweep' ? 1 : Number($('study-count').value);
    const variables = [];
    for (let i=1; i<=count; i++) {
      for (const suffix of ['low', 'high']) if (!$(`study-${suffix}-${i}`).reportValidity()) throw new Error('Check the study bounds.');
      const parameter = $(`study-variable-${i}`).value, factor = studyScale(parameter, unit);
      variables.push({parameter, lower:Number($(`study-low-${i}`).value)*factor, upper:Number($(`study-high-${i}`).value)*factor});
    }
    for (const id of ['study-points','study-seed']) if (!$(id).reportValidity()) throw new Error('Check study samples and seed.');
    input.study = {mode, variables, points:Number($('study-points').value), seed:Number($('study-seed').value)};
  }
  if (action === 'design') {
    for (const id of ['target', 'lower', 'upper', 'tolerance']) if (!$(id).reportValidity()) throw new Error('Check the target and width bounds.');
    input.design = {target: Number($('target').value), bounds: [Number($('lower').value) * scales[unit], Number($('upper').value) * scales[unit]], tolerance: Number($('tolerance').value)};
  }
  return input;
}

function svgNode(name, attrs, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== undefined) node.textContent = text;
  return node;
}

function draw(model) {
  const svg = $('cross-section');
  svg.replaceChildren();
  svg.setAttribute('viewBox', '0 0 760 300');
  if (!model || !Array.isArray(model.layers) || !Array.isArray(model.traces) || model.layers.length > 64 || model.traces.length > 64) return;
  const height = model.layers.reduce((a, layer) => a + layer.thickness, 0);
  const width = model.box?.width;
  if (!Number.isFinite(height) || !Number.isFinite(width) || height <= 0 || width <= 0) return;
  const x = n => 65 + (n / width + 0.5) * 630;
  const y = n => 245 - n / height * 210;
  let base = 0;
  model.layers.forEach(layer => {
    if (!Number.isFinite(layer.thickness) || layer.thickness <= 0) return;
    const top = base + layer.thickness;
    const air = layer.eps_r === 1;
    svg.append(svgNode('rect', {x: 65, y: y(top), width: 630, height: 210 * layer.thickness / height, fill: air ? '#f8fafb' : '#dceae8'}));
    svg.append(svgNode('text', {x: 77, y: y((top + base) / 2) + 4, fill: '#72928e', 'font-size': 11}, `${String(layer.name).slice(0, 30)} · εr ${format(layer.eps_r, 2)}`));
    base = top;
  });
  const traceLabels = [];
  for (const trace of model.traces) {
    if (![trace.x, trace.y, trace.width, trace.thickness].every(Number.isFinite) || trace.width <= 0 || trace.thickness < 0) continue;
    const h = trace.thickness === 0 ? 4 : trace.thickness / height * 210;
    const topWidth = trace.top_width ?? trace.width;
    if (!Number.isFinite(topWidth) || topWidth <= 0) continue;
    const points = [[trace.x - trace.width/2, trace.y], [trace.x + trace.width/2, trace.y], [trace.x + topWidth/2, trace.y + trace.thickness], [trace.x - topWidth/2, trace.y + trace.thickness]];
    if (topWidth !== trace.width && trace.thickness > 0) svg.append(svgNode('polygon', {points: points.map(([px, py]) => `${x(px)},${y(py)}`).join(' '), fill:'#b58b51', 'data-trace':trace.name}));
    else svg.append(svgNode('rect', {x: x(trace.x - trace.width / 2), y: y(trace.y) - h, width: trace.width / width * 630, height: h, fill: '#b58b51', rx: 0.5}));
    traceLabels.push({x: x(trace.x), y: y(trace.y) - h - 13, tip: y(trace.y) - h,
      text: `${trace.ground ? 'GND' : String(trace.name).slice(0, 20)} · ${format(trace.width / scales[unit])} ${unit}`});
  }
  for (const [boundary, py] of [['bottom', 245], ['top', 35]]) {
    if (model.box[boundary] === 'ground') {
      svg.append(svgNode('rect', {x: 65, y: py, width: 630, height: 5, fill: '#b58b51'}));
      svg.append(svgNode('text', {x: 695, y: py + (boundary === 'bottom' ? 22 : -10), fill: '#a0825c', 'font-size': 10, 'text-anchor': 'end'}, 'GROUND PLANE'));
    }
  }
  // Measure rendered text rather than estimating character widths. Keep the
  // geometry fixed and move crowded labels to a free row, with a leader back
  // to the conductor. Dense imported sections can extend below the drawing.
  const occupied = [...svg.querySelectorAll('text, rect[fill="#b58b51"], polygon')].map(node => node.getBBox());
  let bottom = 300;
  for (const label of traceLabels) {
    const node = svgNode('text', {x: label.x, y: label.y, fill: '#8f714e', 'font-size': 11, 'text-anchor': 'middle'}, label.text);
    svg.append(node);
    const size = node.getBBox();
    const px = Math.max(8 + size.width / 2, Math.min(752 - size.width / 2, label.x));
    node.setAttribute('x', px);
    let box;
    for (let attempt = 0; ; attempt++) {
      const offset = attempt === 0 ? 0 : Math.ceil(attempt / 2) * 18 * (attempt % 2 ? -1 : 1);
      const py = attempt < 32 ? label.y + offset : bottom + 18;
      node.setAttribute('y', py);
      box = node.getBBox();
      if (box.y < 8 || (attempt < 32 && box.y + box.height > 280)) continue;
      if (occupied.some(b => box.x < b.x + b.width + 4 && b.x < box.x + box.width + 4 && box.y < b.y + b.height + 4 && b.y < box.y + box.height + 4)) continue;
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
  svg.setAttribute('viewBox', `0 0 760 ${bottom}`);
}

function preview() {
  $('drawing-unit').textContent = unit;
  try {
    const model = imported ? JSON.parse(imported) : schematic(template, currentParameters());
    draw(model);
  } catch { $('cross-section').replaceChildren(); }
}

function geometryFields() {
  $('top-width-field').hidden = $('profile').value !== 'tapered';
  $('coating-fields').hidden = template !== 'coated_microstrip';
  // Inactive fields must not block validation of a different template/profile.
  for (const id of ['top_width', 'gap', 'ground_gap', 'ground_width', 'coating_height', 'coating_eps_r', 'coating_tan_delta']) {
    $(id).disabled = busy || !!imported || !!$(id).closest('[hidden]');
  }
}

function history(rows) {
  $('history').hidden = !rows?.length;
  $('history-data').textContent = rows?.map((row, i) => `${i + 1}. ${row.stage.padEnd(10)}  width ${format(row.parameter / scales[unit], 6)} ${unit}  ${format(row.impedance, 6)} Ω`).join('\n') || '';
}

function render(result) {
  latest = result;
  if (result.network) renderNetwork(result.network);
  if (result.study) renderStudy(result.study, result.runtime);
  const line = result.line;
  if (!line) return;
  $('result').hidden = false;
  const unavailable = line.scalar_summary_unavailable;
  $('scalar-summary').hidden = !!unavailable;
  $('scalar-note').hidden = !unavailable;
  $('scalar-note').textContent = unavailable ? `Scalar summary unavailable: ${unavailable}. Full matrices remain available.` : '';
  const pair = 'z_diff' in line;
  $('z-label').textContent = pair ? 'Differential impedance' : 'Characteristic impedance';
  $('z-value').textContent = format(pair ? line.z_diff : line.z0);
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
    lengthSI.width = d.width;
    changedFields.add('width');
    savedMesh = {...result.document.mesh};
    $('width').value = String(Number((d.width / scales[unit]).toPrecision(10)));
    $('refinement').textContent = `Width ${format(d.width / scales[unit], 6)} ${unit} · initial ${format(d.impedance, 5)} Ω · refined ${format(d.refined_impedance, 5)} Ω · mesh change ${format(d.mesh_change, 5)} Ω. Both meet the requested target tolerance.`;
    history(d.history);
  }
  resolvedMesh = {...result.document.mesh}; meshControls();
  // Retain a useful schematic rather than squeezing the signal into the full air box.
  preview();
  $('preview-label').textContent = 'Schematic · not to scale';
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

function resetStudyBounds(i) {
  try {
    const p=currentParameters(), key=$(`study-variable-${i}`).value;
    const value=p[key]/studyScale(key,unit);
    $(`study-low-${i}`).value=String(['eps_r','coating_eps_r'].includes(key) ? Math.max(1,value*.9) : value*.9);
    $(`study-high-${i}`).value=String(value === 0 ? .05*scales.mm/scales[unit] : value*1.1);
  } catch { /* Invalid nominal inputs are reported by the ordinary request path. */ }
}

function refreshStudyOptions(reset=false) {
  let p; try {p=currentParameters();} catch {return;}
  const choices=studyFields(template,p);
  for (let i=1;i<=2;i++) {
    const select=$(`study-variable-${i}`), previous=select.value;
    select.replaceChildren();
    for (const [key,label] of Object.entries(choices)) {const option=document.createElement('option');option.value=key;option.textContent=label;select.append(option);}
    select.value=previous in choices ? previous : i===1 ? 'width' : 'eps_r';
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
  const rows=[['sample',...names.map(n=>n+(['eps_r','coating_eps_r'].includes(n)?'_1':'_m')),study.quantity+'_ohm','status','error']];
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
    const input = request(action === 'mesh-inspect' ? 'document' : action);
    if (!['document', 'template-document', 'mesh-inspect'].includes(action)) clearResult();
    setBusy(true);
    status(action === 'study' ? 'Calculating every sampled cross-section…' : action === 'network' ? 'Calculating the cross-section and frequency response…' : action === 'design' ? 'Searching the width range, then checking a finer mesh…' : action === 'analyze' ? (inBrowser ? 'Preparing the browser engine and calculating… The first load can take longer.' : 'Meshing the cross-section and solving locally…') : 'Validating the design file…');
    const result = await transport.run(input);
    if (sequence !== runSequence || closed) return;
    resolvedMesh = {...result.document.mesh}; meshControls();
    if (action === 'mesh-inspect') {
      status('Mesh settings inspected without solving or changing the design. Refinement is an explicit input change.');
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
    template = name; imported = null;
    originalParameters = null; savedMesh = null; changedFields.clear();
    $('import-note').hidden = true;
    $('inputs').hidden = false;
    for (const element of $('inputs').elements) element.disabled = false;
    for (const b of document.querySelectorAll('[data-template]')) {
      b.classList.toggle('selected', b.dataset.template === name); b.setAttribute('aria-pressed', String(b.dataset.template === name));
    }
    $('height-label').textContent = isStripline(template) ? 'Plane spacing' : 'Substrate height';
    $('gap-field').hidden = !(isPair(template) || template === 'grounded_coplanar');
    $('ground-field').hidden = !isCoplanar(template);
    $('ground-gap-field').hidden = template !== 'coupled_grounded_coplanar';
    $('target-label').firstChild.textContent = isPair(template) ? 'Differential target (Ω)' : 'Target impedance (Ω)';
    $('design').disabled = false;
    $('save-editable').disabled = busy;
    geometryFields(); refreshStudyOptions(true); studyControls(); clearResult(); preview(); projectControls();
}

function restoreEditable(restored) {
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
  geometryFields(); refreshStudyOptions(true); studyControls(); preview();
}
for (const button of document.querySelectorAll('[data-template]')) {
  button.addEventListener('click', () => chooseTemplate(button.dataset.template));
}
$('inputs').addEventListener('submit', event => event.preventDefault());
for (const id of allFields) $(id).addEventListener('input', () => {
  if (lengthFields.includes(id)) lengthSI[id] = Number($(id).value) * scales[unit];
  changedFields.add(id);
  geometryFields(); refreshStudyOptions(); studyControls(); clearResult(); preview();
});
$('unit').addEventListener('change', () => {
  const next = $('unit').value;
  for (const id of lengthFields) $(id).value = String(Number((lengthSI[id] / scales[next]).toPrecision(10)));
  for (let i=1; i<=2; i++) { const key=$(`study-variable-${i}`).value; for (const side of ['low','high']) $(`study-${side}-${i}`).value=String(Number($(`study-${side}-${i}`).value)*studyScale(key,unit)/studyScale(key,next)); }
  unit = next; studyControls();
  for (const label of document.querySelectorAll('.unit-label')) label.textContent = unit;
  preview();
  if (latest) render(latest);
});
$('calculate').addEventListener('click', () => run('analyze'));
$('mesh-inspect').addEventListener('click', () => run('mesh-inspect'));
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
$('touchstone-save').addEventListener('click', () => { if (latestNetwork) downloadText(latestNetwork.touchstone, `sipi-line.${latestNetwork.extension}`, 'text/plain'); });
for (const id of networkFields) $(id).addEventListener('input', () => { latestNetwork = null; if (latest) latest = {...latest, network: undefined}; $('network-result').hidden = true; status('Frequency inputs changed. Recalculate the response.'); });
$('study-calculate').addEventListener('click', () => run('study'));
$('study-save').addEventListener('click', () => { if(latestStudy) downloadText(JSON.stringify(latestStudy,null,2)+'\n','sipi-parameter-study.json','application/json'); });
$('study-csv').addEventListener('click', () => { if(latestStudy) downloadText(studyCSV(latestStudy),'sipi-parameter-study.csv','text/csv'); });
for (const id of ['study-mode','study-points','study-seed','study-count','study-variable-1','study-variable-2','study-low-1','study-high-1','study-low-2','study-high-2']) $(id).addEventListener('input', () => {
  if(id.startsWith('study-variable')) resetStudyBounds(Number(id.at(-1)));
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
    if (value?.schema === 'sipi.template-section/1') {
      status('Validating the editable design…');
      const restored = await transport.run({action: 'template-open', text});
      if (sequence !== runSequence || closed) return;
      restoreEditable(restored);
      status(`Loaded ${file.name}. Edit the dimensions, calculate, or run a target search or study. Saved mesh settings are retained.`);
      return;
    }
    if (!['sipi.cross-section/1', 'sipi.cross-section/2'].includes(value?.schema)) throw new Error('Choose a sipi.cross-section/1 or /2 JSON design.');
    if (projectText) throw new Error('A geometry-only import cannot replace an editable project design. Open an editable design, or use a separate workspace.');
    imported = text;
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
geometryFields(); refreshStudyOptions(true); studyControls(); preview(); projectControls(); meshControls();
