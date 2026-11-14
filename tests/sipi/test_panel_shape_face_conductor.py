# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Face motion invariants, bounded work and preflight refusals."""
import numpy as np
import pytest
from sipi import CrossSection,Layer,Trace,PolygonTrace
import sipi.panel_shape_face_conductor as module
from sipi.panel_shape_conductor import _offset_velocity,PanelShapeCurrentError
from test_panel_shape_conductor import single


@pytest.mark.parametrize('top_width',[.0002,.0008,.0012])
@pytest.mark.parametrize('scale',[.001,1.,1000.])
@pytest.mark.parametrize('clockwise',[False,True])
def test_continuous_face_motion_has_exact_normals_and_whole_sum(top_width,scale,clockwise):
    trace=Trace('s',0.,.0008,.001,50e-6,top_width=top_width);points=trace.corners()*scale
    if clockwise:points=points[::-1]
    motions=[]
    for face in range(4):
        p,v=module._face_velocity(points,face);motions.append(v)
        edge=np.roll(p,-1,axis=0)-p;normals=np.column_stack((edge[:,1],-edge[:,0]))/np.linalg.norm(edge,axis=1)[:,None]
        for j in range(4):
            np.testing.assert_allclose(v[[j,(j+1)%4]]@normals[j],[-float(face==j)]*2,rtol=1e-12,atol=1e-12)
    _,whole,_=_offset_velocity(points)
    np.testing.assert_allclose(np.sum(motions,axis=0),whole,rtol=1e-12,atol=1e-12)


@pytest.mark.parametrize('count',[1,2,3,4])
def test_exact_request_budget_and_all_offsets_are_preflighted_without_fields(monkeypatch,count):
    def forbidden(*a,**k):pytest.fail('preflight reached fields')
    monkeypatch.setattr(module,'_panel_solver',forbidden);monkeypatch.setattr(module,'panel_shape_current_factors',forbidden)
    traces=[Trace(str(i),(i-(count-1)/2)*.001,.0003,.001,50e-6,ground=(i==1)) for i in range(count)]
    section=CrossSection([Layer('u',.01105,4.)],traces,.02)
    checked,h,requests=module._prepare_faces(section,32,1024,16,.001)
    assert len(requests)==16*count and 16*count+(4*count+5)==20*count+5<=85
    assert checked.traces==section.traces and h>0
    assert len({r.stage for r in requests})==len(requests)
    assert requests[0].stage=='face-step-0/trace-0/bottom/sign--1'
    assert all(r.height==section.height and r.width==section.width for r in requests)
    with pytest.raises(ValueError):requests[0].polygons[0].setflags(write=True)


@pytest.mark.parametrize('kind',['type','polygon','five','zero','overlap-offset','top-ground','aspect',
    'step-zero','step-bool','step-nan','step-large','panels-zero','panels-float','panels-count',
    'modes-low','modes-high','degree-odd','degree-bool'])
def test_invalid_geometry_and_controls_fail_before_whole_currents(monkeypatch,kind):
    def forbidden(*a,**k):pytest.fail('invalid input reached fields')
    monkeypatch.setattr(module,'panel_shape_current_factors',forbidden);monkeypatch.setattr(module,'_panel_solver',forbidden)
    section=single();options={}
    if kind=='type':section=None
    if kind=='polygon':section=CrossSection(section.layers,[PolygonTrace('s',section.traces[0].corners())],section.width)
    if kind=='five':section=CrossSection(section.layers,[Trace(str(i),(i-2)*.001,.0003,.001,50e-6) for i in range(5)],section.width)
    if kind=='zero':section=CrossSection(section.layers,[Trace('s',0.,.0008,.0008,0.)],section.width)
    if kind=='overlap-offset':section=CrossSection(section.layers,[Trace('a',-.0004000001,.0008,.0008,35e-6),Trace('b',.0004000001,.0008,.0008,35e-6)],section.width)
    if kind=='top-ground':section=CrossSection(section.layers,section.traces,section.width,top='ground')
    if kind=='aspect':section=CrossSection(section.layers,section.traces,.1)
    if kind.startswith('step-'):options['step_fraction']={'step-zero':0.,'step-bool':True,'step-nan':np.nan,'step-large':.1}[kind]
    if kind.startswith('panels-'):options['panels_per_edge']={'panels-zero':0,'panels-float':2.,'panels-count':257}[kind]
    if kind.startswith('modes-'):options['ground_modes']=63 if kind=='modes-low' else 4097
    if kind.startswith('degree-'):options['interpolation_degree']=True if kind=='degree-bool' else 11
    with pytest.raises((TypeError,ValueError)):module.panel_shape_face_current_factors(section,**options)


def test_original_whole_current_exception_is_preserved(monkeypatch):
    error=PanelShapeCurrentError('original partial whole-current failure',samples=())
    def fail(*a,**k):raise error
    monkeypatch.setattr(module,'panel_shape_current_factors',fail)
    monkeypatch.setattr(module,'_panel_solver',lambda:pytest.fail('whole failure reached face fields'))
    with pytest.raises(PanelShapeCurrentError) as caught:module.panel_shape_face_current_factors(single())
    assert caught.value is error
