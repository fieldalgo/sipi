// Read the original frozen engine fixture and separately recorded extensions;
// do not infer choices from the UI. These snapshots check inputs, not accuracy.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const reference=JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/template_section/reference.json',import.meta.url),'utf8'));
reference.cases.push(...JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/layered_microstrip/inputs.json',import.meta.url),'utf8')).cases);
reference.cases.push(...JSON.parse(readFileSync(new URL('../../tests/sipi/reference_data/asymmetric_layered_microstrip/inputs.json',import.meta.url),'utf8')).cases);
export const registeredNames=reference.cases.map(row=>row.template).sort();

export function registeredInput(name) {
  const row=reference.cases.find(row=>row.template===name);
  assert.ok(row,`Unknown registered template: ${name}`);
  return structuredClone({schema:'sipi.template-section/1',template:name,
    parameters:row.resolved_parameters,cross_section:row.cross_section});
}

export function registeredInputText(name) {
  // Preserve the engine fixture's signed zero through JavaScript serialization.
  return JSON.stringify(registeredInput(name),(_,value)=>Object.is(value,-0)?'__sipi_negative_zero__':value)
    .replaceAll('"__sipi_negative_zero__"','-0.0');
}

export async function assertRegisteredForms(cdp) {
  const names=await cdp.evaluate('[...document.querySelectorAll("[data-template]")].map(button=>button.dataset.template)');
  assert.deepEqual([...names].sort(),registeredNames);
  return names;
}
