# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit harmonic-density physical face, material and resource contracts."""
import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection, Layer, Trace, PolygonTrace
from sipi.constants import mu_0, epsilon_0
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.layered_metal import MetalLayer
from sipi.roughness import CausalHuray
import sipi.two_ground_harmonic_guard_corner_conductor as module
from galerkin.laplace_corner_harmonic_guard_field import solve_two_ground_harmonic_corner_guard_edges

F = np.array([1e9, 3e9, 10e9])
TRACES = [{'name': 'left', 'x': -0.0004, 'y': 0.0006, 'width': 0.00035, 'thickness': 5e-05, 'top_width': 0.0003}, {'name': 'right', 'x': 0.00045, 'y': 0.0011, 'width': 0.0004, 'thickness': 6e-05, 'top_width': 0.00045}, {'name': 'center', 'x': 0.0, 'y': 0.00155, 'width': 0.0002, 'thickness': 4e-05, 'top_width': 0.00018}]


def section(index=0, dielectric=4.):
    return CrossSection([Layer('uniform',.002,dielectric)], [Trace(**row,ground=(i==2)) for i,row in enumerate(TRACES)],.008,top='ground')


def reference():
    return ReferenceSurfaceMetals(SurfaceMetal(45e6), SurfaceMetal(45e6), None, {'center':SurfaceMetal(17e6)})


def conductors(index=1, uniform=False):
    rows = [[58e6,35e6,21e6,45e6],[45e6,21e6,35e6,58e6],[17e6,21e6,35e6,45e6]]
    return {t.name:TraceFaceMetals(*[SurfaceMetal(s) for s in ([rows[i][0]]*4 if uniform else rows[i])])
            for i,t in enumerate(section(index).traces) if not t.ground}


@pytest.fixture(scope='module')
def shared():
    s = section()
    return solve_two_ground_harmonic_corner_guard_edges([t.corners()+[s.width/2,0.] for t in s.traces],
        signals=(0,1), width=s.width, height=s.height, panels_per_edge=32)


@pytest.fixture
def reused(monkeypatch, shared):
    calls = []
    def solver(*args, **kwargs):
        calls.append((args,kwargs))
        return shared
    monkeypatch.setattr(module, '_solver', lambda:solver)
    return calls


def test_one_shared_solve_and_exact_fixed_guard_basis(reused, shared):
    factors=module.two_ground_harmonic_guard_corner_face_current_factors(section())
    assert len(reused)==1
    assert np.array_equal(factors.base.boundary_parts,shared.whole.current_gram[[0,1,3,4,2]])
    assert np.array_equal(factors.base.boundary_integrals,shared.whole.current_integrals[[0,1,3,4,2]])
    assert np.array_equal(factors.C0,epsilon_0*shared.whole.capacitance_per_permittivity)
    assert np.array_equal(factors.parts[:8],shared.edge_current_gram[[0,2,3,1,4,6,7,5]])
    assert np.array_equal(factors.parts[10:],shared.edge_current_gram[[8,10,11,9]])
    assert np.array_equal(factors.parts[8:10],shared.whole.current_gram[3:])
    assert np.max(abs(factors.base.boundary_integrals[-1]))>1e-6
    assert reused[0][1]['signal_indices']==(0,1)
    assert factors.names==('left','right') and factors.base.ground_trace_names==('center',)
    assert factors.reference_labels==('reference:bottom','reference:top')+tuple('reference:ground:center:'+face for face in ('bottom','top','left','right'))
    assert factors.base.diagnostics['method']=='two-ground-harmonic-corner-fixed-guard'
    for value in (factors.parts,factors.current_integrals,factors.C0,factors.base.boundary_parts):
        with pytest.raises(ValueError):value.flags.writeable=True
    with pytest.raises(TypeError):factors.base.diagnostics['method']='other'


def test_uniform_faces_preserve_whole_surface_law(reused):
    metals=conductors(uniform=True)
    whole=module.two_ground_harmonic_guard_corner_conductor_loss(section(),F,
        conductors={k:v.bottom for k,v in metals.items()},reference=reference(),ground_thickness=35e-6)
    faces=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,
        conductors=metals,reference=reference(),ground_thickness=35e-6)
    for name in ('R','L_internal'):np.testing.assert_allclose(getattr(whole,name),getattr(faces,name),rtol=1e-10,atol=0)
    assert np.array_equal(whole.factors.C0,faces.factors.C0)
    assert np.array_equal(whole.factors.boundary_parts,faces.factors.base.boundary_parts)
    assert len(reused)==2


