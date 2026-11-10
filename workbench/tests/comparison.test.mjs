import test from 'node:test';
import assert from 'node:assert/strict';
import {compareLines} from '../ui/model.js';
const line = {names:['signal'],C:[[4e-12]],L:[[8e-9]],G_1GHz:[[0]],z0:50,eps_eff:4,delay:2e-9};
test('literal scalar engineering values and zero baseline',()=>{
 const result=compareLines(line,{...line,C:[[5e-12]],L:[[6e-9]],G_1GHz:[[.002]],z0:55,eps_eff:3,delay:3e-9});
 assert.ok(result.compatible);assert.equal(result.rows.length,6);
 const rows=Object.fromEntries(result.rows.map(r=>[r.key,r]));
 for(const [key,b,c,d,p] of [['z0',50,55,5,10],['eps_eff',4,3,-1,-25],['delay',2,3,1,50],['C:0:0',4,5,1,25],['L:0:0',8,6,-2,-25],['G_1GHz:0:0',0,2,2,null]]) {
  for(const [k,v] of Object.entries({baseline:b,current:c,delta:d,percent:p})) {
   if(v===null)assert.equal(rows[key][k],null);else assert.ok(Math.abs(rows[key][k]-v)<1e-12,`${key}.${k}`);
  }
 }
});
test('ordered names and dimensions are required; asymmetric pair matrices survive',()=>{
 const a={names:['left','right'],C:[[10e-12,-4e-12],[-4e-12,8e-12]],L:[[5e-9,1e-9],[1e-9,6e-9]],G_1GHz:[[0,0],[0,0]],scalar_summary_unavailable:'asymmetric'};
 const b=structuredClone(a);b.C[0][1]=-3e-12;b.C[1][0]=-3e-12;
 const result=compareLines(a,b);assert.equal(result.rows.length,12);
 const row=result.rows.find(r=>r.key==='C:0:1');assert.ok(Math.abs(row.delta-1)<1e-12);assert.ok(Math.abs(row.percent-25)<1e-12);
 assert.equal(compareLines(a,{...b,names:['right','left']}).compatible,false);
 assert.equal(compareLines(a,line).compatible,false);
 assert.equal(compareLines(a,{...b,C:[[1,2]]}).compatible,false);
 assert.equal(compareLines(a,{...b,L:[[1,NaN],[2,3]]}).compatible,false);
});

test('pair scalars are shared finite quantities and never inferred from asymmetric matrices',()=>{
 const a={names:['p','n'],C:[[10e-12,-4e-12],[-4e-12,10e-12]],L:[[5e-9,1e-9],[1e-9,5e-9]],G_1GHz:[[0,0],[0,0]],z_diff:100,z_common:30,z_even:60,z_odd:50,eps_eff_even:4,eps_eff_odd:3};
 const before=structuredClone(a),b={...a,z_diff:98,eps_eff_odd:NaN};
 const result=compareLines(a,b);assert.equal(result.rows.length,17);
 const row=result.rows.find(r=>r.key==='z_diff');assert.deepEqual([row.baseline,row.current,row.delta,row.percent],[100,98,-2,-2]);
 assert.equal(result.rows.some(r=>r.key==='eps_eff_odd'),false);
 assert.equal(compareLines(a,{...b,scalar_summary_unavailable:'asymmetric'}).rows.length,12);
 assert.deepEqual(a,before);
});
test('unsupported counts, nonfinite matrices and derived overflow refuse comparison',()=>{
 assert.equal(compareLines(null,line).compatible,false);
 assert.equal(compareLines({...line,names:['a','b','c']},line).compatible,false);
 assert.equal(compareLines(line,{...line,C:[[Infinity]]}).compatible,false);
 assert.equal(compareLines({...line,z0:1e-320},{...line,z0:1e308}).compatible,false);
 assert.equal(compareLines({...line,C:[[1e308]]},line).compatible,false);
});
