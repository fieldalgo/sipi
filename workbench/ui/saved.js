import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';
import {SAVED_EXAMPLES} from './saved-examples.js';
import {renderMaterialResults, clearMaterialResults, materialStudyCSV} from './material-results.js';
import {createMaterialSettingsEditor, applyMaterialSettings as updatedMaterialSettings} from './material-goal-form.js';

const $ = id => document.getElementById(id);
const browser = document.documentElement.dataset.runtime === 'browser';
const transport = browser ? new BrowserTransport() : new LocalTransport();
$('example-choice').replaceChildren(...SAVED_EXAMPLES.map(item => {
  const option = document.createElement('option'); option.value = item.id; option.textContent = item.label; return option;
}));
$('example-help').textContent = SAVED_EXAMPLES[0].description;
let generation = 0, activeRun = null, busy = false, closed = false, checked = null, report = null;
let recorded = null, sampleCSV = null;
let projectText = null, activeDesign = null, projectDirty = false;
const bytes = value => new TextEncoder().encode(value).length;
const materialEditor = createMaterialSettingsEditor($('material-goal-editor'), {onDraft:invalidate, onApply:applyMaterialSettings});

function state(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
function controls() {
  materialEditor.sync($('input-text').value, busy || closed);
  for (const id of ['open', 'example', 'example-choice', 'check', 'run', 'record']) $(id).disabled = busy || closed;
  $('save-input').disabled = busy || closed || checked === null;
  $('save-result').disabled = busy || closed || report === null;
  $('save-study-csv').hidden = sampleCSV === null;
  $('save-study-csv').disabled = busy || closed || sampleCSV === null;
  $('save-record').disabled = busy || closed || recorded === null;
  $('save-environment').disabled = busy || closed || !recorded?.environment;
  for (const id of ['project-open', 'project-save', 'project-duplicate', 'project-label']) $(id).disabled = busy || closed;
  $('project-start').disabled = busy || closed || projectText !== null;
  $('project-design').disabled = busy || closed || projectText === null;
  $('project-record').disabled = busy || closed || projectText === null || !design()?.records.length;
  for (const id of ['project-view', 'project-select', 'project-remove']) $(id).disabled = busy || closed || !$('project-record').value;
  $('project-clear').disabled = busy || closed || projectText === null;
  $('cancel').disabled = closed;
  if (materialEditor.dirty) {
    for (const id of ['check','run','record','save-input','project-start','project-save','project-duplicate',
      'project-design','project-select','project-clear','project-remove']) $(id).disabled = true;
  }
}
function invalidate() {
  ++generation; checked = report = recorded = sampleCSV = null;
  if (projectText) projectDirty = true;
  projectNote();
  $('record-status').hidden = true;
  $('output').hidden = true; clearMaterialResults($('material-results')); $('output').textContent = '';
  $('diagnostic-status').hidden = true;
  state(busy ? 'Inputs changed. Cancel the current calculation to run these settings.' : 'Inputs changed. Check or run the updated analysis.');
  controls();
}
function design(text = projectText, id = activeDesign) {
  return text ? JSON.parse(text).designs.find(item => item.design_id === id) : null;
}
function executionControls() {
  const limits = design()?.controls || {max_input_bytes: 200*1024, max_evaluations: 128};
  return {...limits, diagnostics: ['characteristic', 'modes'].filter(id => $(id).checked)};
}
function projectNote() {
  $('project-note').textContent = !projectText ? 'Start a project to keep input variants and recorded runs in one file. Save it to this device to resume later.' :
    (projectDirty ? 'Unsaved input changes. Existing history is retained; saving or switching checks the current input and clears any incompatible selection. ' : 'Project ready. Save the file to keep changes. ') +
    `Stored evaluation limit: ${design().controls.max_evaluations}. This workspace runs at most 128 evaluations. Environment files are saved separately.`;
}
function showProject(preferredRun = null) {
  if (!projectText) { projectNote(); controls(); return; }
  const project = JSON.parse(projectText), current = design();
  $('project-title').textContent = project.title;
  $('project-design').replaceChildren(...project.designs.map(item => {
    const option = document.createElement('option'); option.value = item.design_id; option.textContent = item.label; return option;
  }));
  $('project-design').value = activeDesign; $('project-label').value = current.label;
  const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = 'Choose a saved run';
  $('project-record').replaceChildren(placeholder, ...current.records.map(item => {
    const option = document.createElement('option'); option.value = item.run_id;
    option.textContent = `${item.run_id} · ${item.receipt.execution.status}${item.run_id === current.selected_run_id ? ' · selected in project' : ''}`;
    return option;
  }));
  if (preferredRun && current.records.some(item => item.run_id === preferredRun)) $('project-record').value = preferredRun;
  projectNote(); controls();
}
function showMaterial(execution, historical = false) {
  renderMaterialResults($('material-results'), execution, {historical});
  const text=materialStudyCSV(execution);
  sampleCSV=text===null?null:{text,filename:historical?'sipi-saved-study-samples.csv':'sipi-study-samples.csv'};
  $('save-study-csv').textContent=historical?'Save saved-run samples CSV ↓':'Save sample table CSV ↓';
}
function clearOutput() {
  checked = report = recorded = sampleCSV = null;
  $('output').hidden = true; clearMaterialResults($('material-results')); $('output').textContent = '';
  $('diagnostic-status').hidden = true; $('record-status').hidden = true;
}
async function projectCall(input, current) {
  if (bytes(JSON.stringify(input)) > 256*1024) throw new Error('Encoded project request exceeds 256 KiB. The project is unchanged.');
  const result = await transport.run(input);
  if (current !== generation || closed) throw new DOMException('Project operation cancelled.', 'AbortError');
  return result;
}
async function snapshot(current, text = $('input-text').value, settings = executionControls()) {
  if (materialEditor.dirty) throw new Error('Apply or reset the material settings before saving the input.');
  const label = $('project-label').value;
  if (!label.trim()) throw new Error('Enter a design name.');
  if (bytes(text) > 200*1024) throw new Error('Input exceeds 200 KiB.');
  const id = activeDesign || crypto.randomUUID();
  const input = projectText ? {action:'project-update', project_text:projectText, design_id:id, text, label, controls:settings} :
    {action:'project-create', text, controls:settings, project_id:crypto.randomUUID(), design_id:id, title:'Analysis designs', label};
  const result = await projectCall(input, current);
  return {text:result.project_text, id};
}
function commitProject(snapshot, restore = false, runId = null) {
  projectText = snapshot.text; activeDesign = snapshot.id; projectDirty = false;
  if (restore) {
    materialEditor.clearDraft();
    const current = design(); $('input-text').value = current.source_text;
    for (const id of ['characteristic', 'modes']) $(id).checked = current.controls.diagnostics.includes(id);
  }
  showProject(runId);
}
function showStored(result) {
  const record = JSON.parse(result.record_text);
  report = checked = null; recorded = {text:result.record_text, environment:null};
  $('output').textContent = JSON.stringify(record.receipt.execution, null, 2); $('output').hidden = false;
  showMaterial(record.receipt.execution, true);
  $('diagnostic-status').hidden = true;
  const kind = projectDirty ? 'Current input has unsaved changes.' : !result.matches_current ? 'Historical input or execution settings.' :
    result.selected ? 'Selected in the saved project for this input.' : 'Matches this input but is not selected.';
  state(`Viewing saved ${record.receipt.execution.status} run. ${kind} No calculation was performed.`);
  $('record-status').textContent = `${record.run_id}. The record can be exported unchanged. Its separate environment file is not contained in this project.`;
  $('record-status').hidden = false;
}
async function projectOperation(operation, target) {
  if (busy || closed) return;
  if (projectText) $('project-design').value = activeDesign;
  const current = ++generation; activeRun = current; busy = true; clearOutput(); controls();
  state('Updating project…');
  try {
    if (operation === 'view') {
      const result = await projectCall({action:'project-record', project_text:projectText, design_id:activeDesign, run_id:target}, current);
      showStored(result); return;
    }
    let next = await snapshot(current), restore = false, viewed = null;
    if (operation === 'duplicate') {
      const id = crypto.randomUUID();
      const result = await projectCall({action:'project-duplicate', project_text:next.text, source_id:next.id,
        design_id:id, label:`Design ${JSON.parse(next.text).designs.length + 1}`}, current);
      next = {text:result.project_text, id}; restore = true;
    } else if (operation === 'switch') {
      if (!design(next.text, target)) throw new Error('Design is unavailable.');
      next.id = target; restore = true;
    } else if (['select','clear','remove'].includes(operation)) {
      const result = await projectCall({action:operation === 'remove' ? 'project-remove-record' : 'project-select',
        project_text:next.text, design_id:next.id, run_id:operation === 'clear' ? null : target}, current);
      next.text = result.project_text;
      if (operation === 'select') viewed = await projectCall({action:'project-record', project_text:next.text, design_id:next.id, run_id:target}, current);
    }
    commitProject(next, restore, operation === 'select' ? target : null);
    if (viewed) showStored(viewed);
    else if (operation === 'save') { download('sipi-analysis-project.json', projectText); state('Project saved. Inputs, controls, records and explicit selection are retained. Save environment files separately.'); }
    else state(operation === 'remove' ? 'Record removed from this project. Save the file to keep this change.' : 'Project ready. Recorded runs will be added to this design; save the project file to keep changes.');
  } catch (error) { if (current === generation && !closed) state(error.message, error.name !== 'AbortError'); }
  finally { if (activeRun === current) { activeRun = null; busy = false; controls(); } }
}
function request(action) {
  if (materialEditor.dirty) throw new Error('Apply or reset the material settings before checking or running.');
  const text = $('input-text').value;
  if (!text.trim()) throw new Error('Open or enter an analysis input first.');
  if (bytes(text) > 200 * 1024) throw new Error('Input exceeds 200 KiB.');
  const input = {action, text};
  if (action === 'saved-analyze') input.diagnostics = ['characteristic', 'modes'].filter(id => $(id).checked);
  if (action === 'saved-record') input.controls = executionControls();
  else if (action === 'saved-analyze' && projectText) {
    input.action = 'saved-receipt'; input.controls = executionControls(); delete input.diagnostics;
  }
  if (bytes(JSON.stringify(input)) > 256 * 1024) throw new Error('Encoded input exceeds the 256 KiB request limit.');
  return input;
}
async function applyMaterialSettings(source, drafts) {
  if (busy || closed || source !== $('input-text').value) return;
  try { updatedMaterialSettings(JSON.parse(source), drafts); }
  catch (error) { state(error.message, true); return; }
  const current = ++generation; activeRun = current; busy = true; controls(); state('Checking material settings…');
  try {
    // Validate the original text first: parsing in JavaScript must not silently
    // accept duplicate keys or repair a malformed saved input during editing.
    const original = await projectCall({action:'saved-normalize',text:source},current);
    const candidate = updatedMaterialSettings(JSON.parse(original.document_text),drafts);
    const result = await projectCall({action:'saved-normalize',text:JSON.stringify(candidate)},current);
    if (source !== $('input-text').value || current !== generation || closed) return;
    $('input-text').value = result.document_text; materialEditor.clearDraft(); invalidate(); checked = result.document_text;
    state('Material settings applied and checked. Run the analysis to calculate the new target.');
  } catch (error) { if(current === generation && !closed) state(error.message,error.name !== 'AbortError'); }
  finally { if(activeRun === current){activeRun=null;busy=false;controls();} }
}
async function run(action) {
  if (busy || closed) return;
  let input;
  try { input = request(action); } catch (error) { state(error.message, true); return; }
  const current = ++generation;
  activeRun = current;
  busy = true; checked = report = recorded = sampleCSV = null;
  $('record-status').hidden = true;
  $('output').hidden = true; clearMaterialResults($('material-results')); $('output').textContent = ''; $('diagnostic-status').hidden = true;
  state(action === 'saved-normalize' ? 'Checking input…' : 'Calculating…'); controls();
  try {
    const pending = action === 'saved-record' && projectText ? await snapshot(current, input.text, input.controls) : null;
    const result = await transport.run(input);
    if (current !== generation || closed) return;
    if (action === 'saved-normalize') {
      checked = result.document_text; $('input-text').value = checked;
      if (projectText && design().source_text !== checked) { projectDirty = true; projectNote(); }
      state('Input checked. Its schema and resolved settings are preserved.');
    } else {
      const record = action === 'saved-record' ? JSON.parse(result.record_text) : null;
      const out = record ? record.receipt.execution : result.receipt ? result.receipt.execution : result.execution;
      report = record || result.receipt ? {engine: result.engine, execution: out} : result;
      checked = record ? record.source_text : JSON.stringify(out.input, null, 2);
      if (record) {
        // Reserializing parsed numbers can change the record's content digest.
        recorded = {text: result.record_text, environment: result.runtime_manifest_text};
        $('record-status').textContent = `Execution record ready (${record.run_id}). Save the record and environment files together to keep this run.`;
        $('record-status').hidden = false;
      }
      $('output').textContent = JSON.stringify(out, null, 2); $('output').hidden = false;
      showMaterial(out);
      if (out.status === 'failed') state('Target not met: ' + out.error.message, true);
      else if (out.status === 'incomplete') state(`${out.result.failed} sample(s) failed. All rows are retained; no summary was calculated.`, true);
      else state('Calculation complete. Review the result and model limits.');
      const failed = Object.entries(out.result?.diagnostics || {}).filter(([, value]) => value.status === 'failed');
      if (failed.length) {
        $('diagnostic-status').textContent = 'Base results retained. ' + failed.map(([name, value]) => `${name}: ${value.error.message}`).join(' ');
        $('diagnostic-status').hidden = false;
      }
      if (pending) {
        try {
          const attached = await projectCall({action:'project-attach', project_text:pending.text, design_id:pending.id, record_text:result.record_text, select:true}, current);
          commitProject({text:attached.project_text, id:pending.id}, false, record.run_id);
        } catch (error) {
          if (current !== generation || closed) return;
          state(`${$('status').textContent} Record was not added to the project: ${error.message} The project is unchanged; save the separate execution record.`, true);
        }
      }
    }
  } catch (error) {
    if (current === generation && !closed) state(error.message, error.name !== 'AbortError');
  } finally { if (activeRun === current) { activeRun = null; busy = false; controls(); } }
}
function download(filename, text, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], {type}));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('input-text').addEventListener('input', () => { materialEditor.clearDraft(); invalidate(); });
for (const id of ['characteristic', 'modes']) $(id).addEventListener('change', invalidate);
$('open').onclick = () => $('file').click();
$('file').onchange = async () => {
  const file = $('file').files[0]; $('file').value = '';
  if (!file || closed) return;
  invalidate(); const current = generation;
  try {
    if (file.size > 200 * 1024) throw new Error('Input exceeds 200 KiB.');
    const text = await file.text();
    if (current !== generation || closed) return;
    materialEditor.clearDraft(); $('input-text').value = text; controls(); state('File opened. Check or run its saved settings.');
  } catch (error) { if (current === generation) state(error.message, true); }
};
$('example-choice').onchange = () => {
  $('example-help').textContent = SAVED_EXAMPLES.find(item => item.id === $('example-choice').value)?.description || '';
};
$('example').onclick = () => {
  if (busy || closed) return;
  const example = SAVED_EXAMPLES.find(item => item.id === $('example-choice').value);
  if (!example) { state('Choose an example before loading it.', true); return; }
  materialEditor.clearDraft(); invalidate(); $('input-text').value = JSON.stringify(example.document, null, 2);
  $('characteristic').checked = $('modes').checked = false;
  controls();
  state(`${example.label} example loaded. Edit its values, check the input or run the analysis.`);
};
$('check').onclick = () => run('saved-normalize');
$('run').onclick = () => run('saved-analyze');
$('record').onclick = () => run('saved-record');
$('save-input').onclick = () => { if (!busy && checked !== null) download('sipi-input.json', checked); };
$('save-result').onclick = () => { if (!busy && report !== null) download('sipi-result.json', JSON.stringify(report, null, 2)); };
$('save-study-csv').onclick = () => { if (!busy && !closed && sampleCSV !== null) download(sampleCSV.filename, sampleCSV.text, 'text/csv;charset=utf-8'); };
$('save-record').onclick = () => { if (!busy && !closed && recorded !== null) download('sipi-execution-record.json', recorded.text); };
$('save-environment').onclick = () => { if (!busy && !closed && recorded?.environment) download('sipi-runtime-manifest.json', recorded.environment); };
$('project-start').onclick = () => projectOperation('start');
$('project-save').onclick = () => projectOperation('save');
$('project-duplicate').onclick = () => projectOperation('duplicate');
$('project-design').onchange = () => projectOperation('switch', $('project-design').value);
$('project-label').oninput = () => { if (projectText) { projectDirty = true; projectNote(); } };
$('project-record').onchange = controls;
for (const name of ['view','select','remove']) $(`project-${name}`).onclick = () => projectOperation(name, $('project-record').value);
$('project-clear').onclick = () => projectOperation('clear');
$('project-open').onclick = () => $('project-file').click();
$('project-file').onchange = async () => {
  const file = $('project-file').files[0]; $('project-file').value = '';
  if (!file || busy || closed) return;
  const current = ++generation; activeRun = current; busy = true; clearOutput(); controls(); state('Opening project…');
  try {
    if (file.size > 200*1024) throw new Error('Project exceeds 200 KiB. The current project is unchanged.');
    const text = await file.text();
    if (current !== generation || closed) return;
    const result = await projectCall({action:'project-open', project_text:text}, current);
    const id = JSON.parse(result.project_text).designs[0].design_id;
    commitProject({text:result.project_text, id}, true);
    state('Project opened. Choose a saved run to inspect it, or calculate the current input.');
  } catch (error) { if (current === generation && !closed) state(error.message, error.name !== 'AbortError'); }
  finally { if (activeRun === current) { activeRun = null; busy = false; controls(); } }
};
$('cancel').onclick = async () => {
  const current = ++generation; activeRun = current; busy = true;
  checked = report = recorded = sampleCSV = null; $('output').hidden = true; clearMaterialResults($('material-results')); $('diagnostic-status').hidden = true;
  $('record-status').hidden = true; controls();
  try { await transport.cancel(); if (current === generation) state('Calculation cancelled. You can run another input.'); }
  catch (error) { if (current === generation) state(error.message, true); }
  finally { if (activeRun === current) { activeRun = null; busy = false; controls(); } }
};
$('exit').textContent = browser ? 'Close workspace' : 'Exit';
$('exit').onclick = async () => {
  recorded = null; $('record-status').hidden = true;
  closed = true; ++generation; activeRun = null; busy = false; controls();
  try { await transport.close(); state(browser ? 'Workspace closed. You can close this tab.' : 'Application stopped. You can close this tab.'); }
  catch (error) { state(error.message, true); closed = false; controls(); }
};
controls();
