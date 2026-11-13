import test from 'node:test';
import assert from 'node:assert/strict';
import {assertRegisteredForms,registeredNames,registeredInput,registeredInputText} from './registered-forms.mjs';

test('registry checks the complete names, including multiplicity',async()=>{
  assert.equal(registeredNames.length,45);
  assert.deepEqual(await assertRegisteredForms({evaluate:async()=>[...registeredNames].reverse()}),[...registeredNames].reverse());
  for(const names of [registeredNames.slice(1),[...registeredNames,'unknown'],[registeredNames[0],...registeredNames.slice(0,-1)]])
    await assert.rejects(assertRegisteredForms({evaluate:async()=>names}));
});
test('stored geometry and parameters are detached and missing names reject',()=>{
  for(const name of registeredNames){
    const a=registeredInput(name),b=registeredInput(name);
    assert.deepEqual(JSON.parse(registeredInputText(name)),b);
    assert.equal(a.template,name);assert.ok(a.cross_section.traces.length);
    a.parameters.extra=1;a.cross_section.traces.length=0;
    assert.deepEqual(registeredInput(name),b);
  }
  assert.throws(()=>registeredInput('unknown'));
});
