# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent boundary sums and field-free metal admission."""
from dataclasses import FrozenInstanceError
import numpy as np
import pytest
from sipi.boundary_conductor import SurfaceMetal,LayeredSurfaceMetal
from sipi.layered_metal import MetalLayer
from sipi.face_conductor import ReferenceSurfaceMetals,TraceFaceMetals
from sipi.panel_shape_conductor import PanelShapeCurrentFactors,PanelShapeCurrentError
from sipi.shape_reference_conductor import panel_shape_conductor_loss_with_reference_metals as solve
import sipi.shape_reference_conductor as module
from sipi.constants import mu_0
from test_panel_shape_conductor import guard
from test_layered_metal import transfer,LAYERS

F=np.array([1e9,4e9,16e9])


def metals(coated=False):
    signals={'a':SurfaceMetal(58e6),'b':SurfaceMetal(35e6)}
    ground=LayeredSurfaceMetal(58e6,coatings=LAYERS) if coated else SurfaceMetal(20e6)
    return signals,ReferenceSurfaceMetals(SurfaceMetal(45e6),None,None,{'guard':ground})


def fake(monkeypatch):
    # Deliberately synthetic positive matrices; test material weighting only.
    pieces=np.array([[[2.,.1],[.1,1.]],[[1.,-.2],[-.2,3.]],
                     [[1.,.3],[.3,2.]],[[4.,-.1],[-.1,1.]]])
    grouped=np.array([pieces[0],pieces[2],pieces[[1,3]].sum(axis=0)])
    factors=PanelShapeCurrentFactors(names=('a','b'),parts=grouped,
        current_integrals=np.array([[1.,0.],[0.,1.],[-1.,-1.]]),
        C0=np.array([[2.,-.4],[-.4,3.]])*1e-11,ground_trace_names=('guard',),
        diagnostics={'transport_stub':1.},samples=(),step_m=1e-8,
        step_parts=np.array([grouped,grouped]),boundary_step_parts=np.array([pieces,pieces]))
    calls=[]
    def extract(section,**options):calls.append(options);return factors
    monkeypatch.setattr(module,'panel_shape_current_factors',extract)
    return factors,calls


@pytest.mark.parametrize('coated',[False,True])
def test_independent_complex_transfer_and_each_boundary_sum(monkeypatch,coated):
    factors,calls=fake(monkeypatch);signals,reference=metals(coated)
    result=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    assert len(calls)==1 and result.factors is factors
    assert result.boundary_labels==('signal:a','signal:b','reference:bottom','reference:ground:guard')
    np.testing.assert_array_equal(result.boundary_parts,factors.boundary_step_parts[-1,[0,2,3,1]])
    zs=np.column_stack([np.sqrt(2j*np.pi*F*mu_0/s) for s in (58e6,35e6,45e6,20e6)])
    if coated:zs[:,-1]=[transfer(f) for f in F]
    np.testing.assert_allclose(result.surface_impedance,zs,rtol=1e-12,atol=0)
    total=np.zeros((len(F),2,2),complex)
    for i in range(4):total+=zs[:,i,None,None]*result.boundary_parts[i]
    np.testing.assert_allclose(result.R+2j*np.pi*F[:,None,None]*result.L_internal,total,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1),result.R,rtol=1e-12,atol=0)
    assert np.all(np.linalg.eigvalsh(result.R)>0)
    signals.clear();assert result.metals[0].conductivity==58e6
    for value in (result.frequency,result.R,result.L_internal,result.skin_depth,result.surface_impedance,result.boundary_parts,result.resistance_parts):
        with pytest.raises(ValueError):value.flat[0]=0
        with pytest.raises(ValueError):value.setflags(write=True)
    with pytest.raises(FrozenInstanceError):result.metals=()


