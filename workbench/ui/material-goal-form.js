// This editor changes saved settings only. The engine validates both documents.
const finite = value => typeof value === 'number' && Number.isFinite(value);
const names = {z0:'Single-ended', z_diff:'Differential', z_common:'Common-mode'};
const fields = [
  ['target', 'Target impedance (Ω)'], ['tolerance', 'Allowed error (Ω)'],
  ['lower', 'Lower search bound (dimensionless)'], ['upper', 'Upper search bound (dimensionless)'],
  ['frequency', 'Evaluation frequency (Hz)'], ['budget', 'Maximum evaluations (3–128)'],
];

export function materialGoalSettings(doc) {
  if (doc?.schema !== 'sipi.impedance-design/3' || !Object.hasOwn(names,doc.quantity) ||
      !doc.material_variables || Object.keys(doc.material_variables).length !== 1 ||
      !Object.hasOwn(doc.material_variables,doc.variable)) return null;
  const binding = doc.material_variables[doc.variable], evaluation = doc.material_evaluation;
  const model = evaluation?.materials?.[binding?.region], path = binding?.path;
  if (model?.schema !== 'sipi.dielectric/1' || !Array.isArray(path)) return null;
  let variable;
  if (model.kind === 'constant' && path.length === 1 && path[0] === 'eps_r') variable = 'Relative permittivity';
  else if (model.kind === 'debye' && path.length === 2 && path[0] === 'strengths' &&
      Number.isInteger(path[1]) && path[1] >= 0 && Array.isArray(model.parameters?.strengths) &&
      path[1] < model.parameters.strengths.length) variable = `Debye strength ${path[1]+1}`;
  else return null;
  const leaf = model.kind === 'constant' ? model.parameters?.eps_r : model.parameters.strengths[path[1]];
  if (!finite(leaf) || !Array.isArray(doc.bounds) || doc.bounds.length !== 2) return null;
  const values = {target:doc.target_ohm, tolerance:doc.tolerance_ohm, lower:doc.bounds[0],
    upper:doc.bounds[1], frequency:evaluation.frequency_hz, budget:doc.max_evaluations};
  if (!Object.values(values).every(finite)) return null;
  return {values, description:`${names[doc.quantity]} target · ${variable} · region ${binding.region}`};
}

export function applyMaterialGoalSettings(doc, drafts) {
  if (!materialGoalSettings(doc)) throw new Error('This input has no supported material target form.');
  const values = {};
  for (const [name,label] of fields) {
    const raw = drafts[name];
    if (typeof raw !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(raw.trim()) ||
        !Number.isFinite(Number(raw))) throw new Error(`${label}: enter a finite number.`);
    values[name] = Number(raw);
  }
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

export function createMaterialGoalEditor(container, {onDraft, onApply}) {
  const document = container.ownerDocument;
  const node = (tag,text) => {const value=document.createElement(tag); if(text!==undefined)value.textContent=text; return value;};
  const heading=node('h3','Material target settings'), description=node('p'), grid=node('div');grid.className='material-goal-fields';
  const inputs={};
  for(const [name,text] of fields){
    const label=node('label',text), input=node('input');input.type='number';input.step=name==='budget'?'1':'any';
    input.id='material-goal-'+name;input.setAttribute('aria-describedby','material-goal-note');label.htmlFor=input.id;
    label.append(input);grid.append(label);inputs[name]=input;
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
      'Edit these settings, then apply them to the input. Geometry, material poles and mesh stay in the JSON. Applying checks the input without calculating.';
  }
  function restore(){for(const [name,input] of Object.entries(inputs))input.value=String(settings.values[name]);dirty=false;update();}
  for(const input of Object.values(inputs))input.addEventListener('input',()=>{
    if(blocked)return;
    dirty=Object.entries(inputs).some(([name,input])=>input.value!==String(settings.values[name]));update();onDraft();
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
        try{settings=materialGoalSettings(JSON.parse(text));}catch{}
        container.hidden=settings===null;
        if(settings){description.textContent=settings.description;restore();}
      }
      update();
    },
  };
}
