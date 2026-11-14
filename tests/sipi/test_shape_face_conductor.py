# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Face-material admission and isolated boundary weighting invariants."""
from dataclasses import replace,FrozenInstanceError
import numpy as np
import pytest
from sipi import CrossSection,Layer,Trace,PolygonTrace,MetalLayer
from sipi.boundary_conductor import SurfaceMetal,LayeredSurfaceMetal
from sipi.face_conductor import TraceFaceMetals,ReferenceSurfaceMetals
from sipi.panel_shape_conductor import PanelShapeCurrentFactors,PanelShapeSample,PanelShapeRequest,PanelShapeCurrentError
from sipi.panel_shape_face_conductor import PanelShapeFaceCurrentFactors,PanelShapeFaceCurrentError
from sipi.shape_face_conductor import panel_shape_conductor_loss_by_face as solve
import sipi.shape_face_conductor as module
from sipi.constants import mu_0
from test_layered_metal import LAYERS,transfer

F=np.array([1e9,4e9,16e9]);FACES=('bottom','top','left','right')
OPTIONS=dict(ground_modes=4096,interpolation_degree=16,step_fraction=.001)


def geometry():
    return CrossSection([Layer('u',.01105,1.)],[
        Trace('a',-.0005,.0003,.001,50e-6,top_width=.00022),
        Trace('guard',0.,.0002,.001,50e-6,ground=True,top_width=.00012),
        Trace('b',.0005,.0004,.001,60e-6,top_width=.00055)],.02)


def materials(ground_faces=True):
    signals={'a':TraceFaceMetals(SurfaceMetal(58e6),LayeredSurfaceMetal(58e6,coatings=LAYERS),SurfaceMetal(35e6),SurfaceMetal(20e6)),
             'b':TraceFaceMetals.uniform(SurfaceMetal(45e6))}
    g=TraceFaceMetals(SurfaceMetal(30e6),SurfaceMetal(40e6),SurfaceMetal(50e6),SurfaceMetal(60e6)) if ground_faces else SurfaceMetal(30e6)
    return signals,ReferenceSurfaceMetals(SurfaceMetal(48e6),None,None,{'guard':g})


def synthetic(section):
    # Algebra-only positive energy matrices, not field or accuracy evidence.
    traces=section.traces;names=tuple(t.name for t in traces if not t.ground);n=len(names)
    signal=[i for i,t in enumerate(traces) if not t.ground];ground=[i for i,t in enumerate(traces) if t.ground]
    q=np.array([(np.eye(n)+.1*np.ones((n,n)))*(i+1) for i in range(4*len(traces)+1)])
    whole=np.concatenate((q[:-1].reshape(len(traces),4,n,n).sum(axis=1),q[-1:]))
    grouped=np.concatenate((whole[signal],whole[ground+[len(traces)]].sum(axis=0,keepdims=True)))
    base=PanelShapeCurrentFactors(names,grouped,np.vstack((np.eye(n),-np.ones(n))),np.eye(n)*1e-11,
        tuple(t.name for t in traces if t.ground),{'synthetic':1},(),1e-8,np.array([grouped,grouped]),np.array([whole,whole]))
    request=PanelShapeRequest('synthetic',tuple(t.corners() for t in traces),section.width,section.height,32,4096,16)
    sample=PanelShapeSample(request,np.eye(len(traces)),{'synthetic':1})
    return PanelShapeFaceCurrentFactors(base,tuple(t.name for t in traces),tuple(t.ground for t in traces),
        np.array([q,q]),(sample,)*(16*len(traces)),{'synthetic':1})


def stub(monkeypatch,section=None):
    section=geometry() if section is None else section;factors=synthetic(section);calls=[]
    def extract(section,**options):calls.append(options);return factors
    monkeypatch.setattr(module,'panel_shape_face_current_factors',extract)
    return factors,calls


