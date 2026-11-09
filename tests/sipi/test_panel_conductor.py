# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import numpy as np
import pytest
import sipi.panel_conductor as candidate
from sipi.panel_conductor import panel_surface_current_factors
from sipi import CrossSection, Layer, Trace, PolygonTrace


def circles(scale=1., permittivity=1., reverse=False):
    theta=np.arange(64)*2*np.pi/64
    traces=[]
    for name,x,r,ground in [('left',-.4,.08,False),('guard',0.,.1,True),('right',.4,.1,False)]:
        p=scale*(np.column_stack((x+r*np.cos(theta),.5+r*np.sin(theta))))
        traces.append(PolygonTrace(name,p,ground=ground))
    if reverse:traces.reverse()
    return CrossSection([Layer('uniform',2.*scale,permittivity)],traces,4.*scale)


def test_grounded_geometry_current_energy_and_metadata_independence():
    a=panel_surface_current_factors(circles(),panels_per_edge=2,interpolation_degree=12)
    b=panel_surface_current_factors(circles(permittivity=4.),panels_per_edge=2,interpolation_degree=12)
    assert a.names==('left','right') and a.ground_trace_names==('guard',)
    np.testing.assert_array_equal(a.C0,b.C0)
    np.testing.assert_array_equal(a.parts,b.parts)
    np.testing.assert_allclose(a.current_integrals,[[1,0],[0,1],[-1,-1]],atol=1e-10,rtol=0)
    assert a.diagnostics['ground_voltage_error']<=1e-10
    np.linalg.cholesky(a.C0)
    for part in a.parts:assert np.linalg.eigvalsh(part).min()>=-1e-12*abs(part).max()
    with pytest.raises(TypeError):a.diagnostics['panel_count']=0


