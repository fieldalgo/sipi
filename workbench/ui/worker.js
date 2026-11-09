// Pyodide remains an unmodified, separate runtime asset.
let runtime;
let running = false;

async function checkedBytes(path, manifest) {
  const response = await fetch(new URL(path, self.location.href));
  if (!response.ok) throw new Error('Could not load calculation asset: ' + path);
  const bytes = await response.arrayBuffer();
  const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(v => v.toString(16).padStart(2, '0')).join('');
  if (hash !== manifest.files[path]?.sha256) throw new Error('Calculation asset integrity mismatch: ' + path);
  return bytes;
}

async function initialize() {
  const started = performance.now();
  const response = await fetch(new URL('./runtime-manifest.json', self.location.href));
  if (!response.ok) throw new Error('The browser calculation assets are not staged.');
  const manifestText = await response.text();
  if (new TextEncoder().encode(manifestText).length > 1024*1024) throw new Error('Browser manifest exceeds 1 MiB.');
  const manifest = JSON.parse(manifestText);
  const entries = Object.entries(manifest.files || {});
  if (!entries.length || entries.length > 128) throw new Error('Browser manifest needs 1 to 128 source files.');
  let total = 0;
  const checked = new Map();
  for (const [path, row] of entries) {
    if (!/^(?:(?:runtime|wheels)\/[A-Za-z0-9_+.-]+|[a-z_]+\.py|notices\.txt)$/.test(path)
        || path.split('/').some(part => part === '.' || part === '..')
        || !Number.isSafeInteger(row?.bytes) || row.bytes < 0 || row.bytes > 64*1024*1024
        || !/^[0-9a-f]{64}$/.test(row?.sha256)) throw new Error('Invalid browser source-file descriptor.');
    total += row.bytes;
    if (total > 128*1024*1024) throw new Error('Browser source files exceed 128 MiB.');
    const bytes = await checkedBytes(path, manifest);
    if (bytes.byteLength !== row.bytes) throw new Error('Calculation asset size mismatch: ' + path);
    if (path.startsWith('wheels/') || path.endsWith('.py')) checked.set(path, bytes);
  }
  importScripts(new URL('./runtime/pyodide.js', self.location.href).href);
  const pyodide = await loadPyodide({indexURL: new URL('./runtime/', self.location.href).href});
  if (pyodide.version !== manifest.pyodide) throw new Error('Browser runtime version does not match its manifest.');
  await pyodide.loadPackage(['numpy', 'scipy', 'shapely']);
  const target = '/home/pyodide/sipi-env';
  pyodide.FS.mkdirTree(target);
  for (const wheel of manifest.wheels) {
    if (!checked.has(wheel)) throw new Error('Source wheel was not checked: ' + wheel);
    pyodide.unpackArchive(checked.get(wheel), 'zip', {extractDir: target});
  }
  for (const name of ['engine.py', 'artifacts.py', 'recording.py', 'browser_recording.py']) {
    if (!checked.has(name)) throw new Error('Calculation helper was not checked: ' + name);
    pyodide.FS.writeFile(target + '/' + name, new Uint8Array(checked.get(name)));
  }
  pyodide.globals.set('_sipi_source_manifest', manifestText);
  pyodide.runPython(`import sys, json, time\nsys.path.insert(0, ${JSON.stringify(target)})\nfrom engine import execute\nfrom browser_recording import BrowserSourceRecorder\n_sipi_browser_record = BrowserSourceRecorder(_sipi_source_manifest)\nimport sipi, numpy, scipy`);
  return {pyodide, manifest, initialization_ms: performance.now() - started};
}

self.onmessage = async event => {
  const {id, input} = event.data;
  if (running) { self.postMessage({id, status: 'error', message: 'A calculation is already running.'}); return; }
  running = true;
  try {
    runtime ??= initialize();
    const {pyodide, manifest, initialization_ms} = await runtime;
    const started = performance.now();
    pyodide.globals.set('_sipi_request_json', JSON.stringify(input));
    const text = await pyodide.runPythonAsync(`
try:
    _sipi_result = {'status': 'complete', 'result': execute(json.loads(_sipi_request_json), record_provider=_sipi_browser_record)}
except Exception as exc:
    _sipi_result = {'status': 'error', 'message': str(exc), 'type': type(exc).__name__}
    if isinstance(exc, sipi.GoalSeekError):
        _sipi_result['history'] = [vars(row) for row in exc.history]
json.dumps(_sipi_result, allow_nan=False)
`);
    const result = JSON.parse(text);
    if (result.status === 'complete') result.result.runtime = {pyodide: manifest.pyodide,
      initialization_ms, calculation_ms: performance.now() - started,
      wasm_heap_bytes: pyodide._module?.HEAPU8?.buffer.byteLength ?? null,
      engine_commit: manifest.engine_commit};
    self.postMessage({id, ...result});
  } catch (error) {
    runtime = null;
    self.postMessage({id, status: 'error', message: error.message, fatal: true});
  } finally { running = false; }
};
