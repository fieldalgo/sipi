# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit linear-density physical face, material and resource contracts."""
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
import sipi.two_ground_linear_corner_conductor as module
from galerkin.laplace_corner_linear_field import solve_two_ground_linear_corner_rectangle_edges

F = np.array([1e9, 3e9, 10e9])
ROWS = json.loads((Path(__file__).parent/'data/two_ground/corner_registered.json').read_text())


def section(index=1, dielectric=4.):
    traces = [Trace(**row) for row in ROWS[index]['traces']]
    return CrossSection([Layer('uniform', .002, dielectric)], traces, .008, top='ground')


def reference():
    return ReferenceSurfaceMetals(SurfaceMetal(45e6), SurfaceMetal(45e6), None, {})


def conductors(index=1, uniform=False):
    rows = [[58e6,35e6,21e6,45e6],[45e6,21e6,35e6,58e6]]
    return {t.name:TraceFaceMetals(*[SurfaceMetal(s) for s in ([rows[i][0]]*4 if uniform else rows[i])])
            for i,t in enumerate(section(index).traces)}


@pytest.fixture(scope='module')
def shared():
    s = section()
    return solve_two_ground_linear_corner_rectangle_edges([t.corners()+[s.width/2,0.] for t in s.traces],
        width=s.width, height=s.height, panels_per_edge=32)


@pytest.fixture
def reused(monkeypatch, shared):
    calls = []
    def solver(*args, **kwargs):
        calls.append((args,kwargs))
        return shared
    monkeypatch.setattr(module, '_solver', lambda:solver)
    return calls


def test_one_shared_solve_and_exact_all_active_basis(reused, shared):
    factors=module.two_ground_linear_corner_face_current_factors(section())
    assert len(reused)==1
    assert np.array_equal(factors.base.boundary_parts,shared.whole.current_gram)
    assert np.array_equal(factors.base.boundary_integrals,shared.whole.current_integrals)
    assert np.array_equal(factors.C0,epsilon_0*shared.whole.capacitance_per_permittivity)
    assert np.array_equal(factors.parts[:8],shared.edge_current_gram[[0,2,3,1,4,6,7,5]])
    assert factors.names==('left','right') and factors.base.ground_trace_names==()
    assert factors.reference_labels==('reference:bottom','reference:top')
    assert factors.base.diagnostics['method']=='two-ground-linear-corner-power-all-active'
    for value in (factors.parts,factors.current_integrals,factors.C0,factors.base.boundary_parts):
        with pytest.raises(ValueError):value.flags.writeable=True
    with pytest.raises(TypeError):factors.base.diagnostics['method']='other'


def test_uniform_faces_preserve_whole_surface_law(reused):
    metals=conductors(uniform=True)
    whole=module.two_ground_linear_corner_conductor_loss(section(),F,
        conductors={k:v.bottom for k,v in metals.items()},reference=reference(),ground_thickness=35e-6)
    faces=module.two_ground_linear_corner_conductor_loss_by_face(section(),F,
        conductors=metals,reference=reference(),ground_thickness=35e-6)
    for name in ('R','L_internal'):np.testing.assert_allclose(getattr(whole,name),getattr(faces,name),rtol=1e-10,atol=0)
    assert np.array_equal(whole.factors.C0,faces.factors.C0)
    assert np.array_equal(whole.factors.boundary_parts,faces.factors.base.boundary_parts)
    assert len(reused)==2


def test_surface_formula_passivity_and_matched_network(reused):
    result=module.two_ground_linear_corner_conductor_loss_by_face(section(),F,
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
    original=module.two_ground_linear_corner_conductor_loss_by_face(section(),F,conductors=metals,**kwargs)
    changed=SurfaceMetal(58e6,roughness=CausalHuray((.2e-6,),(2.,))) if kind=='roughness' else LayeredSurfaceMetal(58e6,coatings=(MetalLayer(2e-7,14e6,3.),))
    altered=dict(metals);altered['left']=dataclasses.replace(metals['left'],top=changed)
    result=module.two_ground_linear_corner_conductor_loss_by_face(section(),F,conductors=altered,**kwargs)
    dz=changed._samples(F)[3]-metals['left'].top._samples(F)[3]
    expected=dz[:,None,None]*original.factors.parts[1]
    np.testing.assert_allclose(result.R-original.R,expected.real,rtol=1e-10,atol=0)
    np.testing.assert_allclose((result.L_internal-original.L_internal)*2*np.pi*F[:,None,None],expected.imag,rtol=1e-10,atol=0)


def test_vacuum_current_extraction_ignores_dielectric_metadata(reused):
    a=module.two_ground_linear_corner_current_factors(section(dielectric=4.))
    b=module.two_ground_linear_corner_current_factors(section(dielectric=9.))
    assert np.array_equal(a.parts,b.parts) and np.array_equal(a.C0,b.C0)


@pytest.mark.parametrize('kind',['guard','third','polygon','open-top','ground-sides'])
def test_unsupported_section_refused_before_shared_lookup(monkeypatch,kind):
    s=section();traces=list(s.traces);top='ground';sides='open'
    if kind=='guard':traces[1]=dataclasses.replace(traces[1],ground=True)
    if kind=='third':traces.append(Trace('extra',x=0.,y=.00155,width=.00015,thickness=.00004))
    if kind=='polygon':traces[0]=PolygonTrace(traces[0].name,traces[0].corners())
    if kind=='open-top':top='open'
    if kind=='ground-sides':sides='ground'
    bad=CrossSection(s.layers,traces,s.width,top=top,sides=sides)
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('shared lookup before admission'))
    with pytest.raises(ValueError):module.two_ground_linear_corner_face_current_factors(bad)


