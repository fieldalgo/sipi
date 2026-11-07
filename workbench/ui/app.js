import {scales, lengthFields, labels, parameters, format, schematic, studyFields, studyScale} from './model.js';
import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const inBrowser = document.documentElement.dataset.runtime === 'browser';
const transport = inBrowser ? new BrowserTransport() : new LocalTransport();
if (inBrowser) document.querySelector('.local').lastChild.textContent = ' Browser workspace';
let template = 'microstrip', unit = 'mm', imported = null, latest = null, busy = false;
let cancelling = false, closed = false, latestNetwork = null, latestStudy = null;
let runSequence = 0;
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
  geometryFields(); studyControls();
}

function clearResult() {
  latest = null;
  latestNetwork = null;
  $('network-result').hidden = true;
  $('result').hidden = true;
  $('history').hidden = true;
  latestStudy = null; $('study-result').hidden = true;
  status('Inputs changed. Calculate to update the results.');
}

function values() { return Object.fromEntries(allFields.map(id => [id, $(id).value])); }
function request(action) {
  const network = {};
  if (action === 'network') {
    for (const id of networkFields) if (!$(id).reportValidity()) throw new Error('Check the frequency response inputs.');
    network.network = {start_hz: Number($('frequency-start').value)*1e6, stop_hz: Number($('frequency-stop').value)*1e6, points: Number($('frequency-points').value), length: Number($('line-length').value)*1e-3, resistance: Number($('series-r').value), z_ref: Number($('reference-z').value)};
  }
  if (imported) return {action, document_text: imported, ...network};
  if (!$('inputs').reportValidity()) throw new Error('Check the highlighted input.');
  const input = {action, template, parameters: parameters(template, values(), unit), ...network};
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
  for (const trace of model.traces) {
    if (![trace.x, trace.y, trace.width, trace.thickness].every(Number.isFinite) || trace.width <= 0 || trace.thickness < 0) continue;
    const h = trace.thickness === 0 ? 4 : trace.thickness / height * 210;
    const topWidth = trace.top_width ?? trace.width;
    if (!Number.isFinite(topWidth) || topWidth <= 0) continue;
    const points = [[trace.x - trace.width/2, trace.y], [trace.x + trace.width/2, trace.y], [trace.x + topWidth/2, trace.y + trace.thickness], [trace.x - topWidth/2, trace.y + trace.thickness]];
    if (topWidth !== trace.width && trace.thickness > 0) svg.append(svgNode('polygon', {points: points.map(([px, py]) => `${x(px)},${y(py)}`).join(' '), fill:'#b58b51', 'data-trace':trace.name}));
    else svg.append(svgNode('rect', {x: x(trace.x - trace.width / 2), y: y(trace.y) - h, width: trace.width / width * 630, height: h, fill: '#b58b51', rx: 0.5}));
    svg.append(svgNode('text', {x: x(trace.x), y: y(trace.y) - h - 13, fill: '#8f714e', 'font-size': 11, 'text-anchor': 'middle'}, `${trace.ground ? 'GND' : String(trace.name).slice(0, 20)} · ${format(trace.width / scales[unit])} ${unit}`));
  }
  for (const [boundary, py] of [['bottom', 245], ['top', 35]]) {
    if (model.box[boundary] === 'ground') {
      svg.append(svgNode('rect', {x: 65, y: py, width: 630, height: 5, fill: '#b58b51'}));
      svg.append(svgNode('text', {x: 695, y: py + (boundary === 'bottom' ? 22 : -10), fill: '#a0825c', 'font-size': 10, 'text-anchor': 'end'}, 'GROUND PLANE'));
    }
  }
}

function preview() {
  $('drawing-unit').textContent = unit;
  try {
    const model = imported ? JSON.parse(imported) : schematic(template, parameters(template, values(), unit));
    draw(model);
  } catch { $('cross-section').replaceChildren(); }
}