def test_surface_formula_passivity_and_matched_network(reused):
    result=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,
        conductors=conductors(),reference=reference(),ground_thickness=35e-6)
    expected=np.zeros_like(result.R)
    for i,metal in enumerate(result.metals):
        weights=np.sqrt(np.pi*F*mu_0*metal.relative_permeability/metal.conductivity)
        expected+=weights[:,None,None]*result.factors.parts[i]
    np.testing.assert_allclose(result.R,expected,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.L_internal*(2*np.pi*F[:,None,None]),expected,rtol=1e-12,atol=0)
    for currents in (np.array([1.,0.]),np.array([1.,-1.]),np.array([1.,1.]),np.array([1.+2.j,-.3j])):
        assert np.all(np.real(np.einsum('i,fij,j->f',currents.conj(),result.R,currents))>0)
    network=result.network(C=4*result.factors.C0,G=np.zeros((2,2)),length=.02)
    np.testing.assert_allclose(network.s,network.s.swapaxes(1,2),rtol=1e-10,atol=1e-12)
    assert np.max(np.linalg.svd(network.s,compute_uv=False))<=1+1e-10


@pytest.mark.parametrize('kind',['roughness','coating'])
def test_face_law_changes_only_selected_surface_contribution(reused,kind):
    metals=conductors();kwargs=dict(reference=reference(),ground_thickness=35e-6)
    original=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,conductors=metals,**kwargs)
    changed=SurfaceMetal(58e6,roughness=CausalHuray((.2e-6,),(2.,))) if kind=='roughness' else LayeredSurfaceMetal(58e6,coatings=(MetalLayer(2e-7,14e6,3.),))
    altered=dict(metals);altered['left']=dataclasses.replace(metals['left'],top=changed)
    result=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,conductors=altered,**kwargs)
    dz=changed._samples(F)[3]-metals['left'].top._samples(F)[3]
    expected=dz[:,None,None]*original.factors.parts[1]
    np.testing.assert_allclose(result.R-original.R,expected.real,rtol=1e-10,atol=0)
    np.testing.assert_allclose((result.L_internal-original.L_internal)*2*np.pi*F[:,None,None],expected.imag,rtol=1e-10,atol=0)


def test_vacuum_current_extraction_ignores_dielectric_metadata(reused):
    a=module.two_ground_harmonic_guard_corner_current_factors(section(dielectric=4.))
    b=module.two_ground_harmonic_guard_corner_current_factors(section(dielectric=9.))
    assert np.array_equal(a.parts,b.parts) and np.array_equal(a.C0,b.C0)


@pytest.mark.parametrize('kind',['guard','no-guard','two','polygon','open-top','ground-sides'])
def test_unsupported_section_refused_before_shared_lookup(monkeypatch,kind):
    s=section();traces=list(s.traces);top='ground';sides='open'
    if kind=='guard':traces[1]=dataclasses.replace(traces[1],ground=True)
    if kind=='no-guard':traces[2]=dataclasses.replace(traces[2],ground=False)
    if kind=='two':traces.pop()
    if kind=='polygon':traces[0]=PolygonTrace(traces[0].name,traces[0].corners())
    if kind=='open-top':top='open'
    if kind=='ground-sides':sides='ground'
    bad=CrossSection(s.layers,traces,s.width,top=top,sides=sides)
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('shared lookup before admission'))
    with pytest.raises(ValueError):module.two_ground_harmonic_guard_corner_face_current_factors(bad)


@pytest.mark.parametrize('options',[dict(panels_per_edge=8),dict(panels_per_edge=17),dict(panels_per_edge=514),dict(ground_modes=65),dict(ground_modes=True),dict(interpolation_degree=16),dict(interpolation_degree=24.)])
def test_invalid_resolution_before_field(monkeypatch,options):
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('field before admission'))
    with pytest.raises(ValueError):module.two_ground_harmonic_guard_corner_face_current_factors(section(),**options)


