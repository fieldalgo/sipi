import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const browser = document.documentElement.dataset.runtime === 'browser';
const transport = browser ? new BrowserTransport() : new LocalTransport();
const supported = ['coupled_microstrip', 'coupled_stripline'];
const fields = ['width', 'gap', 'height', 'thickness', 'eps_r', 'box_width', 'air_height'];
let parameters = null, mesh = null, latest = null, baseline = null, busy = false, generation = 0, activeArea = 'analysis';
const changed = new Set();
// Original illustrative inputs; these are not vendor grades or impedance guarantees.
const presets = [
  {id:'surface', name:'Surface pair', family:'Surface routing', template:'coupled_microstrip', width:.3, gap:.2, height:.2, thickness:.035, eps_r:4, box_width:8, air_height:2},
  {id:'compact', name:'Compact surface', family:'Surface routing', template:'coupled_microstrip', width:.18, gap:.15, height:.12, thickness:.018, eps_r:4.1, box_width:8, air_height:2},
  {id:'buried', name:'Buried pair', family:'Internal routing', template:'coupled_stripline', width:.3, gap:.2, height:1, thickness:.035, eps_r:4, box_width:8, air_height:2},
  {id:'thin', name:'Thin core pair', family:'Internal routing', template:'coupled_stripline', width:.16, gap:.16, height:.6, thickness:.018, eps_r:3.8, box_width:8, air_height:2},
];
let activePreset = 'surface', focusedDimension = null;
function presetState() {
  const current = presets.find(p => p.id === activePreset);
  $('preset-state').textContent = current ? current.name : 'Custom dimensions';
  for (const button of document.querySelectorAll('[data-preset]')) button.setAttribute('aria-pressed', String(button.dataset.preset === activePreset));
}
function applyPreset(preset) {
  if (busy) return;
  ++generation; parameters=null; mesh=null; changed.clear(); activePreset=preset.id;
  $('template').value=preset.template;
  for (const id of fields) $(id).value=String(preset[id]);
  $('material-label').value='Example dielectric — not a supplier grade'; $('material-note').value='';
  invalidate(); controls(); draw(); presetState();
  status(`${preset.name} loaded. Calculate to check these example dimensions.`, false, 'analysis');
}
function presetControls() {
  let family = '';
  for (const p of presets) {
    if (p.family !== family) {const heading=document.createElement('p');heading.className='preset-group';heading.textContent=p.family;$('presets').append(heading);family=p.family;}
    const strip = p.template === 'coupled_stripline', compact = p.id === 'compact' || p.id === 'thin';
    const button=document.createElement('button');button.type='button';button.className='preset';button.dataset.preset=p.id;
    button.setAttribute('aria-label',`Load ${p.name} preset`);
    button.innerHTML=`<svg viewBox="0 0 190 80" aria-hidden="true"><rect x="20" y="${strip?15:39}" width="150" height="${strip?48:24}" fill="#e2ebd8" stroke="#b3c5a6"/><path d="M20 65h150${strip?'M20 14h150':''}" stroke="#687c64" stroke-width="5"/><path d="M${compact?62:52} ${strip?39:36}h${compact?24:32}m${compact?18:22} 0h${compact?24:32}" stroke="#bb722b" stroke-width="${compact?5:7}"/></svg><strong>${p.name}</strong><small>H ${p.height} mm · Dk ${p.eps_r}</small>`;
    button.addEventListener('click',()=>applyPreset(p));$('presets').append(button);
  }
  presetState();
}
function focusDimension(id) {
  if (busy) return;
  focusedDimension=id;
  $(id).focus({preventScroll:true});$(id).select();
  $(id).scrollIntoView({behavior:'auto',block:'nearest'});
}
function dimensionState() {
  for (const element of document.querySelectorAll('[data-dimension]')) {
    element.classList.toggle('active',element.dataset.dimension===focusedDimension);
    element.setAttribute('aria-disabled',String(busy));element.setAttribute('tabindex',busy?'-1':'0');
  }
  for (const id of fields) $(id).closest('label').classList.toggle('field-active',id===focusedDimension);
}
$('runtime-note').textContent = browser ? 'Calculations run in this browser. Design files are not uploaded. The first calculation loads the local engine assets.' : 'Local review build: calculations run on this computer through the SIPI engine. Design files are not uploaded.';
// tone: '' (neutral), 'busy' (task running) or 'success' (task completed); errors use `error`.
function status(message, error = false, area = activeArea, tone = '') {
  const element = $(area === 'design' ? 'design-status' : area === 'file' ? 'file-status' : 'status');
  element.hidden = !message; element.textContent = message; element.classList.toggle('error', error);
  element.classList.toggle('busy', !error && tone === 'busy'); element.classList.toggle('success', !error && tone === 'success');
  element.closest('.panel')?.setAttribute('aria-busy', String(!error && tone === 'busy'));
}
function invalidate() {
  latest = null; $('result').hidden = true; $('failure').hidden = true; $('range-feedback').hidden = true;
  status('Calculate impedance to check the current dimensions.', false, 'analysis');
  status('Set a target and width range, then find width.', false, 'design');
  status('', false, 'file'); comparison();
}
function showRangeFailure(error, request) {
  if (request?.action !== 'design' || !error.message.includes('not bracketed') || !Array.isArray(error.history)) return false;
  const endpoints = error.history.filter(point => point.stage === 'search' && Number.isFinite(point.parameter) && Number.isFinite(point.impedance));
  if (endpoints.length !== 2) return false;
  const [a, b] = [...endpoints].sort((a, b) => a.parameter - b.parameter);
  const low = Math.min(a.impedance, b.impedance), high = Math.max(a.impedance, b.impedance);
  status(`Target ${request.design.target} Ω is outside the boundary results (${low.toFixed(3)}–${high.toFixed(3)} Ω). No width was selected.`, true);
  $('range-rows').replaceChildren();
  for (const point of [a, b]) {
    const row = document.createElement('tr');
    for (const value of [String(Number((point.parameter * 1e3).toPrecision(10))), point.impedance.toFixed(3)]) {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    $('range-rows').append(row);
  }
  let advice = 'Try a different width range or review the target and stackup.';
  if (a.impedance > b.impedance) {
    if (request.design.target > high) advice = 'Try a smaller minimum width, or review the target and stackup.';
    else if (request.design.target < low) advice = 'Try a larger maximum width, or review the target and stackup.';
  }
  $('range-guidance').textContent = `${advice} These are the two boundary samples, not a guarantee that another range can reach the target. Your inputs have not been changed.`;
  $('range-feedback').hidden = false;
  return true;
}
// Disabling the focused control would drop keyboard focus to the page start.
// While a task runs, focus moves to Cancel; afterwards it returns to the control
// that started the task, unless the user has already moved focus elsewhere.
let returnFocus = null;
function lock(value) {
  const active = document.activeElement;
  if (value) returnFocus = active && active !== document.body ? active : null;
  busy = value;
  for (const element of document.querySelectorAll('button,input,select')) element.disabled = value;
  $('cancel').disabled = false; $('cancel').hidden = !value;
  dimensionState(); comparison();
  if (value && returnFocus) $('cancel').focus({preventScroll: true});
  else if (!value) {
    const current = document.activeElement;
    if (returnFocus?.isConnected && !returnFocus.disabled && (!current || current === document.body || current === $('cancel'))) returnFocus.focus({preventScroll: true});
    returnFocus = null;
  }
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
    const name=label.textContent.replace(/^(W|S|H|T|εr)(?=[A-Z])/,'').trim();
    element.setAttribute('aria-label', ['width','gap','height','thickness'].includes(id) ? `${name} · mm` : name);
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
      // Pointer shortcut only: keyboard users nudge with ArrowUp/ArrowDown in the field.
      button.tabIndex = -1;
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
  $('height-label').textContent = strip ? 'Plane spacing' : 'Substrate height';
  $('height').setAttribute('aria-label', `${$('height-label').textContent} · mm`);
  for (const button of document.querySelectorAll('.number-arrows button')) {
    const label = $(button.getAttribute('aria-controls')).getAttribute('aria-label');
    const description = `${button.dataset.direction} ${label} by ${button.dataset.increment}`;
    button.setAttribute('aria-label', description); button.title = description;
  }
  $('section-heading').textContent = strip ? 'Differential stripline' : 'Differential microstrip';
  $('air-field').hidden = strip;
  $('air_height').required = !strip;
}
function draw() {
  const strip = $('template').value === 'coupled_stripline';
  const width=Number($('width').value), gap=Number($('gap').value), height=Number($('height').value), thickness=Number($('thickness').value);
  const svg=$('section');svg.replaceChildren();
  const compact=svg.getBoundingClientRect().width<520;
  svg.setAttribute('viewBox',compact?'0 0 460 420':'0 0 800 420');svg.classList.toggle('compact',compact);
  const center=compact?250:400, boardLeft=compact?74:110, boardRight=compact?420:690;
  const node=(tag,attrs,text,parent=svg)=>{const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;parent.append(n);return n;};
  if (![width,gap,height,thickness].every(Number.isFinite) || width<=0 || gap<=0 || height<=0 || thickness<0) {node('text',{x:80,y:200,fill:'#58687c'},'Enter valid dimensions to draw the cross-section.');return;}
  if (strip && thickness>=height) {node('text',{x:80,y:200,fill:'#893724'},'Copper thickness must be less than plane spacing.');return;}
  // Diagram proportions are deliberately bounded for readable dimension targets.
  // Values below are displayed from the inputs; no solver geometry is changed.
  const span=compact?190:260;
  const traceWidth=Math.max(compact?58:75,Math.min(compact?100:160,span*width/(2*width+gap))), traceGap=Math.max(compact?50:62,Math.min(compact?70:130,span*gap/(2*width+gap)));
  const left=center-traceWidth-traceGap/2, right=center+traceGap/2;
  const top=strip?112:210, bottom=330, copperHeight=Math.max(8,Math.min(28,(strip?218:120)*thickness/height));
  const traceY=strip?(top+bottom-copperHeight)/2:top-copperHeight;
  node('rect',{x:boardLeft,y:top,width:boardRight-boardLeft,height:bottom-top,class:'dielectric'});
  node('rect',{x:boardLeft,y:bottom,width:boardRight-boardLeft,height:7,class:'ground'});
  if(strip)node('rect',{x:boardLeft,y:top-7,width:boardRight-boardLeft,height:7,class:'ground'});
  for(const x of [left,right])node('rect',{x,y:traceY,width:traceWidth,height:copperHeight,class:'copper'});
  node('text',{x:left+traceWidth/2,y:traceY+copperHeight+22,'text-anchor':'middle',class:'trace-label'},'Signal +');
  node('text',{x:right+traceWidth/2,y:traceY+copperHeight+22,'text-anchor':'middle',class:'trace-label'},'Signal −');
  node('text',{x:boardLeft+10,y:bottom+27,class:'layer-label'},'Ground plane');
  if(strip)node('text',{x:boardLeft+10,y:top-19,class:'layer-label'},'Ground plane');
  else node('text',{x:boardLeft+10,y:132,class:'layer-label'},'Air');
  const fmt=id=>Number($(id).value).toLocaleString('en-US',{maximumSignificantDigits:8,useGrouping:false});
  const dimension=(id,text,cx,cy,w=112)=>{
    const labelHeight=compact?48:36;
    const g=node('g',{class:'dimension','data-dimension':id,role:'button',tabindex:'0','aria-label':`Edit ${id==='eps_r'?'relative permittivity':id==='height'?(strip?'plane spacing':'substrate height'):id==='gap'?'trace gap':id==='thickness'?'copper thickness':'trace width'}`});
    g.addEventListener('click',()=>focusDimension(id));g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();focusDimension(id);}});
    node('rect',{x:cx-w/2,y:cy-labelHeight/2,width:w,height:labelHeight,rx:5,class:'dim-label'},undefined,g);
    node('text',{x:cx,y:cy+5},text,g);return g;
  };
  const horizontal=(id,label,x1,x2,y)=>{
    for(const x of [x1,x2])node('line',{x1:x,y1:y-6,x2:x,y2:traceY-5,class:'extension'});
    const g=dimension(id,label,(x1+x2)/2,y-24);
    const line=node('path',{d:`M${x1} ${y}H${x2} M${x1+5} ${y-5}l-5 5 5 5 M${x2-5} ${y-5}l5 5-5 5`,class:'dim-line'},undefined,g);g.prepend(line);
  };
  horizontal('width',`W  ${fmt('width')}`,left,left+traceWidth,strip?62:91);
  horizontal('gap',`S  ${fmt('gap')}`,left+traceWidth,right,strip?165:145);
  for(const y of [top,bottom])node('line',{x1:compact?47:72,y1:y,x2:boardLeft,y2:y,class:'extension'});
  const hx=compact?47:76;
  const hg=dimension('height',`H  ${fmt('height')}`,hx,(top+bottom)/2,compact?90:106);
  const hl=node('path',{d:`M${hx} ${top}V${bottom} M${hx-5} ${top+5}l5-5 5 5 M${hx-5} ${bottom-5}l5 5 5-5`,class:'dim-line'},undefined,hg);hg.prepend(hl);
  const tx=compact?388:673,ty=compact?78:(strip?196:158),elbow=compact?408:610;
  const tg=dimension('thickness',`T  ${fmt('thickness')}`,tx,ty,120);
  const tl=node('path',{d:`M${right+traceWidth} ${traceY+copperHeight/2}H${elbow}V${ty}H${tx}`,class:'dim-line'},undefined,tg);tg.prepend(tl);
  dimension('eps_r',`εr  ${fmt('eps_r')}`,compact?338:544,strip?293:288,96);
  dimensionState();
}
function acceptEditable(value) {
  if (!supported.includes(value.template)) throw new Error('This preview opens only symmetric microstrip or stripline pairs.');
  const p=value.parameters;
  const allowed=['width','gap','thickness','eps_r','box_width', value.template === 'coupled_stripline' ? 'plane_spacing' : 'substrate_height', ...(value.template === 'coupled_microstrip' ? ['air_height'] : [])];
  const defaults={tan_delta:0,top_width:null,...(value.template==='coupled_stripline'?{trace_height:null}:{})};
  if(Object.keys(p).some(k=>!allowed.includes(k) && (!Object.hasOwn(defaults,k) || p[k]!==defaults[k]))) throw new Error('This design has settings outside the preview. Open it in the full workbench.');
  if(allowed.some(k=>!Number.isFinite(p[k]))) throw new Error('This preview requires explicit dimensions and calculation boundaries.');
  activePreset=null; presetState();
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
  activeArea = action === 'design' ? 'design' : action.startsWith('template-') ? 'file' : 'analysis';
  const output = $(activeArea === 'design' ? 'design-output' : 'analysis-output');
  output.append($('cancel'), $('result'), $('failure'));
  if (activeArea === 'file') $('file-status').after($('cancel'));
  let request;
  try {
    request = action==='template-open' ? {action,...extra} : input(action);
    if(action==='design') {
      if(!$('goal').reportValidity()) throw new Error('Check target and width bounds.');
      request.design={target:Number($('target').value),bounds:[Number($('lower').value)*1e-3,Number($('upper').value)*1e-3],tolerance:Number($('tolerance').value)};
      if(request.design.bounds[0]>=request.design.bounds[1]) throw new Error('Minimum width must be below maximum width.');
    }
    lock(true); status(action==='design'?'Searching widths, then checking a separate refined mesh…':'Working…', false, activeArea, 'busy');
    const result=await transport.run(request);
    if(version!==generation) return;
    if(action==='template-open') {acceptEditable(result); $('material-label').value='Imported design — material not identified'; $('material-note').value=''; status('Design opened. Add material context and calculate to produce a fresh result.', false, activeArea, 'success');}
    else if(action==='template-document') {download('sipi-pair-design.json',result.document_text); status('Editable design saved. Target-search settings are not part of this input file.', false, activeArea, 'success');}
    else {
      if(![result.line?.z_diff,result.line?.z_common].every(Number.isFinite)) throw new Error('The engine did not return finite symmetric-mode impedances.');
      if(result.design) {
        parameters={...request.parameters,width:result.design.width}; mesh={...result.document.mesh}; changed.clear();
        $('width').value=String(parameters.width*1e3); activePreset=null; presetState(); draw();
      }
      latest={request,result,material:{label:$('material-label').value,note:$('material-note').value}};
      $('z-diff').textContent=result.line.z_diff.toFixed(3); $('z-common').textContent=result.line.z_common.toFixed(3);
      $('refinement').textContent=result.design ? `Selected width ${(result.design.width*1e3).toPrecision(7)} mm. Initial ${result.design.impedance.toFixed(5)} Ω; refined ${result.design.refined_impedance.toFixed(5)} Ω. Both meet the requested target tolerance.` : 'Single mesh result. Mesh and outer-boundary convergence have not been checked by this calculation.';
      $('details').textContent=JSON.stringify({engine:result.engine,mesh:result.document.mesh,line:result.line,design:result.design},null,2);
      $('width-result').hidden = !result.design;
      if (result.design) $('chosen-width').textContent = String(Number((result.design.width * 1e3).toPrecision(10)));
      $('result').hidden=false;
      status(result.design ? 'Width found. Initial and refined target checks passed.' : 'Impedance calculated for the current dimensions.', false, activeArea, 'success');
      if (result.design) status('Selected width applied. See the result in Find trace width.', false, 'analysis');
    }
  } catch(error) {
    if(version!==generation) return;
    invalidate(); if (!showRangeFailure(error, request)) status(error.message,true);
    if(error.history) {$('failure-data').textContent=JSON.stringify(error.history,null,2);$('failure').hidden=false;}
  } finally {if(version===generation) lock(false);}
}
$('inputs').addEventListener('invalid',event=>{const details=event.target.closest('details');if(details)details.open=true;},true);
$('inputs').addEventListener('submit',event=>{event.preventDefault();run('analyze');});
$('goal').addEventListener('submit',event=>{event.preventDefault();run('design');});
for(const id of [...fields,'target','lower','upper','tolerance','material-label','material-note']) $(id).addEventListener('input',()=>{++generation;changed.add(id);if(fields.includes(id)){activePreset=null;presetState();}invalidate();draw();status('Inputs changed. Calculate to update the result.', false, 'analysis');status('Inputs changed. Find width to update the search result.', false, 'design');});
$('template').addEventListener('change',()=>{++generation;parameters=null;mesh=null;changed.clear();activePreset=null;presetState();invalidate();$('height').value=$('template').value==='coupled_stripline'?'1':'0.2';controls();draw();status('Structure changed. Calculate to update the result.', false, 'analysis');});
$('save').addEventListener('click',()=>run('template-document'));
$('open').addEventListener('click',()=>$('file').click());
$('file').addEventListener('change',async()=>{
  const file=$('file').files[0]; $('file').value=''; if(!file || busy) return;
  const version=++generation; invalidate(); activeArea='file';
  if(file.size>200*1024){status('Design files must be at most 200 KiB.',true);return;}
  status('Reading design…', false, activeArea, 'busy');
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
for(const id of fields) {
  $(id).addEventListener('focus',()=>{focusedDimension=id;dimensionState();});
  $(id).addEventListener('blur',()=>{focusedDimension=null;dimensionState();});
}
let lastDrawingWidth=0;
new ResizeObserver(entries=>{const width=entries[0].contentRect.width;if(width!==lastDrawingWidth){lastDrawingWidth=width;draw();}}).observe($('section').parentElement);
numberControls(); presetControls(); controls(); draw(); comparison();