@pytest.mark.parametrize('target',['signal','guard','bottom'])
def test_one_changed_metal_changes_only_its_independent_loss_contribution(monkeypatch,target):
    fake(monkeypatch);signals,reference=metals();base=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    changed=SurfaceMetal(12e6);index={'signal':0,'bottom':2,'guard':3}[target]
    if target=='signal':signals['a']=changed
    if target=='bottom':reference=ReferenceSurfaceMetals(changed,None,None,reference.conductors)
    if target=='guard':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{'guard':changed})
    got=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    delta=(np.sqrt(2j*np.pi*F*mu_0/12e6)-base.surface_impedance[:,index])[:,None,None]*base.boundary_parts[index]
    np.testing.assert_allclose((got.R-base.R)+2j*np.pi*F[:,None,None]*(got.L_internal-base.L_internal),delta,rtol=1e-12,atol=0)
    others=[i for i in range(4) if i!=index]
    np.testing.assert_array_equal(got.resistance_parts[:,others],base.resistance_parts[:,others])


@pytest.mark.parametrize('kind',['section','signals-missing','signals-extra','signal-type','reference-type',
    'ground-missing','ground-extra','ground-faces','bottom-missing','top-metal','side-metal',
    'plane-depth','ground-depth','signal-depth','plane-core','ground-core','signal-core','dc','bad-frequency'])
def test_every_material_or_mapping_refusal_precedes_fields(monkeypatch,kind):
    section=guard();signals,reference=metals();thickness=35e-6;frequency=F
    if kind=='section':section=None
    if kind=='signals-missing':signals.pop('a')
    if kind=='signals-extra':signals['extra']=SurfaceMetal(58e6)
    if kind=='signal-type':signals['a']=TraceFaceMetals.uniform(SurfaceMetal(58e6))
    if kind=='reference-type':reference=SurfaceMetal(58e6)
    if kind=='ground-missing':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{})
    if kind=='ground-extra':reference=ReferenceSurfaceMetals(reference.bottom,None,None,dict(reference.conductors,extra=SurfaceMetal(58e6)))
    if kind=='ground-faces':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{'guard':TraceFaceMetals.uniform(SurfaceMetal(58e6))})
    if kind=='bottom-missing':reference=ReferenceSurfaceMetals(None,None,None,reference.conductors)
    if kind=='top-metal':reference=ReferenceSurfaceMetals(reference.bottom,SurfaceMetal(58e6),None,reference.conductors)
    if kind=='side-metal':reference=ReferenceSurfaceMetals(reference.bottom,None,SurfaceMetal(58e6),reference.conductors)
    if kind=='plane-depth':thickness=1e-7
    if kind=='ground-depth':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{'guard':SurfaceMetal(1e4)})
    if kind=='signal-depth':signals['a']=SurfaceMetal(1e4)
    core=LayeredSurfaceMetal(58e6,coatings=(MetalLayer(30e-6,40e6),))
    if kind=='plane-core':reference=ReferenceSurfaceMetals(core,None,None,reference.conductors)
    if kind=='ground-core':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{'guard':core})
    if kind=='signal-core':signals['a']=core
    if kind=='dc':frequency=[0.,1e9]
    if kind=='bad-frequency':frequency=[1e9,1e9]
    monkeypatch.setattr(module,'panel_shape_current_factors',lambda *a,**k:pytest.fail('invalid material invoked fields'))
    with pytest.raises((ValueError,TypeError)):
        solve(section,frequency,conductors=signals,reference=reference,ground_thickness=thickness)


@pytest.mark.parametrize('interrupt',[False,True])
def test_original_kernel_failure_or_interrupt_is_not_replaced(monkeypatch,interrupt):
    original=KeyboardInterrupt() if interrupt else PanelShapeCurrentError('original shared failure',samples=())
    def fail(*a,**k):raise original
    monkeypatch.setattr(module,'panel_shape_current_factors',fail)
    signals,reference=metals()
    with pytest.raises(type(original)) as caught:
        solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    assert caught.value is original


def test_plane_and_ground_trace_depth_gates_use_separate_dimensions(monkeypatch):
    _,calls=fake(monkeypatch);signals,_=metals()
    # The thick trace admits this metal, while a thin plane with the same
    # metal does not. A different high-conductivity plane remains admissible.
    delta=np.sqrt(1/(np.pi*1e9*mu_0*3e6))
    assert 15e-6/5 < delta < 50e-6/5
    reference=ReferenceSurfaceMetals(SurfaceMetal(58e6),None,None,{'guard':SurfaceMetal(3e6)})
    solve(guard(),[1e9],conductors=signals,reference=reference,ground_thickness=15e-6)
    assert len(calls)==1
    reference=ReferenceSurfaceMetals(SurfaceMetal(3e6),None,None,{'guard':SurfaceMetal(58e6)})
    with pytest.raises(ValueError,match='reference:bottom'):
        solve(guard(),[1e9],conductors=signals,reference=reference,ground_thickness=15e-6)
    assert len(calls)==1