@pytest.mark.parametrize('kind',['frequency','missing-metal','extra-ground-law','skin-depth','foil-thickness','whole-metal-type'])
def test_material_failures_before_field(monkeypatch,kind):
    f=F;metals=conductors();ref=reference();thickness=35e-6
    if kind=='frequency':f=[0.]
    if kind=='missing-metal':metals.pop('left')
    if kind=='extra-ground-law':ref=ReferenceSurfaceMetals(ref.bottom,ref.top,None,{'guard':SurfaceMetal(45e6)})
    if kind=='skin-depth':f=[1e6]
    if kind=='foil-thickness':thickness=1e-7
    if kind=='whole-metal-type':metals['left']=SurfaceMetal(58e6)
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('field before material admission'))
    with pytest.raises((ValueError,TypeError)):
        module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),f,conductors=metals,reference=ref,ground_thickness=thickness)


@pytest.mark.parametrize('stub',[SimpleNamespace(),SimpleNamespace(solve_two_ground_harmonic_corner_guard_edges=lambda polygons:None)])
def test_missing_or_wrong_shared_capability_has_no_fallback(monkeypatch,stub):
    monkeypatch.setattr(module,'import_module',lambda name:stub)
    with pytest.raises(RuntimeError):module.two_ground_harmonic_guard_corner_face_current_factors(section())


@pytest.mark.parametrize('kind',['owner','endpoint'])
def test_shared_edges_must_match_physical_faces(monkeypatch,shared,kind):
    if kind=='owner':bad=dataclasses.replace(shared,edge_owners=np.zeros(12,dtype=int))
    else:bad=dataclasses.replace(shared,edge_starts=shared.edge_starts+.001)
    monkeypatch.setattr(module,'_solver',lambda:lambda *a,**k:bad)
    with pytest.raises(ValueError,match='edge'):module.two_ground_harmonic_guard_corner_face_current_factors(section())


@pytest.mark.parametrize('index,count',[(0,50),(0,64),(0,128)])
def test_physical_panel_budget_fails_before_shared_lookup(monkeypatch,index,count):
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('lookup before resource admission'))
    with pytest.raises(ValueError,match='512 physical panels'):
        module.two_ground_harmonic_guard_corner_face_current_factors(section(index),panels_per_edge=count)


@pytest.mark.parametrize('index,count',[(0,48)])
def test_exact_512_panel_boundary_reaches_shared_capability(monkeypatch,index,count):
    class ReachedShared(Exception):pass
    def reached():raise ReachedShared
    monkeypatch.setattr(module,'_solver',reached)
    with pytest.raises(ReachedShared):
        module.two_ground_harmonic_guard_corner_face_current_factors(section(index),panels_per_edge=count)


def test_default_controls_are_explicit_and_do_not_select_old_solver(reused):
    result=module.two_ground_harmonic_guard_corner_face_current_factors(section())
    assert reused[0][1]['panels_per_edge']==32
    assert reused[0][1]['ground_modes']==256
    assert reused[0][1]['interpolation_degree']==24
    assert result.base.diagnostics['panel_count']==312


@pytest.mark.parametrize('index',[0])
def test_real_physical_faces_and_whole_currents_refine_without_floor(index,shared):
    s=section(index)
    coarse=module.two_ground_harmonic_guard_corner_face_current_factors(s,panels_per_edge=32)
    fine=module.two_ground_harmonic_guard_corner_face_current_factors(s,panels_per_edge=48)
    assert fine.base.diagnostics['panel_count']==4*len(s.traces)*(48-6)
    for a,b in [(coarse.C0,fine.C0),(coarse.parts,fine.parts),
                (coarse.base.parts,fine.base.parts)]:
        delta=abs(a-b);scale=np.maximum(abs(a),abs(b))
        relative=np.divide(delta,scale,out=np.where(delta==0,0.,np.inf),where=scale!=0)
        assert np.max(relative)<=.01
    assert np.array_equal(coarse.base.boundary_parts,shared.whole.current_gram[[0,1,3,4,2]])


def test_bad_shared_conservation_is_not_silently_projected(monkeypatch,shared):
    integrals=shared.whole.current_integrals.copy();integrals[0,0]+=.001
    bad=dataclasses.replace(shared,whole=dataclasses.replace(shared.whole,current_integrals=integrals))
    monkeypatch.setattr(module,'_solver',lambda:lambda *a,**k:bad)
    with pytest.raises(ValueError,match='conservation'):
        module.two_ground_harmonic_guard_corner_face_current_factors(section())


