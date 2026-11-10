// Read-only presentation of supported saved executions; never recompute a result.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const positive = value => finite(value) && value > 0;
const quantity = {z0:'Single-ended', z_diff:'Differential', z_common:'Common', z_diff_forward:'Differential launch'};
const numbers = (values, count, predicate = finite) => Array.isArray(values) && values.length === count && values.every(predicate);
const table = (caption, columns, rows) => ({caption, columns, rows});

function sampleValue(row, name, bindings) {
  if (!Object.hasOwn(bindings, name)) return row.parameters?.[name];
  const binding = bindings[name];
  if (!binding || typeof binding.region !== 'string' || !Array.isArray(binding.path)) return undefined;
  let value = row.material_evaluation?.materials?.[binding.region]?.parameters;
  for (const key of binding.path) {
    if (value === null || typeof value !== 'object' || !Object.hasOwn(value, key)) return undefined;
    value = value[key];
  }
  return value;
}

function studyView(input, result, status) {
  if (result.unit !== 'ohm' || result.quantity !== input.quantity || !Object.hasOwn(quantity, result.quantity) ||
      !Array.isArray(result.rows) || result.rows.length < 2 || result.rows.length > 10000 ||
      !Array.isArray(input.sampling?.variables) || !input.sampling.variables.length || input.sampling.variables.length > 8) return null;
  const names = input.sampling.variables.map(item => item.name);
  if (!names.every(name => typeof name === 'string' && name.length > 0) || new Set(names).size !== names.length) return null;
  const rows = []; let failed = 0;
  for (const [index, row] of result.rows.entries()) {
    if (row.index !== index) return null;
    const values = names.map(name => sampleValue(row, name, input.material_variables || {}));
    if (!values.every(finite)) return null;
    let outcome;
    if (row.error === null && row.error_type === null && positive(row.value)) outcome = 'Calculated';
    else if (row.value === null && typeof row.error === 'string' && row.error && typeof row.error_type === 'string' && row.error_type) {
      ++failed; outcome = row.error_type + ': ' + row.error;
    } else return null;
    rows.push([index, ...values, row.value, outcome]);
  }
  if (result.failed !== failed || status !== (failed ? 'incomplete' : 'complete')) return null;
  const tables = [table(quantity[result.quantity] + ' impedance samples',
    ['Row index', ...names, 'Impedance (Ω)', 'Outcome'], rows)];
  if (failed) {
    if (result.summary !== null) return null;
  } else {
    const summary = result.summary;
    const fields = [['minimum','Minimum'],['maximum','Maximum'],['mean','Mean'],
      ['sample_std','Sample standard deviation'],['p05','5th percentile'],['p95','95th percentile']];
    if (!summary || !fields.every(([key]) => finite(summary[key]))) return null;
    tables.push(table('Reported sample statistics', ['Statistic', 'Impedance (Ω)'], fields.map(([key,label]) => [label, summary[key]])));
  }
  return {title:'Quasistatic impedance study',
    note:failed ? `${failed} of ${rows.length} samples failed. All rows are retained; no aggregate summary is available.` :
      `${rows.length} samples calculated. Sample statistics do not establish manufacturing limits.`, tables};
}

function scalarView(input, result, status) {
  if (status !== 'complete' || result.unit !== 'ohm' || result.quantity !== input.quantity ||
      result.target !== input.target_ohm || !Object.hasOwn(quantity, result.quantity) ||
      typeof input.variable !== 'string' || !finite(result.parameter) ||
      ![result.target,result.value,result.refined_value,input.tolerance_ohm].every(positive) ||
      ![result.residual,result.refined_residual].every(finite)) return null;
  return {title:'Quasistatic impedance target', note:'Requested and refined mesh results are shown separately.', tables:[
    table('Selected input', ['Variable', 'Value in input units'], [[input.variable,result.parameter]]),
    table(quantity[result.quantity] + ' target checks', ['Mesh', 'Target (Ω)', 'Value (Ω)', 'Residual (Ω)', 'Tolerance (Ω)'], [
      ['Requested',result.target,result.value,result.residual,input.tolerance_ohm],
      ['Refined',result.target,result.refined_value,result.refined_residual,input.tolerance_ohm]])]};
}

function pairView(input, result, status) {
  if (status !== 'complete' || !Array.isArray(input.variables) || input.variables.length !== 2 ||
      !input.variables.every(item => typeof item.name === 'string' && item.name.length > 0) ||
      new Set(input.variables.map(item => item.name)).size !== 2 ||
      !Array.isArray(result.quantities) || result.quantities.length !== 2 ||
      result.quantities[0] !== 'z_diff' || result.quantities[1] !== 'z_common' ||
      !numbers(result.parameters,2) || !numbers(result.targets_ohm,2,positive) ||
      !numbers(result.tolerances_ohm,2,positive) || !numbers(result.impedances_ohm,2,positive) ||
      !numbers(result.refined_impedances_ohm,2,positive) || !numbers(result.residuals_ohm,2) ||
      !numbers(result.refined_residuals_ohm,2)) return null;
  return {title:'Paired quasistatic impedance targets', note:'Each target retains its requested and refined mesh result.', tables:[
    table('Selected inputs', ['Variable', 'Value in input units'], input.variables.map((item,i) => [item.name,result.parameters[i]])),
    ...result.quantities.map((name,i) => table(quantity[name] + ' target checks',
      ['Mesh', 'Target (Ω)', 'Value (Ω)', 'Residual (Ω)', 'Tolerance (Ω)'], [
        ['Requested',result.targets_ohm[i],result.impedances_ohm[i],result.residuals_ohm[i],result.tolerances_ohm[i]],
        ['Refined',result.targets_ohm[i],result.refined_impedances_ohm[i],result.refined_residuals_ohm[i],result.tolerances_ohm[i]]]))]};
}