@pytest.mark.parametrize('ground_faces',[False,True])
def test_independent_impedances_named_parts_and_immutable_snapshots(monkeypatch,ground_faces):
    factors,calls=stub(monkeypatch);signals,reference=materials(ground_faces)
    r=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6,**OPTIONS)
    assert len(calls)==1 and r.factors is factors
    indices=list(range(4))+list(range(8,12))+[12]
    parts=list(factors.parts[indices]);parts.extend(factors.parts[4:8] if ground_faces else [factors.parts[4:8].sum(axis=0)])
    np.testing.assert_array_equal(r.boundary_parts,parts)
    sigmas=[58e6,58e6,35e6,20e6]+[45e6]*4+[48e6]+([30e6,40e6,50e6,60e6] if ground_faces else [30e6])
    z=np.sqrt(2j*np.pi*F[:,None]*mu_0/np.array(sigmas));z[:,1]=[transfer(f) for f in F]
    np.testing.assert_allclose(r.surface_impedance,z,rtol=1e-12,atol=0)
    expected=sum(z[:,i,None,None]*p for i,p in enumerate(parts))
    np.testing.assert_allclose(r.R+2j*np.pi*F[:,None,None]*r.L_internal,expected,rtol=1e-12,atol=0)
    np.testing.assert_allclose(r.resistance_parts.sum(axis=1),r.R,rtol=1e-12,atol=0)
    signals.clear();assert r.metals[0].conductivity==58e6
    for a in (r.R,r.L_internal,r.frequency,r.skin_depth,r.roughness_factor,r.surface_impedance,r.boundary_parts,r.resistance_parts):
        with pytest.raises(ValueError):a.flat[0]=0
        with pytest.raises(ValueError):a.setflags(write=True)
    with pytest.raises(FrozenInstanceError):r.metals=()
    for changes in (dict(boundary_labels=r.boundary_labels[::-1]),dict(boundary_parts=r.boundary_parts[::-1]),dict(metals=r.metals[:-1]),dict(R=r.R[:1])):
        with pytest.raises(ValueError):replace(r,**changes)


@pytest.mark.parametrize('location',['signal-bottom','signal-top','signal-left','signal-right','plane','ground-bottom','ground-top','ground-left','ground-right'])
def test_one_metal_change_is_one_boundary_contribution(monkeypatch,location):
    stub(monkeypatch);signals,reference=materials();base=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    changed=SurfaceMetal(12e6)
    if location.startswith('signal-'):
        face=location.split('-')[1];signals['a']=replace(signals['a'],**{face:changed});index=FACES.index(face)
    elif location=='plane':reference=replace(reference,bottom=changed);index=8
    else:
        face=location.split('-')[1];reference=replace(reference,conductors={'guard':replace(reference.conductors['guard'],**{face:changed})});index=9+FACES.index(face)
    r=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    delta=(np.sqrt(2j*np.pi*F*mu_0/12e6)-base.surface_impedance[:,index])[:,None,None]*base.boundary_parts[index]
    np.testing.assert_allclose((r.R-base.R)+2j*np.pi*F[:,None,None]*(r.L_internal-base.L_internal),delta,rtol=1e-12,atol=0)
    others=[i for i in range(len(base.metals)) if i!=index]
    np.testing.assert_array_equal(r.resistance_parts[:,others],base.resistance_parts[:,others])


@pytest.mark.parametrize('kind',['section','polygon','five','zero','top-ground','signals-missing','signals-extra','signal-whole','reference-common',
    'ground-missing','ground-extra','bottom-missing','top-metal','side-metal','plane-depth','ground-face-depth','signal-face-depth',
    'plane-core','ground-face-core','signal-face-core','dc','frequency-order'])
