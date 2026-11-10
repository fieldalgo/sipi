import assert from 'node:assert/strict';
import {test} from 'node:test';
import {drawingWindow} from '../ui/model.js';

// Synthetic display coordinates, not a physical coating or field reference.
function fixture(pair) {
  const signal = x => ({x,y:.0065,width:.0005,top_width:.0004,thickness:.000035});
  return {box:{width:.012,bottom:'open',top:'open',sides:'open'},
    layers:[{thickness:.006},{thickness:.0005},{thickness:.006055}],
    traces:[...(pair?[signal(-.0004),signal(.0004)]:[signal(0)]),
      {x:-.002,y:.0065,width:.001,thickness:.000035,ground:true},
      {x:.002,y:.0065,width:.001,thickness:.000035,ground:true}],
    dielectric_regions:[{vertices:[[-.006,.0065],[.006,.0065],[.006,.006555],[-.006,.006555]]}]};
}
function freeze(v) { if (v && typeof v === 'object') { Object.values(v).forEach(freeze); Object.freeze(v); } return v; }
for (const pair of [false,true]) {
  test(`display crop contains ${pair?'paired':'single'} conductors and region heights without changing input`,()=>{
    const model=freeze(fixture(pair)),before=JSON.stringify(model),full=drawingWindow(model),view=drawingWindow(model,true);
    assert.deepEqual(full,{left:-.006,right:.006,bottom:0,top:model.layers.reduce((s,l)=>s+l.thickness,0),detail:false,clipped:[]});
    assert.deepEqual(view.clipped,['left','right','bottom','top']);
    assert.ok(view.right-view.left<full.right-full.left);
    assert.ok(view.top-view.bottom<(full.top-full.bottom)/20);
    for(const t of model.traces){const span=Math.max(t.width,t.top_width??t.width);assert.ok(view.left<=t.x-span/2&&view.right>=t.x+span/2);assert.ok(view.bottom<=t.y&&view.top>=t.y+t.thickness);}
    for(const region of model.dielectric_regions)for(const [,y] of region.vertices)assert.ok(y>=view.bottom&&y<=view.top);
    assert.equal(JSON.stringify(model),before);assert.deepEqual(drawingWindow(model),full);
  });
}
test('zero-thickness traces keep finite bounds and touching boundaries stay declared',()=>{
  const model=freeze({box:{width:2,bottom:'ground',top:'open',sides:'open'},layers:[{thickness:1}],traces:[{x:0,y:0,width:2,thickness:0}]});
  const view=drawingWindow(model,true);assert.equal(view.left,-1);assert.equal(view.right,1);assert.equal(view.bottom,0);assert.ok(view.top>0);assert.deepEqual(view.clipped,['top']);
});
test('polygon vertices are read directly and invalid display bounds are rejected',()=>{
  const vertices=[[-.2,.4],[.3,.4],[.1,.7]];
  const model=freeze({box:{width:2},layers:[{thickness:1}],traces:[{kind:'polygon',vertices}]});
  const view=drawingWindow(model,true);for(const [x,y] of vertices)assert.ok(x>=view.left&&x<=view.right&&y>=view.bottom&&y<=view.top);
  assert.throws(()=>drawingWindow(model,'detail'),/Unknown/);assert.throws(()=>drawingWindow({...model,box:{width:NaN}},true),/finite/);
});
