import {LocalTransport} from './transport.js';
import {BrowserTransport} from './browser-transport.js';

const $ = id => document.getElementById(id);
const browser = document.documentElement.dataset.runtime === 'browser';
const transport = browser ? new BrowserTransport() : new LocalTransport();
const example = {
  schema: 'sipi.lumped-network/1', frequency_hz: [0, 1e9],
  branch: {resistance_ohms: 10, inductance_h: 2e-9, capacitance_f: null},
  placement: 'series', reference_ohms: [50, 50], port_names: ['near', 'far'],
};
let generation = 0, activeRun = null, busy = false, closed = false, checked = null, report = null;
let recorded = null;
const bytes = value => new TextEncoder().encode(value).length;

function state(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}
function controls() {
  for (const id of ['open', 'example', 'check', 'run', 'record']) $(id).disabled = busy || closed;
  $('save-input').disabled = busy || closed || checked === null;
  $('save-result').disabled = busy || closed || report === null;
  for (const id of ['save-record', 'save-environment']) $(id).disabled = busy || closed || recorded === null;
  $('cancel').disabled = closed;
}
function invalidate() {
  ++generation; checked = report = recorded = null;
  $('record-status').hidden = true;
  $('output').hidden = true; $('output').textContent = '';
  $('diagnostic-status').hidden = true;
  state(busy ? 'Inputs changed. Cancel the current calculation to run these settings.' : 'Inputs changed. Check or run the updated analysis.');
  controls();
}
function request(action) {
  const text = $('input-text').value;
  if (!text.trim()) throw new Error('Open or enter an analysis input first.');
  if (bytes(text) > 200 * 1024) throw new Error('Input exceeds 200 KiB.');
  const input = {action, text};
  if (action === 'saved-analyze') input.diagnostics = ['characteristic', 'modes'].filter(id => $(id).checked);
  if (action === 'saved-record') input.controls = {max_input_bytes: 200*1024, max_evaluations: 128,
    diagnostics: ['characteristic', 'modes'].filter(id => $(id).checked)};
  if (bytes(JSON.stringify(input)) > 256 * 1024) throw new Error('Encoded input exceeds the 256 KiB request limit.');
  return input;
}
async function run(action) {
  if (busy || closed) return;
  let input;
  try { input = request(action); } catch (error) { state(error.message, true); return; }
  const current = ++generation;
  activeRun = current;
  busy = true; checked = report = recorded = null;
  $('record-status').hidden = true;
  $('output').hidden = true; $('output').textContent = ''; $('diagnostic-status').hidden = true;
  state(action === 'saved-normalize' ? 'Checking input…' : 'Calculating…'); controls();
  try {
    const result = await transport.run(input);
    if (current !== generation || closed) return;
    if (action === 'saved-normalize') {
      checked = result.document_text; $('input-text').value = checked;
      state('Input checked. Its schema and resolved settings are preserved.');
    } else {
      const record = action === 'saved-record' ? JSON.parse(result.record_text) : null;
      const out = record ? record.receipt.execution : result.execution;
      report = record ? {engine: result.engine, execution: out} : result;
      checked = record ? record.source_text : JSON.stringify(out.input, null, 2);
      if (record) {
        // Reserializing parsed numbers can change the record's content digest.
        recorded = {text: result.record_text, environment: result.runtime_manifest_text};
        $('record-status').textContent = `Execution record ready (${record.run_id}). Save the record and environment files together to keep this run.`;
        $('record-status').hidden = false;
      }
      $('output').textContent = JSON.stringify(out, null, 2); $('output').hidden = false;
      if (out.status === 'failed') state('Target not met: ' + out.error.message, true);
      else if (out.status === 'incomplete') state(`${out.result.failed} sample(s) failed. All rows are retained; no summary was calculated.`, true);
      else state('Calculation complete. Review the result and model limits.');
      const failed = Object.entries(out.result?.diagnostics || {}).filter(([, value]) => value.status === 'failed');
      if (failed.length) {
        $('diagnostic-status').textContent = 'Base results retained. ' + failed.map(([name, value]) => `${name}: ${value.error.message}`).join(' ');
        $('diagnostic-status').hidden = false;
      }
    }
  } catch (error) {
    if (current === generation && !closed) state(error.message, error.name !== 'AbortError');
  } finally { if (activeRun === current) { activeRun = null; busy = false; controls(); } }
}
function download(filename, text) {
  const url = URL.createObjectURL(new Blob([text], {type: 'application/json'}));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('input-text').addEventListener('input', invalidate);
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
    $('input-text').value = text; state('File opened. Check or run its saved settings.');
  } catch (error) { if (current === generation) state(error.message, true); }
};
$('example').onclick = () => {
  invalidate(); $('input-text').value = JSON.stringify(example, null, 2);
  $('characteristic').checked = $('modes').checked = false;
  state('RLC example loaded. Check the input or run the analysis.');
};
$('check').onclick = () => run('saved-normalize');
$('run').onclick = () => run('saved-analyze');
$('record').onclick = () => run('saved-record');
$('save-input').onclick = () => { if (!busy && checked !== null) download('sipi-input.json', checked); };
$('save-result').onclick = () => { if (!busy && report !== null) download('sipi-result.json', JSON.stringify(report, null, 2)); };
$('save-record').onclick = () => { if (!busy && !closed && recorded !== null) download('sipi-execution-record.json', recorded.text); };
$('save-environment').onclick = () => { if (!busy && !closed && recorded !== null) download('sipi-runtime-manifest.json', recorded.environment); };
$('cancel').onclick = async () => {
  const current = ++generation; activeRun = current; busy = true;
  checked = report = recorded = null; $('output').hidden = true; $('diagnostic-status').hidden = true;
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