def test_all_material_refusals_precede_fields(monkeypatch,kind):
    section=geometry();signals,reference=materials();thickness=35e-6;f=F
    if kind=='section':section=None
    if kind=='polygon':section=CrossSection(section.layers,[PolygonTrace(t.name,t.corners(),ground=t.ground) for t in section.traces],section.width)
    if kind=='five':section=CrossSection(section.layers,[Trace(str(i),(i-2)*.001,.0003,.001,50e-6) for i in range(5)],section.width)
    if kind=='zero':section=CrossSection(section.layers,[Trace('a',0.,.0003,.001,0.)],section.width)
    if kind=='top-ground':section=CrossSection(section.layers,section.traces,section.width,top='ground')
    if kind=='signals-missing':signals.pop('a')
    if kind=='signals-extra':signals['extra']=signals['a']
    if kind=='signal-whole':signals['a']=SurfaceMetal(58e6)
    if kind=='reference-common':reference=SurfaceMetal(58e6)
    if kind=='ground-missing':reference=replace(reference,conductors={})
    if kind=='ground-extra':reference=replace(reference,conductors=dict(reference.conductors,extra=SurfaceMetal(58e6)))
    if kind=='bottom-missing':reference=replace(reference,bottom=None)
    if kind=='top-metal':reference=replace(reference,top=SurfaceMetal(58e6))
    if kind=='side-metal':reference=replace(reference,sides=SurfaceMetal(58e6))
    if kind=='plane-depth':thickness=1e-7
    if kind=='ground-face-depth':reference=replace(reference,conductors={'guard':replace(reference.conductors['guard'],left=SurfaceMetal(1e4))})
    if kind=='signal-face-depth':signals['a']=replace(signals['a'],right=SurfaceMetal(1e4))
    core=LayeredSurfaceMetal(58e6,coatings=(MetalLayer(30e-6,40e6),))
    if kind=='plane-core':reference=replace(reference,bottom=core)
    if kind=='ground-face-core':reference=replace(reference,conductors={'guard':replace(reference.conductors['guard'],top=core)})
    if kind=='signal-face-core':signals['a']=replace(signals['a'],bottom=core)
    if kind=='dc':f=[0.,1e9]
    if kind=='frequency-order':f=[1e9,1e9]
    monkeypatch.setattr(module,'panel_shape_face_current_factors',lambda *a,**k:pytest.fail('invalid material invoked fields'))
    with pytest.raises((ValueError,TypeError)):solve(section,f,conductors=signals,reference=reference,ground_thickness=thickness)


@pytest.mark.parametrize('kind',['whole','face','interrupt'])
def test_original_partial_failure_or_interrupt_propagates_unchanged(monkeypatch,kind):
    factors,_=stub(monkeypatch)
    error={'whole':PanelShapeCurrentError('whole failed',samples=()),'face':PanelShapeFaceCurrentError('face failed',base=factors.base,samples=factors.samples[:3]),'interrupt':KeyboardInterrupt()}[kind]
    def fail(*a,**k):raise error
    monkeypatch.setattr(module,'panel_shape_face_current_factors',fail);signals,reference=materials()
    with pytest.raises(type(error)) as caught:solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    assert caught.value is error


@pytest.mark.parametrize('count',[0,1,2])
@pytest.mark.parametrize('faces',[False,True])
def test_zero_multiple_and_separator_names_keep_structural_ground_assignment(monkeypatch,count,faces):
    traces=[Trace('s',-.002,.0003,.001,50e-6)]+[Trace(n,i*.001,.0003,.001,50e-6,ground=True) for i,n in enumerate(('g','g:bottom')[:count])]
    section=CrossSection([Layer('u',.01105,1.)],traces,.02);factors,_=stub(monkeypatch,section)
    metal=SurfaceMetal(58e6);reference=ReferenceSurfaceMetals(metal,None,None,{t.name:TraceFaceMetals.uniform(metal) if faces else metal for t in traces if t.ground})
    r=solve(section,F,conductors={'s':TraceFaceMetals.uniform(metal)},reference=reference,ground_thickness=35e-6)
    parts=list(factors.parts[:4])+[factors.parts[-1]]
    for i in range(count):parts.extend(factors.parts[4*(i+1):4*(i+2)] if faces else [factors.parts[4*(i+1):4*(i+2)].sum(axis=0)])
    np.testing.assert_array_equal(r.boundary_parts,parts)


@pytest.mark.parametrize('location',['signal','plane','ground'])
def test_rms_surface_law_changes_only_target_real_impedance(monkeypatch,location):
    stub(monkeypatch);signals,reference=materials();a=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    index={'signal':0,'plane':8,'ground':11}[location];metal=replace(a.metals[index],roughness_rms=.5e-6)
    if location=='signal':signals['a']=replace(signals['a'],bottom=metal)
    if location=='plane':reference=replace(reference,bottom=metal)
    if location=='ground':reference=replace(reference,conductors={'guard':replace(reference.conductors['guard'],left=metal)})
    b=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    delta=np.sqrt(1/(np.pi*F*mu_0*metal.conductivity));factor=1+2/np.pi*np.arctan(1.4*(.5e-6/delta)**2)
    np.testing.assert_allclose(b.surface_impedance[:,index].real,a.surface_impedance[:,index].real*factor,rtol=1e-12,atol=0)
    np.testing.assert_array_equal(b.L_internal,a.L_internal)
