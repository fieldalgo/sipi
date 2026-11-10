// Real recorded data plus hostile presentation text; Python's csv reader checks
// every exported field independently of the JavaScript serializer.
import assert from 'node:assert/strict';
import {readFile,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {materialStudyCSV,materialResultView} from '../ui/material-results.js';
const fixtures=JSON.parse(await readFile(process.argv[2],'utf8'));
const directory=await mkdtemp(join(tmpdir(),'sipi-study-csv-'));let checks=0;
async function check(execution){
 const before=JSON.stringify(execution),text=materialStudyCSV(execution);
 assert.equal(typeof text,'string');assert.equal(JSON.stringify(execution),before);
 await writeFile(join(directory,'samples.csv'),text);await writeFile(join(directory,'execution.json'),before);
 const result=spawnSync(process.env.SIPI_PYTHON||'python',['workbench/tests/check_study_csv.py',join(directory,'samples.csv'),join(directory,'execution.json')],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).status,'passed');checks++;
}
try{
 for(const {execution} of fixtures)await check(execution);
 const base=fixtures.find(row=>row.execution.status==='complete').execution;
 for(const name of ['axis,"quoted"\nε','=2+2',' +1','-text','@command','\tplain','\rplain','\nplain','\u2003=2','\uFEFF=2']){
  const doc=structuredClone(base),old=doc.input.sampling.variables[0].name;
  doc.input.sampling.variables[0].name=name;doc.input.material_variables[name]=doc.input.material_variables[old];delete doc.input.material_variables[old];
  await check(doc);
 }
 const failed=structuredClone(fixtures.find(row=>row.execution.status==='incomplete').execution);
 for(const row of failed.result.rows.filter(row=>row.error!==null)){row.error_type='=untrusted';row.error='comma, quote" and\nsecond line';}
 await check(failed);
 const precise=structuredClone(base);precise.result.rows[0].value=1.2345678901234567;await check(precise);
 assert.ok(materialStudyCSV(precise).includes('1.2345678901234567'));
 for(const change of [d=>d.schema='future/1',d=>d.input.schema='future/1',d=>d.status='failed',d=>d.error={},d=>d.result=null,
   d=>d.result.unit='F',d=>d.result.quantity='unknown',d=>d.result.rows=[],d=>d.result.rows[0].index=4,d=>d.result.rows[0].value=NaN,
   d=>d.result.rows[0].value=Infinity,d=>d.result.rows[0].error='unmatched',d=>d.result.summary=null,d=>d.result.failed=99,
   d=>d.input.sampling.variables[0].name='',d=>d.input.material_variables[Object.keys(d.input.material_variables)[0]].path=['unknown']]){
  const copy=structuredClone(base);change(copy);assert.equal(materialStudyCSV(copy),null);checks++;
 }
 for(const value of [null,{},[],{schema:'sipi.execution/1',input:null}, {schema:'sipi.execution/1',input:{schema:'sipi.lumped-network/1'}}]){assert.equal(materialStudyCSV(value),null);checks++;}
 assert.equal(materialResultView(base).tables[0].rows.length,base.result.rows.length);
 console.log(JSON.stringify({status:'passed',checks}));
}finally{await rm(directory,{recursive:true,force:true});}
