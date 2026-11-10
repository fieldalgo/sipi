// This editor changes saved settings only. The engine validates both documents.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const names = {z0:'Single-ended', z_diff:'Differential', z_common:'Common-mode'};
const fields = [
  ['target', 'Target impedance (Ω)'], ['tolerance', 'Allowed error (Ω)'],
  ['lower', 'Lower search bound (dimensionless)'], ['upper', 'Upper search bound (dimensionless)'],
  ['frequency', 'Evaluation frequency (Hz)'], ['budget', 'Maximum evaluations (3–128)'],
];
const sweepFields = [fields[2],fields[3],fields[4],['count','Sample count (2–128)']];
const pairFields = [
  ['targetDiff','Differential target (Ω)'], ['toleranceDiff','Differential allowed error (Ω)'],
  ['targetCommon','Common-mode target (Ω)'], ['toleranceCommon','Common-mode allowed error (Ω)'],
  ['lowerFirst','Variable 1 lower bound (dimensionless)'], ['upperFirst','Variable 1 upper bound (dimensionless)'],
  ['initialFirst','Variable 1 initial value (dimensionless)'],
  ['lowerSecond','Variable 2 lower bound (dimensionless)'], ['upperSecond','Variable 2 upper bound (dimensionless)'],
  ['initialSecond','Variable 2 initial value (dimensionless)'], fields[4], ['pairBudget','Maximum evaluations (2–128)'],
];

function bindingDescription(doc, alias) {
  if (typeof alias !== 'string' || !doc.material_variables || Object.keys(doc.material_variables).length !== 1 ||
      !Object.hasOwn(doc.material_variables,alias)) return null;
  const binding = doc.material_variables[alias], evaluation = doc.material_evaluation;
  if (typeof binding?.region !== 'string') return null;
  const model = evaluation?.materials?.[binding?.region], path = binding?.path;
  if (model?.schema !== 'sipi.dielectric/1' || !Array.isArray(path)) return null;
  let variable;
  if (model.kind === 'constant' && path.length === 1 && path[0] === 'eps_r') variable = 'Relative permittivity';
  else if (model.kind === 'debye' && path.length === 2 && path[0] === 'strengths' &&
      Number.isInteger(path[1]) && path[1] >= 0 && Array.isArray(model.parameters?.strengths) &&
      path[1] < model.parameters.strengths.length) variable = `Debye strength ${path[1]+1}`;
  else return null;
  const leaf = model.kind === 'constant' ? model.parameters?.eps_r : model.parameters.strengths[path[1]];
  return finite(leaf) ? `${variable} · region ${binding.region}` : null;
}

export function materialGoalSettings(doc) {
  if (doc?.schema !== 'sipi.impedance-design/3' || !Object.hasOwn(names,doc.quantity)) return null;
  const description = bindingDescription(doc,doc.variable);
  if (!description || !Array.isArray(doc.bounds) || doc.bounds.length !== 2) return null;
  const values = {target:doc.target_ohm, tolerance:doc.tolerance_ohm, lower:doc.bounds[0],
    upper:doc.bounds[1], frequency:doc.material_evaluation.frequency_hz, budget:doc.max_evaluations};
  if (!Object.values(values).every(finite)) return null;
  return {kind:'goal', values, description:`${names[doc.quantity]} target · ${description}`};
}

export function materialSweepSettings(doc) {
  if (doc?.schema !== 'sipi.impedance-study/4' || !Object.hasOwn(names,doc.quantity) ||
      doc.sampling?.kind !== 'sweep' || !Array.isArray(doc.sampling.variables) || doc.sampling.variables.length !== 1) return null;
  const variable = doc.sampling.variables[0], description = bindingDescription(doc,variable?.name);
  if (!description) return null;
  const values = {lower:variable.lower, upper:variable.upper, frequency:doc.material_evaluation.frequency_hz, count:doc.sampling.count};
  if (!Object.values(values).every(finite)) return null;
  return {kind:'sweep', values, description:`${names[doc.quantity]} sweep · ${description}`};
}