@pytest.mark.parametrize('scale',[.001,1000.])
def test_scale_and_permutation(scale):
    a=panel_surface_current_factors(circles(),panels_per_edge=2,interpolation_degree=12)
    b=panel_surface_current_factors(circles(scale=scale,reverse=True),panels_per_edge=2,interpolation_degree=12)
    assert b.names==a.names[::-1]
    np.testing.assert_allclose(a.C0,b.C0[::-1,::-1],rtol=1e-10,atol=1e-25)
    np.testing.assert_allclose(a.parts,b.parts[[1,0,2],::-1,::-1]*scale,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('kind',['wrong','bottom','top','sides','zero'])
def test_refusals_before_shared_solve(monkeypatch,kind):
    def forbidden(*a,**k):raise AssertionError('invalid section reached shared solve')
    monkeypatch.setattr(candidate,'_panel_solver',forbidden)
    if kind=='wrong':section=None
    else:
        args=dict(bottom='ground',top='open',sides='open');args.update({kind:'open' if kind=='bottom' else 'ground'} if kind!='zero' else {})
        traces=list(circles().traces)
        if kind=='zero':traces=[Trace('signal',0,.5,.2)]
        section=CrossSection([Layer('u',2.,1.)],traces,4.,**args)
    with pytest.raises((ValueError,TypeError)):panel_surface_current_factors(section,panels_per_edge=2,interpolation_degree=12)


def test_qualified_panel_sequence_248_of_grounded_guard():
    rows=[panel_surface_current_factors(circles(),panels_per_edge=n,interpolation_degree=12) for n in [2,4,8]]
    def rel(a,b):return float(abs(a-b).max()/abs(b).max())
    changes=np.array([[rel(a.C0,b.C0)]+[rel(x,y) for x,y in zip(a.parts,b.parts)] for a,b in zip(rows,rows[1:])])
    assert np.all(changes[-1]<changes[0])
    assert changes[-1,0]<=.001 and np.all(changes[-1,1:]<=.005)


def test_default_retains_original_fixed_geometry_refusal():
    with pytest.raises(ValueError,match="quadrature/interpolation"):
        panel_surface_current_factors(circles(),panels_per_edge=2)

import types
from sipi.panel_conductor import panel_conductor_loss_by_boundary, PanelCurrentFactors
from sipi.conductor import SurfaceCurrentFactors
from sipi.boundary_conductor import SurfaceMetal
from sipi.constants import mu_0, epsilon_0
from sipi.roughness import CausalHuray, CannonballHuray, GroissRMS

F=np.array([4e9,16e9])

@pytest.fixture(scope='module')
def smooth():
    metals={'left':SurfaceMetal(58e6),'right':SurfaceMetal(35e6,relative_permeability=1.4)}
    reference=SurfaceMetal(45e6)
    return panel_conductor_loss_by_boundary(circles(scale=.001),F,conductors=metals,
        reference=reference,ground_thickness=35e-6,panels_per_edge=2,interpolation_degree=12)


def test_subclass_retains_diagnostics_and_immutable_arrays(smooth):
    factors=smooth.factors
    assert isinstance(factors,(PanelCurrentFactors,SurfaceCurrentFactors))
    assert factors.ground_trace_names==('guard',)
    assert factors.diagnostics['ground_voltage_error']<=1e-10
    for x in (factors.C0,factors.parts,factors.current_integrals):
        with pytest.raises(ValueError):x.setflags(write=True)


def test_distinct_smooth_metals_independent_law_and_frequency_scaling(smooth):
    # Direct half-space law, scalar loops, no product surface-impedance helper.
    expected=np.zeros_like(smooth.R)
    for k,f in enumerate(F):
        for b,metal in enumerate(smooth.metals):
            expected[k]+=np.sqrt(np.pi*f*mu_0*metal.relative_permeability/metal.conductivity)*smooth.factors.parts[b]
    np.testing.assert_allclose(smooth.R,expected,rtol=1e-12)
    np.testing.assert_allclose(smooth.L_internal*2*np.pi*F[:,None,None],expected,rtol=1e-12)
    np.testing.assert_allclose(smooth.R[1],2*smooth.R[0],rtol=1e-12)
    np.testing.assert_allclose(smooth.resistance_parts.sum(axis=1),smooth.R,rtol=1e-12)
    for matrix in (smooth.R,smooth.L_internal):
        assert np.linalg.eigvalsh(matrix).min()>0
    np.testing.assert_allclose(smooth.factors.C0@smooth.factors.L_external,epsilon_0*mu_0*np.eye(2),atol=1e-28,rtol=1e-10)


def test_reciprocal_passive_network_with_panel_external_inductance(smooth):
    net=smooth.network(C=3*smooth.factors.C0,G=np.zeros((2,2)),length=.02)
    np.testing.assert_allclose(net.s,net.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(net.s,compute_uv=False).max()<=1+1e-10


@pytest.mark.parametrize('roughness',[None,GroissRMS(.8e-6),CausalHuray([.2e-6],[2.]),CannonballHuray(2e-6),'hammerstad'])
def test_existing_roughness_laws_are_reused(smooth,monkeypatch,roughness):
    metal=SurfaceMetal(58e6,roughness_rms=.8e-6) if roughness=='hammerstad' else SurfaceMetal(58e6,roughness=roughness)
    monkeypatch.setattr(candidate,'panel_surface_current_factors',lambda *a,**k:smooth.factors)
    got=panel_conductor_loss_by_boundary(circles(scale=.001),F,conductors={'left':metal,'right':metal},reference=metal,ground_thickness=35e-6)
    zs=metal._samples(F)[3]
    np.testing.assert_allclose(got.R,zs.real[:,None,None]*smooth.factors.total,rtol=1e-12)
    np.testing.assert_allclose(got.L_internal,(zs.imag/(2*np.pi*F))[:,None,None]*smooth.factors.total,rtol=1e-12)


@pytest.mark.parametrize('case',['missing','extra','wrong','reference','depth','dc','type'])
def test_invalid_inputs_precede_field_solve(monkeypatch,case):
    def forbidden(*a,**k):raise AssertionError('invalid input reached field solve')
    monkeypatch.setattr(candidate,'panel_surface_current_factors',forbidden)
    metal=SurfaceMetal(58e6);metals={'left':metal,'right':metal};ref=metal;thickness=35e-6;f=F;section=circles(scale=.001)
    if case=='missing':metals.pop('left')
    if case=='extra':metals['guard']=metal
    if case=='wrong':metals['left']=None
    if case=='reference':ref=None
    if case=='depth':thickness=1e-9
    if case=='dc':f=[0]
    if case=='type':section=None
    with pytest.raises((ValueError,TypeError)):
        panel_conductor_loss_by_boundary(section,f,conductors=metals,reference=ref,ground_thickness=thickness)


@pytest.mark.parametrize('missing',['module','function','degree'])
def test_missing_shared_capability_is_an_explicit_lazy_error(monkeypatch,missing):
    def load(name):
        if missing=='module':raise ImportError('unavailable')
        if missing=='function':return types.SimpleNamespace()
        return types.SimpleNamespace(solve_grounded_rectangle=lambda polygons, width,height:None)
    monkeypatch.setattr(candidate,'import_module',load)
    with pytest.raises(RuntimeError,match='shared'):
        candidate.panel_surface_current_factors(circles(),panels_per_edge=2,interpolation_degree=12)


def test_original_one_ghz_fixture_remains_rejected_before_solve(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('skin-depth refusal reached solve')
    monkeypatch.setattr(candidate,'panel_surface_current_factors',forbidden)
    with pytest.raises(ValueError,match='signal left:.*skin depth'):
        panel_conductor_loss_by_boundary(circles(scale=.001),[1e9,4e9],
            conductors={'left':SurfaceMetal(58e6),'right':SurfaceMetal(35e6,relative_permeability=1.4)},
            reference=SurfaceMetal(45e6),ground_thickness=35e-6,
            panels_per_edge=2,interpolation_degree=12)