@pytest.mark.parametrize('kind',['roughness','coating'])
def test_distinct_guard_face_law_retains_induced_cross_terms(reused,kind):
    ref=reference();base=TraceFaceMetals.uniform(ref.conductors['center'])
    original=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,
        conductors=conductors(),reference=ref,ground_thickness=35e-6)
    changed=(SurfaceMetal(17e6,roughness=CausalHuray((.2e-6,),(2.,))) if kind=='roughness'
        else LayeredSurfaceMetal(17e6,coatings=(MetalLayer(2e-7,14e6,3.),)))
    altered=ReferenceSurfaceMetals(ref.bottom,ref.top,None,{'center':dataclasses.replace(base,right=changed)})
    result=module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,
        conductors=conductors(),reference=altered,ground_thickness=35e-6)
    index=result.boundary_labels.index('reference:ground:center:right')
    assert index==13 and abs(result.factors.parts[index,0,1])>0
    dz=changed._samples(F)[3]-base.right._samples(F)[3]
    expected=dz[:,None,None]*original.factors.parts[index]
    np.testing.assert_allclose(result.R-original.R,expected.real,rtol=1e-10,atol=0)
    np.testing.assert_allclose((result.L_internal-original.L_internal)*2*np.pi*F[:,None,None],expected.imag,rtol=1e-10,atol=0)
    assert np.array_equal(result.factors.parts,original.factors.parts)


@pytest.mark.parametrize('permutation',[(2,0,1),(0,2,1),(1,0,2),(2,1,0),(1,2,0)])
def test_geometry_order_and_active_order_are_distinct(monkeypatch,shared,permutation):
    original=section();traces=[original.traces[i] for i in permutation]
    changed=CrossSection(original.layers,traces,original.width,top='ground')
    basis=[i for i in permutation if i!=2]
    matrix=lambda a:np.take(np.take(a,basis,axis=-2),basis,axis=-1)
    rows=list(permutation)+[3,4]
    whole=dataclasses.replace(shared.whole,capacitance_per_permittivity=matrix(shared.whole.capacitance_per_permittivity),
        current_gram=matrix(shared.whole.current_gram[rows]),
        current_integrals=shared.whole.current_integrals[rows][:,basis])
    edge_rows=[4*i+j for i in permutation for j in range(4)]
    remap={old:new for new,old in enumerate(permutation)}
    reordered=dataclasses.replace(shared,whole=whole,
        edge_owners=np.array([remap[int(i)] for i in shared.edge_owners[edge_rows]]),
        edge_starts=shared.edge_starts[edge_rows],edge_ends=shared.edge_ends[edge_rows],
        edge_current_gram=matrix(shared.edge_current_gram[edge_rows]),
        edge_current_integrals=shared.edge_current_integrals[edge_rows][:,basis])
    calls=[]
    def solver(*args,**kwargs):calls.append(kwargs);return reordered
    monkeypatch.setattr(module,'_solver',lambda:solver)
    result=module.two_ground_harmonic_guard_corner_face_current_factors(changed)
    assert calls[0]['signal_indices']==tuple(i for i,t in enumerate(traces) if not t.ground)
    assert result.names==tuple(original.traces[i].name for i in basis)
    assert result.base.ground_trace_names==('center',)
    assert np.array_equal(result.C0,epsilon_0*matrix(shared.whole.capacitance_per_permittivity))
    for i,old in enumerate(basis):
        assert np.array_equal(result.parts[4*i:4*i+4],matrix(shared.edge_current_gram[[4*old+j for j in (0,2,3,1)]]))
    assert np.array_equal(result.parts[10:],matrix(shared.edge_current_gram[[8,10,11,9]]))


def test_missing_guard_law_refused_before_fields(monkeypatch):
    ref=reference();bad=ReferenceSurfaceMetals(ref.bottom,ref.top,None,{})
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('field before guard material admission'))
    with pytest.raises(ValueError,match='ground trace'):
        module.two_ground_harmonic_guard_corner_conductor_loss_by_face(section(),F,
            conductors=conductors(),reference=bad,ground_thickness=35e-6)