export function materialPairSettings(doc) {
  if (doc?.schema !== 'sipi.pair-impedance-design/2' || !Array.isArray(doc.variables) || doc.variables.length !== 2 ||
      !Array.isArray(doc.initial) || doc.initial.length !== 2 || !doc.material_variables ||
      Object.keys(doc.material_variables).length !== 2) return null;
  const descriptions=[], regions=[], axes=[], aliases=[];
  for (const variable of doc.variables) {
    if (typeof variable?.name !== 'string' || !Object.hasOwn(doc.material_variables,variable.name) ||
        !Array.isArray(variable.bounds) || variable.bounds.length !== 2) return null;
    const binding=doc.material_variables[variable.name], path=binding?.path;
    if (typeof binding?.region !== 'string' || !Array.isArray(path) || path.length !== 3 ||
        !['axis1','axis2'].includes(path[0]) || path[1] !== 'parameters' || path[2] !== 'eps_r') return null;
    const model=doc.material_evaluation?.materials?.[binding.region], axis=model?.parameters?.[path[0]];
    if (model?.schema !== 'sipi.dielectric/2' || model.kind !== 'principal-axes' ||
        axis?.schema !== 'sipi.dielectric/1' || axis.kind !== 'constant' || !finite(axis.parameters?.eps_r)) return null;
    aliases.push(variable.name);regions.push(binding.region);axes.push(path[0]);
    descriptions.push(`${variable.name}: ${path[0]} relative permittivity`);
  }
  if (aliases[0]===aliases[1] || axes[0]===axes[1] || regions[0]!==regions[1]) return null;
  for (const mapping of [doc.targets_ohm,doc.tolerances_ohm])
    if (!mapping || Object.keys(mapping).length!==2 || !Object.hasOwn(mapping,'z_diff') || !Object.hasOwn(mapping,'z_common')) return null;
  const values={targetDiff:doc.targets_ohm.z_diff,toleranceDiff:doc.tolerances_ohm.z_diff,
    targetCommon:doc.targets_ohm.z_common,toleranceCommon:doc.tolerances_ohm.z_common,
    lowerFirst:doc.variables[0].bounds[0],upperFirst:doc.variables[0].bounds[1],initialFirst:doc.initial[0],
    lowerSecond:doc.variables[1].bounds[0],upperSecond:doc.variables[1].bounds[1],initialSecond:doc.initial[1],
    frequency:doc.material_evaluation.frequency_hz,pairBudget:doc.max_evaluations};
  if (!Object.values(values).every(finite)) return null;
  return {kind:'pair',values,description:`Two targets · variable 1 ${descriptions[0]} · variable 2 ${descriptions[1]} · region ${regions[0]}`};
}

function numericDrafts(drafts, selectedFields) {
  const values = {};
  for (const [name,label] of selectedFields) {
    const raw = drafts[name];
    if (typeof raw !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw.trim()) ||
        !Number.isFinite(Number(raw))) throw new Error(`${label}: enter a finite number.`);
    values[name] = Number(raw);
  }
  return values;
}

export function applyMaterialGoalSettings(doc, drafts) {
  if (!materialGoalSettings(doc)) throw new Error('This input has no supported material target form.');
  const values = numericDrafts(drafts,fields);
  if (values.target <= 0 || values.tolerance <= 0) throw new Error('Target and allowed error must be positive.');
  if (values.lower <= 0 || values.lower >= values.upper) throw new Error('Search bounds must be positive, with lower below upper.');
  if (values.frequency < 0) throw new Error('Evaluation frequency must be zero or positive.');
  if (!Number.isInteger(values.budget) || values.budget < 3 || values.budget > 128) throw new Error('Maximum evaluations must be an integer from 3 to 128.');
  const result = structuredClone(doc);
  result.target_ohm = values.target; result.tolerance_ohm = values.tolerance;
  result.bounds = [values.lower,values.upper]; result.max_evaluations = values.budget;
  result.material_evaluation.frequency_hz = values.frequency;
  return result;
}

export function applyMaterialSweepSettings(doc, drafts) {
  if (!materialSweepSettings(doc)) throw new Error('This input has no supported material sweep form.');
  const values = numericDrafts(drafts,sweepFields);
  if (values.lower >= values.upper) throw new Error('Lower sample bound must be below upper.');
  if (values.frequency < 0) throw new Error('Evaluation frequency must be zero or positive.');
  if (!Number.isInteger(values.count) || values.count < 2 || values.count > 128) throw new Error('Sample count must be an integer from 2 to 128.');
  const result = structuredClone(doc);
  result.sampling.variables[0].lower = values.lower; result.sampling.variables[0].upper = values.upper;
  result.sampling.count = values.count; result.material_evaluation.frequency_hz = values.frequency;
  return result;
}

export function applyMaterialPairSettings(doc,drafts) {
  if (!materialPairSettings(doc)) throw new Error('This input has no supported paired material target form.');
  const values=numericDrafts(drafts,pairFields);
  if (['targetDiff','targetCommon','toleranceDiff','toleranceCommon'].some(key=>values[key]<=0))
    throw new Error('Both targets and allowed errors must be positive.');
  for (const suffix of ['First','Second']) {
    const lower=values['lower'+suffix], upper=values['upper'+suffix], initial=values['initial'+suffix];
    if (lower<=0 || lower>=upper) throw new Error('Both search bounds must be positive, with lower below upper.');
    if (initial<lower || initial>upper) throw new Error('Each initial value must be inside its search bounds.');
  }
  if (values.frequency<0) throw new Error('Evaluation frequency must be zero or positive.');
  if (!Number.isInteger(values.pairBudget) || values.pairBudget<2 || values.pairBudget>128)
    throw new Error('Maximum evaluations must be an integer from 2 to 128.');
  const result=structuredClone(doc);
  result.targets_ohm.z_diff=values.targetDiff;result.targets_ohm.z_common=values.targetCommon;
  result.tolerances_ohm.z_diff=values.toleranceDiff;result.tolerances_ohm.z_common=values.toleranceCommon;
  result.variables[0].bounds=[values.lowerFirst,values.upperFirst];result.variables[1].bounds=[values.lowerSecond,values.upperSecond];
  result.initial=[values.initialFirst,values.initialSecond];result.max_evaluations=values.pairBudget;
  result.material_evaluation.frequency_hz=values.frequency;
  return result;
}