@pytest.mark.parametrize('options',[dict(panels_per_edge=17),dict(panels_per_edge=514),dict(ground_modes=65),dict(ground_modes=True),dict(interpolation_degree=16),dict(interpolation_degree=24.)])
def test_invalid_resolution_before_field(monkeypatch,options):
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('field before admission'))
    with pytest.raises(ValueError):module.two_ground_linear_corner_face_current_factors(section(),**options)


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
        module.two_ground_linear_corner_conductor_loss_by_face(section(),f,conductors=metals,reference=ref,ground_thickness=thickness)


@pytest.mark.parametrize('stub',[SimpleNamespace(),SimpleNamespace(solve_two_ground_linear_corner_rectangle_edges=lambda polygons:None)])
def test_missing_or_wrong_shared_capability_has_no_fallback(monkeypatch,stub):
    monkeypatch.setattr(module,'import_module',lambda name:stub)
    with pytest.raises(RuntimeError):module.two_ground_linear_corner_face_current_factors(section())


@pytest.mark.parametrize('kind',['owner','endpoint'])
def test_shared_edges_must_match_physical_faces(monkeypatch,shared,kind):
    if kind=='owner':bad=dataclasses.replace(shared,edge_owners=np.zeros(8,dtype=int))
    else:bad=dataclasses.replace(shared,edge_starts=shared.edge_starts+.001)
    monkeypatch.setattr(module,'_solver',lambda:lambda *a,**k:bad)
    with pytest.raises(ValueError,match='edge'):module.two_ground_linear_corner_face_current_factors(section())


@pytest.mark.parametrize('index,count',[(0,136),(1,72),(1,128)])
def test_physical_panel_budget_fails_before_shared_lookup(monkeypatch,index,count):
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('lookup before resource admission'))
    with pytest.raises(ValueError,match='512 physical panels'):
        module.two_ground_linear_corner_face_current_factors(section(index),panels_per_edge=count)


@pytest.mark.parametrize('index,count',[(0,134),(1,70)])
def test_exact_512_panel_boundary_reaches_shared_capability(monkeypatch,index,count):
    class ReachedShared(Exception):pass
    def reached():raise ReachedShared
    monkeypatch.setattr(module,'_solver',reached)
    with pytest.raises(ReachedShared):
        module.two_ground_linear_corner_face_current_factors(section(index),panels_per_edge=count)


def test_default_controls_are_explicit_and_do_not_select_old_solver(reused):
    result=module.two_ground_linear_corner_face_current_factors(section())
    assert reused[0][1]['panels_per_edge']==32
    assert reused[0][1]['ground_modes']==256
    assert reused[0][1]['interpolation_degree']==24
    assert result.base.diagnostics['panel_count']==208


@pytest.mark.parametrize('index',[0,1])
def test_real_physical_faces_and_whole_currents_refine_without_floor(index,shared):
    s=section(index)
    coarse=module.two_ground_linear_corner_face_current_factors(s,panels_per_edge=32)
    fine=module.two_ground_linear_corner_face_current_factors(s,panels_per_edge=64)
    assert fine.base.diagnostics['panel_count']==4*len(s.traces)*(64-6)
    for a,b in [(coarse.C0,fine.C0),(coarse.parts,fine.parts),
                (coarse.base.parts,fine.base.parts)]:
        delta=abs(a-b);scale=np.maximum(abs(a),abs(b))
        relative=np.divide(delta,scale,out=np.where(delta==0,0.,np.inf),where=scale!=0)
        assert np.max(relative)<=.01
    if index==1:
        assert np.array_equal(coarse.base.boundary_parts,shared.whole.current_gram)


def test_bad_shared_conservation_is_not_silently_projected(monkeypatch,shared):
    integrals=shared.whole.current_integrals.copy();integrals[0,0]+=.001
    bad=dataclasses.replace(shared,whole=dataclasses.replace(shared.whole,current_integrals=integrals))
    monkeypatch.setattr(module,'_solver',lambda:lambda *a,**k:bad)
    with pytest.raises(ValueError,match='conservation'):
        module.two_ground_linear_corner_face_current_factors(section())
