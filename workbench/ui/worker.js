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
  const manifest = await response.json();
  importScripts(new URL('./runtime/pyodide.js', self.location.href).href);
  const pyodide = await loadPyodide({indexURL: new URL('./runtime/', self.location.href).href});
  if (pyodide.version !== manifest.pyodide) throw new Error('Browser runtime version does not match its manifest.');
  await pyodide.loadPackage(['numpy', 'scipy', 'shapely']);
  const target = '/home/pyodide/sipi-env';
  pyodide.FS.mkdirTree(target);
  for (const wheel of manifest.wheels) pyodide.unpackArchive(await checkedBytes(wheel, manifest), 'zip', {extractDir: target});
  pyodide.FS.writeFile(target + '/engine.py', new Uint8Array(await checkedBytes('engine.py', manifest)));
  pyodide.runPython(`import sys, json, time\nsys.path.insert(0, ${JSON.stringify(target)})\nfrom engine import execute\nimport sipi, numpy, scipy`);
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
    _sipi_result = {'status': 'complete', 'result': execute(json.loads(_sipi_request_json))}
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