export function applyMaterialSettings(doc,drafts) {
  if (doc?.schema === 'sipi.pair-impedance-design/2') return applyMaterialPairSettings(doc,drafts);
  return doc?.schema === 'sipi.impedance-study/4' ? applyMaterialSweepSettings(doc,drafts) : applyMaterialGoalSettings(doc,drafts);
}

export function createMaterialSettingsEditor(container, {onDraft, onApply}) {
  const document = container.ownerDocument;
  const node = (tag,text) => {const value=document.createElement(tag); if(text!==undefined)value.textContent=text; return value;};
  const heading=node('h3','Material target settings'), description=node('p'), grid=node('div');grid.className='material-goal-fields';
  const inputs={},labels={};
  for(const [name,text] of [...fields,sweepFields[3],...pairFields.filter(([name])=>name!=='frequency')]){
    const label=node('label',text), input=node('input');input.type='number';input.step=['budget','count','pairBudget'].includes(name)?'1':'any';
    input.id='material-goal-'+name;input.setAttribute('aria-describedby','material-goal-note');label.htmlFor=input.id;
    label.append(input);grid.append(label);inputs[name]=input;labels[name]=label;
  }
  const actions=node('div');actions.className='saved-actions';
  const apply=node('button','Apply settings'), reset=node('button','Reset form');apply.id='material-goal-apply';reset.id='material-goal-reset';actions.append(apply,reset);
  const note=node('p');note.id='material-goal-note';note.className='fine';note.setAttribute('role','status');
  container.append(heading,description,grid,actions,note);
  let source=null, settings=null, dirty=false, blocked=false;
  function update(){
    for(const input of Object.values(inputs))input.disabled=blocked;
    apply.disabled=reset.disabled=blocked||!dirty;
    note.textContent=dirty?'Unapplied settings. Apply or reset before running or saving the current input.':
      'Edit these settings, then apply them to the input. Geometry, material poles and mesh stay in the JSON. Applying checks the input without calculating.' +
      (settings?.kind==='sweep'?' Bounds and materials are checked before running. Failed calculation rows are retained without aggregate statistics. Sampled values do not guarantee manufacturing limits.':
       settings?.kind==='pair'?' Both targets must pass on the requested and refined meshes. The search is local; an evaluation budget does not guarantee a solution or limit elapsed time. Failed runs remain in the raw record.':'');
  }
  function restore(){
    for(const [name,input] of Object.entries(inputs)){labels[name].hidden=!Object.hasOwn(settings.values,name);input.value=labels[name].hidden?'':String(settings.values[name]);}
    for(const [name] of settings.kind==='pair'?pairFields:settings.kind==='sweep'?sweepFields:fields)grid.append(labels[name]);
    for(const name of ['lower','upper'])labels[name].firstChild.textContent=`${name==='lower'?'Lower':'Upper'} ${settings.kind==='sweep'?'sample':'search'} bound (dimensionless)`;
    dirty=false;update();
  }
  for(const [name,input] of Object.entries(inputs))input.addEventListener('input',()=>{
    if(blocked||!settings||!Object.hasOwn(settings.values,name))return;
    dirty=Object.keys(settings.values).some(name=>inputs[name].value!==String(settings.values[name]));update();onDraft();
  });
  apply.onclick=()=>{if(!blocked&&dirty)onApply(source,Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])));};
  reset.onclick=()=>{if(!blocked&&dirty){restore();onDraft();}};
  return {
    get dirty(){return dirty;},
    clearDraft(){if(settings)restore();},
    sync(text,disabled){
      blocked=disabled;
      if(text!==source){
        source=text;dirty=false;settings=null;
        try{const doc=JSON.parse(text);settings=materialGoalSettings(doc)||materialSweepSettings(doc)||materialPairSettings(doc);}catch{}
        container.hidden=settings===null;
        if(settings){heading.textContent=settings.kind==='sweep'?'Material sweep settings':settings.kind==='pair'?'Paired material target settings':'Material target settings';container.setAttribute('aria-label',heading.textContent);description.textContent=settings.description;restore();}
      }
      update();
    },
  };
}

export const createMaterialGoalEditor = createMaterialSettingsEditor;
