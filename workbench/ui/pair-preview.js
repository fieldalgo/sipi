import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const browser = document.documentElement.dataset.runtime === 'browser';
const transport = browser ? new BrowserTransport() : new LocalTransport();
const supported = ['coupled_microstrip', 'coupled_stripline'];
const fields = ['width', 'gap', 'height', 'thickness', 'eps_r', 'box_width', 'air_height'];
let parameters = null, mesh = null, latest = null, baseline = null, busy = false, generation = 0;
const changed = new Set();
$('runtime-note').textContent = browser ? 'Calculations run in this browser. Design files are not uploaded. The first calculation loads the local engine assets.' : 'Local review build: calculations run on this computer through the SIPI engine. Design files are not uploaded.';
function status(message, error = false) { $('status').textContent = message; $('status').classList.toggle('error', error); }
function invalidate() { latest = null; $('result').hidden = true; $('failure').hidden = true; comparison(); }
function lock(value) {
  busy = value;
  for (const element of document.querySelectorAll('button,input,select')) element.disabled = value;
  $('cancel').disabled = false; $('cancel').hidden = !value;
  comparison();
}
function condition(record) {
  const p = {...record.request.parameters};
  if (record.result.design) p.width = record.result.design.width;
  const mm = value => `${(value * 1e3).toPrecision(8)} mm`;
  return [record.material.label, record.material.note || 'Not specified', record.request.template,
    String(p.eps_r), mm(p.width), mm(p.gap), mm(p.thickness),
    mm(p.plane_spacing ?? p.substrate_height), mm(p.box_width),
    p.air_height === undefined ? 'Not applicable' : mm(p.air_height),
    record.request.action === 'design' ? `Width search: ${record.request.design.target} Ω ± ${record.request.design.tolerance} Ω` : 'Single calculation',
    `${record.result.line.z_diff.toFixed(5)} Ω`, `${record.result.line.z_common.toFixed(5)} Ω`,
    record.result.design ? 'Separate refined target check passed; outer convergence not checked' : 'Single mesh; convergence not checked'];
}
function comparison() {
  $('keep-a').disabled = busy || !latest;
  $('clear-a').disabled = busy || !baseline;
  $('export-comparison').disabled = busy || !baseline || !latest;
  $('comparison-results').hidden = !baseline;
  $('comparison-status').textContent = baseline ? (latest ? 'A and B are completed calculations. Changed values are highlighted.' : 'A is retained. Edit the copied inputs and calculate to produce B.') : 'Calculate a condition to start a comparison.';
  $('comparison-rows').replaceChildren();
  if (!baseline) return;
  const labels = ['Material / condition', 'Source / measurement notes', 'Structure', 'Relative permittivity', 'Selected trace width', 'Edge-to-edge gap', 'Copper thickness', 'Substrate height / plane spacing', 'Box width', 'Air height', 'Calculation', 'Differential impedance', 'Common impedance', 'Checks'];
  const a = condition(baseline), b = latest ? condition(latest) : null;
  labels.forEach((label, i) => {
    const row = document.createElement('tr');
    const heading = document.createElement('th'); heading.scope = 'row'; heading.textContent = label; row.append(heading);
    for (const value of [a[i], b ? b[i] : 'Awaiting calculation']) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    if (b && a[i] !== b[i]) row.classList.add('changed');
    $('comparison-rows').append(row);
  });
}
function key(id) { return id === 'height' ? ($('template').value === 'coupled_stripline' ? 'plane_spacing' : 'substrate_height') : id; }
function input(action) {
  if (!$('inputs').reportValidity()) throw new Error('Check the highlighted cross-section input.');
  const p = parameters ? {...parameters} : {};
  for (const id of fields) {
    if (id === 'air_height' && $('template').value === 'coupled_stripline') continue;
    if (!parameters || changed.has(id)) p[key(id)] = Number($(id).value) * (id === 'eps_r' ? 1 : 1e-3);
  }
  return {action, template: $('template').value, parameters: p, ...(mesh ? {mesh: {...mesh}} : {})};
}
// Keep step="any": imported and optimized dimensions need not lie on a step grid.
// These controls change a value only after an explicit button or arrow-key action.
function numberControls() {
  const increments = {width: .01, gap: .01, height: .01, thickness: .001,
    eps_r: .1, box_width: .1, air_height: .1, lower: .01, upper: .01,
    target: 1, tolerance: .01};
  for (const [id, increment] of Object.entries(increments)) {
    const element = $(id), label = element.closest('label');
    element.setAttribute('aria-label', label.textContent.trim());
    const wrapper = document.createElement('span'); wrapper.className = 'number-control';
    element.before(wrapper); wrapper.append(element);
    const arrows = document.createElement('span'); arrows.className = 'number-arrows';
    wrapper.append(arrows);
    const nudge = direction => {
      if (element.disabled || element.value === '' || !Number.isFinite(element.valueAsNumber)) return;
      let value = Number((element.valueAsNumber + direction * increment).toPrecision(15));
      if (element.min !== '') value = Math.max(Number(element.min), value);
      if (element.max !== '') value = Math.min(Number(element.max), value);
      if (value === element.valueAsNumber) return;
      element.value = String(value);
      element.dispatchEvent(new Event('input', {bubbles: true}));
    };
    for (const [direction, action, symbol] of [[1, 'Increase', '▲'], [-1, 'Decrease', '▼']]) {
      const button = document.createElement('button'); button.type = 'button';
      button.dataset.direction = action; button.dataset.increment = String(increment);
      button.setAttribute('aria-controls', id); button.textContent = symbol;
      button.addEventListener('click', () => {nudge(direction); element.focus({preventScroll: true});});
      arrows.append(button);
    }
    element.addEventListener('keydown', event => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      event.preventDefault(); nudge(event.key === 'ArrowUp' ? 1 : -1);
    });
  }
}
function controls() {
  const strip = $('template').value === 'coupled_stripline';
  $('height-label').textContent = strip ? 'Plane spacing · mm' : 'Substrate height · mm';
  $('height').setAttribute('aria-label', $('height-label').textContent);
  for (const button of document.querySelectorAll('.number-arrows button')) {
    const label = $(button.getAttribute('aria-controls')).getAttribute('aria-label');
    const description = `${button.dataset.direction} ${label} by ${button.dataset.increment}`;
    button.setAttribute('aria-label', description); button.title = description;
  }
  $('air-field').hidden = strip;
  $('air_height').required = !strip;
}
function draw() {
  const strip = $('template').value === 'coupled_stripline';
  const width = Number($('width').value), gap = Number($('gap').value), height = Number($('height').value), thickness = Number($('thickness').value);
  const svg = $('section'); svg.replaceChildren();
  const node = (tag, attrs, text) => { const n = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [k,v] of Object.entries(attrs)) n.setAttribute(k, String(v)); if (text) n.textContent = text; svg.append(n); };
  if (![width,gap,height,thickness].every(Number.isFinite) || width <= 0 || gap <= 0 || height <= 0 || thickness < 0) { node('text',{x:24,y:120},'Enter valid dimensions to draw the schematic.'); return; }
  const scale = Math.min(400/(2*width+gap),150/(height+thickness)), bottom=225, top=bottom-height*scale, x=320-(2*width+gap)*scale/2;
  node('rect',{x:24,y:top,width:592,height:height*scale,class:'dielectric'});
  node('line',{x1:24,y1:bottom,x2:616,y2:bottom,class:'ground'});
  if(strip) node('line',{x1:24,y1:top,x2:616,y2:top,class:'ground'});
  const y=strip ? bottom-(height+thickness)*scale/2 : top-thickness*scale;
  for(const tx of [x,x+(width+gap)*scale]) node('rect',{x:tx,y,width:width*scale,height:Math.max(2,thickness*scale),class:'copper'});
  node('text',{x:26,y:254},strip ? 'Centred pair · uniform dielectric · two ground planes' : 'Air above · uniform substrate · lower ground plane');
}
function acceptEditable(value) {
  if (!supported.includes(value.template)) throw new Error('This preview opens only symmetric microstrip or stripline pairs.');
  const p=value.parameters;
  const allowed=['width','gap','thickness','eps_r','box_width', value.template === 'coupled_stripline' ? 'plane_spacing' : 'substrate_height', ...(value.template === 'coupled_microstrip' ? ['air_height'] : [])];
  const defaults={tan_delta:0,top_width:null,...(value.template==='coupled_stripline'?{trace_height:null}:{})};
  if(Object.keys(p).some(k=>!allowed.includes(k) && (!Object.hasOwn(defaults,k) || p[k]!==defaults[k]))) throw new Error('This design has settings outside the preview. Open it in the full workbench.');
  if(allowed.some(k=>!Number.isFinite(p[k]))) throw new Error('This preview requires explicit dimensions and calculation boundaries.');
  $('template').value=value.template;
  parameters={...p}; mesh={...value.document.mesh}; changed.clear();
  for(const id of fields) if(key(id) in p) $(id).value=String(p[key(id)]/(id==='eps_r'?1:1e-3));
  controls(); draw();
}
function download(name, value) {
  const url=URL.createObjectURL(new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type:'application/json'}));
  const a=document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function run(action, extra={}) {
  if(busy) return;
  invalidate(); const version=++generation;
  try {
    const request = action==='template-open' ? {action,...extra} : input(action);
    if(action==='design') {
      if(!$('goal').reportValidity()) throw new Error('Check target and width bounds.');
      request.design={target:Number($('target').value),bounds:[Number($('lower').value)*1e-3,Number($('upper').value)*1e-3],tolerance:Number($('tolerance').value)};
      if(request.design.bounds[0]>=request.design.bounds[1]) throw new Error('Minimum width must be below maximum width.');
    }
    lock(true); status(action==='design'?'Searching widths, then checking a separate refined mesh…':'Working…');
    const result=await transport.run(request);
    if(version!==generation) return;
    if(action==='template-open') {acceptEditable(result); $('material-label').value='Imported design — material not identified'; $('material-note').value=''; status('Design opened. Add material context and calculate to produce a fresh result.');}
    else if(action==='template-document') {download('sipi-pair-design.json',result.document_text); status('Editable design saved. Target-search settings are not part of this input file.');}
    else {
      if(![result.line?.z_diff,result.line?.z_common].every(Number.isFinite)) throw new Error('The engine did not return finite symmetric-mode impedances.');
      if(result.design) {
        parameters={...request.parameters,width:result.design.width}; mesh={...result.document.mesh}; changed.clear();
        $('width').value=String(parameters.width*1e3); draw();
      }
      latest={request,result,material:{label:$('material-label').value,note:$('material-note').value}};
      $('z-diff').textContent=result.line.z_diff.toFixed(3); $('z-common').textContent=result.line.z_common.toFixed(3);
      $('refinement').textContent=result.design ? `Selected width ${(result.design.width*1e3).toPrecision(7)} mm. Initial ${result.design.impedance.toFixed(5)} Ω; refined ${result.design.refined_impedance.toFixed(5)} Ω. Both meet the requested target tolerance.` : 'Single mesh result. Mesh and outer-boundary convergence have not been checked by this calculation.';
      $('details').textContent=JSON.stringify({engine:result.engine,mesh:result.document.mesh,line:result.line,design:result.design},null,2);
      $('result').hidden=false; status('Calculation complete. Review model limits before using the result.');
    }
  } catch(error) {
    if(version!==generation) return;
    invalidate(); status(error.message,true);
    if(error.history) {$('failure-data').textContent=JSON.stringify(error.history,null,2);$('failure').hidden=false;}
  } finally {if(version===generation) lock(false);}
}
$('inputs').addEventListener('submit',event=>{event.preventDefault();run('analyze');});
$('goal').addEventListener('submit',event=>{event.preventDefault();run('design');});
for(const id of [...fields,'target','lower','upper','tolerance','material-label','material-note']) $(id).addEventListener('input',()=>{++generation;changed.add(id);invalidate();draw();status('Inputs changed. Calculate to update the result.');});
$('template').addEventListener('change',()=>{++generation;parameters=null;mesh=null;changed.clear();invalidate();$('height').value=$('template').value==='coupled_stripline'?'1':'0.2';controls();draw();status('Structure changed. Calculate to update the result.');});
$('save').addEventListener('click',()=>run('template-document'));
$('open').addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',async()=>{
  const file=$('file').files[0]; $('file').value=''; if(!file || busy) return;
  const version=++generation; invalidate();
  if(file.size>200*1024){status('Design files must be at most 200 KiB.',true);return;}
  status('Reading design…');
  try{const text=await file.text();if(version===generation && !busy) await run('template-open',{text});}
  catch(error){if(version===generation){invalidate();status(error.message,true);}}
});
$('export').addEventListener('click',()=>{if(latest) download('sipi-pair-calculation.json',latest);});
$('keep-a').addEventListener('click',()=>{
  if (!latest || busy) return;
  baseline=structuredClone(latest); invalidate();
  status('A retained. Inputs are copied for B. Change material or stackup conditions, then calculate.');
});
$('clear-a').addEventListener('click',()=>{baseline=null;comparison();});
$('export-comparison').addEventListener('click',()=>{
  if (baseline && latest && !busy) download('sipi-pair-comparison.json', {schema:'sipi.preview-comparison/1',a:baseline,b:latest});
});
$('cancel').addEventListener('click',async()=>{
  ++generation; invalidate(); $('cancel').disabled=true;
  try{await transport.cancel();status('Calculation cancelled. No result retained.');}
  catch(error){status(error.message,true);}finally{lock(false);}
});
numberControls(); controls(); draw(); comparison();