@pytest.mark.parametrize('ground_count',[0,1,2])
def test_zero_or_multiple_ground_traces_preserve_exact_grouping(monkeypatch,ground_count):
    from sipi import CrossSection,Layer,Trace
    traces=[Trace('a',-.0005,.0003,.001,50e-6),Trace('b',.0005,.0004,.001,60e-6)]
    for i in range(ground_count):traces.insert(1+i,Trace('g'+str(i),i*.0002,.0001,.001,50e-6,ground=True))
    section=CrossSection([Layer('u',.01105,1.)],traces,.02)
    indices=[i for i,t in enumerate(traces) if not t.ground];grounds=[i for i,t in enumerate(traces) if t.ground]
    pieces=np.array([np.array([[2.,.1],[.1,3.]])*(i+1) for i in range(len(traces)+1)])
    grouped=np.concatenate((pieces[indices],pieces[grounds+[len(traces)]].sum(axis=0,keepdims=True)))
    factors=PanelShapeCurrentFactors(('a','b'),grouped,np.array([[1.,0.],[0.,1.],[-1.,-1.]]),
        np.eye(2)*1e-11,tuple(t.name for t in traces if t.ground),{'transport_stub':1.},(),1e-8,
        np.array([grouped,grouped]),np.array([pieces,pieces]))
    monkeypatch.setattr(module,'panel_shape_current_factors',lambda *a,**k:factors)
    ref=ReferenceSurfaceMetals(SurfaceMetal(45e6),None,None,{t.name:SurfaceMetal(20e6) for t in traces if t.ground})
    signals,_=metals();result=solve(section,F,conductors=signals,reference=ref,ground_thickness=35e-6)
    assert len(result.boundary_labels)==3+ground_count
    np.testing.assert_array_equal(result.boundary_parts,pieces[indices+[len(traces)]+grounds])
    np.testing.assert_array_equal(np.concatenate((result.boundary_parts[3:],result.boundary_parts[2:3])).sum(axis=0),factors.parts[-1])


@pytest.mark.parametrize('location',['signal','bottom','guard'])
def test_explicit_rms_law_keeps_reactance_and_uses_each_metal_skin_depth(monkeypatch,location):
    fake(monkeypatch);signals,reference=metals();index={'signal':0,'bottom':2,'guard':3}[location]
    base=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    sigma=base.metals[index].conductivity;rms=.5e-6;rough=SurfaceMetal(sigma,roughness_rms=rms)
    if location=='signal':signals['a']=rough
    if location=='bottom':reference=ReferenceSurfaceMetals(rough,None,None,reference.conductors)
    if location=='guard':reference=ReferenceSurfaceMetals(reference.bottom,None,None,{'guard':rough})
    result=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    delta=np.sqrt(1/(np.pi*F*mu_0*sigma));factor=1+2/np.pi*np.arctan(1.4*(rms/delta)**2)
    np.testing.assert_allclose(result.surface_impedance[:,index].real,base.surface_impedance[:,index].real*factor,rtol=1e-12,atol=0)
    np.testing.assert_array_equal(result.surface_impedance.imag,base.surface_impedance.imag)
    np.testing.assert_array_equal(result.L_internal,base.L_internal)


def test_empty_coatings_preserve_bulk_transfer(monkeypatch):
    fake(monkeypatch);signals,reference=metals();base=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    signals={n:LayeredSurfaceMetal(m.conductivity,coatings=()) for n,m in signals.items()}
    reference=ReferenceSurfaceMetals(LayeredSurfaceMetal(45e6,coatings=()),None,None,{'guard':LayeredSurfaceMetal(20e6,coatings=())})
    result=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6)
    np.testing.assert_allclose(result.R,base.R,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.L_internal,base.L_internal,rtol=1e-12,atol=0)
