import test from 'node:test';
import assert from 'node:assert/strict';
import {polygonDrawing, checkDrawing} from '../ui/model.js';

const vertices = [[-.35,.8],[.35,.8],[.25,1.2],[0,1.2],[0,1.05],[-.35,1.05]];
const geometry = () => ({layers:[{thickness:2,eps_r:4}],box:{width:4},
  traces:[{kind:'polygon',name:'signal',vertices:structuredClone(vertices),ground:false}],
  dielectric_regions:[{name:'film',vertices:[[-.6,.7],[.6,.7],[.6,1.4],[-.6,1.4]],eps_r:3,tan_delta:.03}]});

test('concavity, orientation and exact input coordinates survive display preparation',()=>{
  for(const input of [vertices,vertices.toReversed()]){
    const original=structuredClone(input),shape=polygonDrawing(input);
    assert.deepEqual(shape.points,original);
    assert.deepEqual([shape.left,shape.right,shape.bottom,shape.top],[-.35,.35,.8,1.2]);
    shape.points[0][0]=99;assert.deepEqual(input,original);
  }
});
test('local materials and polygon names are not altered by display validation',()=>{
  const doc=geometry();doc.dielectric_regions[0].name='<script>window.changed=true</script>';
  const original=structuredClone(doc);checkDrawing(doc);assert.deepEqual(doc,original);
});
test('rectangular, tapered and zero-thickness conductors remain displayable',()=>{
  for(const thickness of [0,.1])for(const top of [undefined,.3]){
    const doc=geometry();doc.traces=[{x:0,y:1,width:.5,thickness,top_width:top}];
    delete doc.dielectric_regions;checkDrawing(doc);
  }
});
for(const [name,value] of Object.entries({missing:null,short:[[0,0],[1,1]],boolean:[[0,0],[1,true],[0,1]],
    string:[[0,0],[1,'1'],[0,1]],nonfinite:[[0,0],[1,Infinity],[0,1]],extra:[[0,0,1],[1,0],[0,1]]})){
  test('rejects '+name+' polygon coordinates before drawing',()=>assert.throws(()=>polygonDrawing(value)));
}
test('display limits reject excess complexity without truncating the document',()=>{
  for(const kind of ['layers','traces','dielectric_regions']){
    const doc=geometry();doc[kind]=Array.from({length:65},()=>structuredClone(doc[kind][0]));
    const original=structuredClone(doc);assert.throws(()=>checkDrawing(doc));assert.deepEqual(doc,original);
  }
  const tooMany=Array.from({length:16385},(_,i)=>[i,1]);assert.throws(()=>polygonDrawing(tooMany));assert.equal(tooMany.length,16385);
});
test('the exact display complexity boundary remains accepted',()=>{
  const doc=geometry();doc.layers=Array.from({length:64},()=>({thickness:1}));
  doc.traces=Array.from({length:64},()=>structuredClone(doc.traces[0]));
  doc.dielectric_regions=Array.from({length:64},()=>structuredClone(doc.dielectric_regions[0]));
  checkDrawing(doc);assert.equal(polygonDrawing(Array.from({length:16384},(_,i)=>[i,1])).points.length,16384);
});
test('nonfinite aggregate domain and malformed metal cannot enter the preview',()=>{
  for(const value of [0,-1,NaN,Infinity]){const doc=geometry();doc.box.width=value;assert.throws(()=>checkDrawing(doc));}
  const doc=geometry();doc.layers=[{thickness:Number.MAX_VALUE},{thickness:Number.MAX_VALUE}];assert.throws(()=>checkDrawing(doc));
  doc.layers=[{thickness:2}];doc.traces=[{x:0,y:1,width:.5,thickness:.1,top_width:NaN}];assert.throws(()=>checkDrawing(doc));
});