function failedScalarView(input, error) {
  if (!['GoalSeekError','GoalMeshSizeLimitError'].includes(error?.type) || error.unit !== 'ohm' ||
      typeof error.message !== 'string' || !error.message || !Object.hasOwn(quantity,input.quantity) ||
      typeof input.variable !== 'string' || !input.variable || !positive(input.target_ohm) ||
      !positive(input.tolerance_ohm) || !numbers(input.bounds,2,positive) || input.bounds[0] >= input.bounds[1] ||
      !Number.isInteger(input.max_evaluations) || input.max_evaluations < 3 || input.max_evaluations > 10000 ||
      !Array.isArray(error.history) || error.history.length > input.max_evaluations ||
      !(error.parameter === null || positive(error.parameter))) return null;
  const stages = ['search','refinement'];
  if (!error.history.every((row,index) => positive(row.parameter) && positive(row.value) && stages.includes(row.stage) &&
      (row.stage !== 'refinement' || index === error.history.length-1))) return null;
  const tables = [
    table('Requested target — not accepted', ['Quantity','Target (Ω)','Tolerance (Ω)'],
      [[quantity[input.quantity],input.target_ohm,input.tolerance_ohm]]),
    table('Search interval', ['Variable','Lower bound in input units','Upper bound in input units'],
      [[input.variable,...input.bounds]])];
  if (error.history.length) tables.push(table('Completed evaluations only',
    ['Row index','Stage','Parameter in input units','Impedance (Ω)'],
    error.history.map((row,index) => [index,row.stage,row.parameter,row.value])));
  if (error.type === 'GoalMeshSizeLimitError') {
    if (!positive(error.parameter) || !stages.includes(error.stage) || error.history.some(row => row.stage === 'refinement') ||
        !Number.isInteger(error.attempts) || error.attempts !== error.history.length+1 ||
        error.attempts > input.max_evaluations || typeof error.cause_type !== 'string' || !error.cause_type ||
        error.input?.schema !== 'sipi.cross-section/1') return null;
    tables.push(table('Stopped evaluation — no impedance calculated',
      ['Attempt','Stage','Parameter in input units','Impedance (Ω)','Cause'],
      [[error.attempts,error.stage,error.parameter,null,error.cause_type]]));
  }
  return {title:'Impedance target not accepted', failed:true,
    note:`${error.message}. ${error.history.length} completed evaluations. History does not select a solution or certify convergence.`, tables};
}

export function materialResultView(execution) {
  try {
    if (execution?.schema !== 'sipi.execution/1') return null;
    const {input,result,status,error} = execution;
    if (status === 'failed' && result === null && ['sipi.impedance-design/1','sipi.impedance-design/2','sipi.impedance-design/3'].includes(input.schema))
      return failedScalarView(input,error);
    if (!result || error !== null) return null;
    if (input.schema === 'sipi.impedance-study/4') return studyView(input,result,status);
    if (input.schema === 'sipi.impedance-design/3') return scalarView(input,result,status);
    if (input.schema === 'sipi.pair-impedance-design/2') return pairView(input,result,status);
  } catch { /* Unsupported display shapes retain the original JSON view. */ }
  return null;
}

export function clearMaterialResults(container) {
  container.replaceChildren(); container.hidden = true;
}

export function renderMaterialResults(container, execution, {historical = false} = {}) {
  clearMaterialResults(container);
  const view = materialResultView(execution);
  if (!view) return;
  const document = container.ownerDocument;
  const element = (tag, text) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; return node; };
  const fragment = document.createDocumentFragment();
  const heading = element('h3',(historical ? 'Saved run · ' : '') + view.title);
  const description = element('p',view.note);
  if (view.failed) { heading.className = 'error'; description.className = 'error'; }
  fragment.append(heading,description);
  for (const item of view.tables) {
    const wrap = element('div'); wrap.className = 'material-table'; wrap.tabIndex = 0;
    wrap.setAttribute('role','region'); wrap.setAttribute('aria-label',item.caption);
    const node = element('table'); node.append(element('caption',item.caption));
    const header = element('tr');
    for (const label of item.columns) { const cell = element('th',label); cell.scope = 'col'; header.append(cell); }
    const head = element('thead'); head.append(header); node.append(head);
    const body = element('tbody');
    for (const values of item.rows) {
      const row = element('tr');
      for (const value of values) {
        const text = value === null ? '—' : typeof value === 'number' ? String(Number(value.toPrecision(7))) : value;
        const cell = element('td',text); if (typeof value === 'number') cell.dataset.value = String(value); row.append(cell);
      }
      body.append(row);
    }
    node.append(body); wrap.append(node); fragment.append(wrap);
  }
  const note = element('p','Values use the input document’s units and are rounded to 7 significant digits for display. The full JSON below and saved files retain all reported digits.');
  note.className = 'fine'; fragment.append(note); container.append(fragment); container.hidden = false;
}