function geometryFields() {
  $('top-width-field').hidden = $('profile').value !== 'tapered';
  $('coating-fields').hidden = template !== 'coated_microstrip';
  // Inactive fields must not block validation of a different template/profile.
  for (const id of ['top_width', 'coating_height', 'coating_eps_r', 'coating_tan_delta']) {
    $(id).disabled = busy || !!imported || (id === 'top_width' ? $('profile').value !== 'tapered' : template !== 'coated_microstrip');
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
    $('width').value = String(Number((d.width / scales[unit]).toPrecision(10)));
    $('refinement').textContent = `Width ${format(d.width / scales[unit], 6)} ${unit} · initial ${format(d.impedance, 5)} Ω · refined ${format(d.refined_impedance, 5)} Ω · mesh change ${format(d.mesh_change, 5)} Ω. Both meet the requested target tolerance.`;
    history(d.history);
  }
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
    const p=parameters(template,values(),unit), key=$(`study-variable-${i}`).value;
    const value=p[key]/studyScale(key,unit);
    $(`study-low-${i}`).value=String(['eps_r','coating_eps_r'].includes(key) ? Math.max(1,value*.9) : value*.9);
    $(`study-high-${i}`).value=String(value === 0 ? .05*scales.mm/scales[unit] : value*1.1);
  } catch { /* Invalid nominal inputs are reported by the ordinary request path. */ }
}

function refreshStudyOptions(reset=false) {
  let p; try {p=parameters(template,values(),unit);} catch {return;}
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
    const input = request(action);
    if (action !== 'document') clearResult();
    setBusy(true);
    status(action === 'study' ? 'Calculating every sampled cross-section…' : action === 'network' ? 'Calculating the cross-section and frequency response…' : action === 'design' ? 'Searching the width range, then checking a finer mesh…' : action === 'analyze' ? (inBrowser ? 'Preparing the browser engine and calculating… The first load can take longer.' : 'Meshing the cross-section and solving locally…') : 'Validating the design file…');
    const result = await transport.run(input);
    if (sequence !== runSequence || closed) return;
    if (action === 'document') { download(result.document); status('Design saved with its resolved mesh settings.'); }
    else { render(result); if (result.study?.failed) status('Study incomplete: failed samples are retained; summary statistics are withheld.', true); else status('Calculation complete. Check mesh and domain convergence before using these values.'); }
  } catch (error) {
    if (sequence === runSequence && !closed && !cancelling) { status(error.message, error.name !== 'AbortError'); history(error.history); }
  } finally { if (sequence === runSequence && !closed && !cancelling) setBusy(false); }
}

for (const button of document.querySelectorAll('[data-template]')) {
  button.addEventListener('click', () => {
    template = button.dataset.template; imported = null;
    $('import-note').hidden = true;
    $('inputs').hidden = false;
    for (const element of $('inputs').elements) element.disabled = false;
    for (const b of document.querySelectorAll('[data-template]')) {
      b.classList.toggle('selected', b === button); b.setAttribute('aria-pressed', String(b === button));
    }
    $('height-label').textContent = template === 'stripline' ? 'Plane spacing' : 'Substrate height';
    $('gap-field').hidden = !['coupled_microstrip', 'grounded_coplanar'].includes(template);
    $('ground-field').hidden = template !== 'grounded_coplanar';
    $('target-label').firstChild.textContent = template === 'coupled_microstrip' ? 'Differential target (Ω)' : 'Target impedance (Ω)';
    $('design').disabled = false;
    geometryFields(); refreshStudyOptions(true); studyControls(); clearResult(); preview();
  });
}
$('inputs').addEventListener('submit', event => event.preventDefault());
for (const id of allFields) $(id).addEventListener('input', () => {
  if (lengthFields.includes(id)) lengthSI[id] = Number($(id).value) * scales[unit];
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
$('open').addEventListener('click', () => $('file').click());
$('file').addEventListener('change', async () => {
  const file = $('file').files[0];
  $('file').value = '';
  if (!file) return;
  try {
    if (file.size > 200 * 1024) throw new Error('Design files must be smaller than 200 KiB.');
    const text = await file.text(); const value = JSON.parse(text);
    if (!['sipi.cross-section/1', 'sipi.cross-section/2'].includes(value?.schema)) throw new Error('Choose a sipi.cross-section/1 or /2 JSON design.');
    imported = text;
    clearResult(); preview(); setBusy(false);
    $('import-note').hidden = false;
    $('inputs').hidden = true;
    for (const b of document.querySelectorAll('[data-template]')) { b.classList.remove('selected'); b.setAttribute('aria-pressed', 'false'); }
    status(`Loaded ${file.name}. Calculate to validate and solve the imported design.`);
  } catch (error) { status(error.message, true); }
});
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
geometryFields(); refreshStudyOptions(true); studyControls(); preview();
