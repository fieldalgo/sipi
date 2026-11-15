# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection, Layer, Trace, PolygonTrace
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.layered_metal import MetalLayer
from sipi.face_conductor import ReferenceSurfaceMetals, TraceFaceMetals
from sipi.constants import mu_0
import sipi.two_ground_conductor as candidate
from sipi.two_ground_conductor import two_ground_current_factors, two_ground_conductor_loss

ROWS=json.loads((Path(__file__).parent/"data/two_ground/registered.json").read_text())
F=np.array([2e9,5e9])


def section(row,eps=4.):
    traces=[PolygonTrace("positive" if i==0 else "negative",np.array(p)-[row["width"]/2,0.])
            for i,p in enumerate(row["polygons"])]
    return CrossSection([Layer("uniform",row["height"],eps)],traces,row["width"],top="ground")


def metals(names, distinct=False):
    positive=LayeredSurfaceMetal(58e6,coatings=(MetalLayer(2e-7,14e6,3.),MetalLayer(1e-6,40e6)))
    conductors={name:positive if name=="positive" else SurfaceMetal(35e6) for name in names}
    reference=ReferenceSurfaceMetals(SurfaceMetal(58e6),SurfaceMetal(21e6 if distinct else 58e6),None,{})
    return conductors,reference


@pytest.mark.parametrize("row",ROWS,ids=[r["case"] for r in ROWS])
def test_actual_registered_material_and_current_agreement(row,record_property):
    sec=section(row);conductors,reference=metals([t.name for t in sec.traces])
    loss=two_ground_conductor_loss(sec,F,conductors=conductors,reference=reference,
        ground_thickness=35e-6,panels_per_edge=256,interpolation_degree=row["degree"])
    observation={"C0":loss.factors.C0,"Q":loss.factors.parts,"R":loss.R,"L_internal":loss.L_internal}
    np.testing.assert_array_equal(observation["C0"],row["panel"]["C0"])
    for key in ("Q","R","L_internal"):
        np.testing.assert_allclose(observation[key],row["panel"][key],rtol=1e-10,atol=0)
    for key in observation:
        expected=np.asarray(row["reference"][key])
        if key=="Q" and expected.ndim==4:expected=expected[0]
        np.testing.assert_allclose(observation[key],expected,rtol=5e-4 if key=="C0" else .01,atol=0)
    np.testing.assert_allclose(loss.resistance_parts.sum(axis=1),loss.R,rtol=1e-12,atol=0)
    record_property("two_ground_material",json.dumps({k:np.asarray(v).tolist() for k,v in observation.items()},sort_keys=True))


def guarded(reverse=False,scale=1.,eps=1.):
    traces=[Trace("left",-.0004,.0007,.0003,.00005),
            Trace("guard",0.,.001,.0002,.00005,ground=True),
            Trace("right",.0004,.0009,.0003,.00005)]
    if reverse:traces=traces[::-1]
    traces=[Trace(t.name,t.x*scale,t.y*scale,t.width*scale,t.thickness*scale,ground=t.ground) for t in traces]
    return CrossSection([Layer("uniform",.002*scale,eps)],traces,.008*scale,top="ground")


@pytest.fixture(scope="module")
def guards():
    return two_ground_current_factors(guarded(),panels_per_edge=16,interpolation_degree=14)


def test_ground_trace_is_fixed_potential_and_preserves_surface_partition(guards):
    assert guards.names==("left","right") and guards.ground_trace_names==("guard",)
    assert guards.boundary_labels==("signal:left","signal:right","reference:bottom","reference:top","reference:ground:guard")
    assert guards.diagnostics["ground_voltage_error"]<=1e-10
    np.testing.assert_allclose(guards.current_integrals,[[1,0],[0,1],[-1,-1]],rtol=0,atol=1e-10)
    np.testing.assert_array_equal(guards.parts[-1],guards.boundary_parts[2:].sum(axis=0))
    assert not np.allclose(guards.boundary_integrals[2],guards.boundary_integrals[3])
    for a in (guards.parts,guards.C0,guards.boundary_parts,guards.boundary_integrals):
        with pytest.raises(ValueError):a.setflags(write=True)
    with pytest.raises(TypeError):guards.diagnostics["current_error"]=1


def test_guarded_voltage_constraint_against_public_capacitance(guards):
    shared=candidate._solver()([t.corners()+[.004,0] for t in guarded().traces],
        width=.008,height=.002,panels_per_edge=16,ground_modes=128,interpolation_degree=14)
    cap=shared.capacitance_per_permittivity
    # Independently prescribe zero potential on the middle trace, then
    # normalize the two signal currents by the principal capacitance block.
    v=np.zeros((3,2));v[[0,2]]=np.linalg.inv(cap[np.ix_([0,2],[0,2])])
    current=cap@v
    assert np.max(abs(v[1]))==0
    parts=np.array([current.T@q@current for q in shared.current_gram])[[0,2,3,4,1]]
    np.testing.assert_allclose(parts,guards.boundary_parts,rtol=1e-10,atol=0)
    # A floating-ground Schur complement is observably different.
    floating=cap[np.ix_([0,2],[0,2])]-cap[[0,2],1,None]*cap[None,1,[0,2]]/cap[1,1]
    assert not np.allclose(floating,cap[np.ix_([0,2],[0,2])],rtol=1e-3,atol=0)


@pytest.mark.parametrize("operation",["scale","reverse","dielectric"])
def test_current_geometry_invariants(guards,operation):
    scale=2 if operation=="scale" else 1
    after=two_ground_current_factors(guarded(scale=scale,reverse=operation=="reverse",eps=9 if operation=="dielectric" else 1),
        panels_per_edge=16,interpolation_degree=14)
    p=after.boundary_parts*scale;c=after.C0;j=after.boundary_integrals
    if operation=="reverse":p=p[[1,0,2,3,4],::-1,::-1];c=c[::-1,::-1];j=j[[1,0,2,3,4],::-1]
    np.testing.assert_allclose(p,guards.boundary_parts,rtol=1e-10,atol=0)
    np.testing.assert_allclose(c,guards.C0,rtol=1e-10,atol=0)
    np.testing.assert_allclose(j,guards.boundary_integrals,rtol=0,atol=1e-10)


def test_distinct_foils_guard_laws_and_independent_surface_formula():
    sec=guarded();conductors={"left":SurfaceMetal(58e6),"right":SurfaceMetal(35e6,1.4)}
    reference=ReferenceSurfaceMetals(SurfaceMetal(45e6),SurfaceMetal(21e6),None,{"guard":SurfaceMetal(17e6)})
    loss=two_ground_conductor_loss(sec,F,conductors=conductors,reference=reference,ground_thickness=35e-6,
        panels_per_edge=16,interpolation_degree=14)
    expected=np.zeros_like(loss.R)
    for k,f in enumerate(F):
        for b,m in enumerate(loss.metals):
            expected[k]+=np.sqrt(np.pi*f*mu_0*m.relative_permeability/m.conductivity)*loss.factors.boundary_parts[b]
    np.testing.assert_allclose(loss.R,expected,rtol=1e-12,atol=0)
    np.testing.assert_allclose(loss.L_internal*2*np.pi*F[:,None,None],expected,rtol=1e-12,atol=0)
    swapped=two_ground_conductor_loss(sec,F,conductors=conductors,
        reference=replace(reference,bottom=reference.top,top=reference.bottom),ground_thickness=35e-6,
        panels_per_edge=16,interpolation_degree=14)
    delta=np.sqrt(np.pi*F*mu_0)*(1/np.sqrt(21e6)-1/np.sqrt(45e6))
    expected_delta=delta[:,None,None]*(loss.factors.boundary_parts[2]-loss.factors.boundary_parts[3])
    np.testing.assert_allclose(swapped.R-loss.R,expected_delta,rtol=1e-10,atol=0)
    assert np.max(abs(expected_delta))>0
    network=loss.network(C=4*loss.factors.C0,G=np.zeros((2,2)),length=.02)
    assert np.isfinite(network.s).all()
    np.testing.assert_allclose(network.s,np.swapaxes(network.s,1,2),rtol=1e-10,atol=1e-12)
    assert np.max(np.linalg.svd(network.s,compute_uv=False))<=1+1e-10


@pytest.mark.parametrize("case",["wrong","bottom","top","sides","zero","concave","aspect","count","modes","degree"])
def test_invalid_inputs_stop_before_dependency(monkeypatch,case):
    monkeypatch.setattr(candidate,"_solver",lambda:pytest.fail("dependency reached"))
    sec=guarded();options={}
    if case=="wrong":sec=None
    elif case in ("bottom","top","sides"):
        kw=dict(bottom="ground",top="ground",sides="open");kw[case]="ground" if case=="sides" else "open"
        sec=CrossSection(sec.layers,sec.traces,sec.width,**kw)
    elif case=="zero":sec=CrossSection(sec.layers,[Trace("signal",0,.001,.0003)],sec.width,top="ground")
    elif case=="concave":sec=CrossSection(sec.layers,[PolygonTrace("signal",[[-.0002,.0009],[.0002,.0009],[0,.001], [.0002,.0011],[-.0002,.0011]])],sec.width,top="ground")
    elif case=="aspect":sec=CrossSection(sec.layers,sec.traces,.034,top="ground")
    else:options={dict(count="panels_per_edge",modes="ground_modes",degree="interpolation_degree")[case]:dict(count=0,modes=63,degree=11)[case]}
    with pytest.raises((ValueError,TypeError)):two_ground_current_factors(sec,**options)


@pytest.mark.parametrize("case",["signals","reference-type","missing-top","side","ground-name","ground-face","skin","core","frequency"])
def test_material_preflight_before_dependency(monkeypatch,case):
    monkeypatch.setattr(candidate,"_solver",lambda:pytest.fail("dependency reached"))
    sec=guarded();metals={"left":SurfaceMetal(58e6),"right":SurfaceMetal(35e6)}
    ref=ReferenceSurfaceMetals(SurfaceMetal(58e6),SurfaceMetal(58e6),None,{"guard":SurfaceMetal(58e6)});f=F
    if case=="signals":metals.pop("right")
    if case=="reference-type":ref=SurfaceMetal(58e6)
    if case=="missing-top":ref=replace(ref,top=None)
    if case=="side":ref=replace(ref,sides=SurfaceMetal(58e6))
    if case=="ground-name":ref=replace(ref,conductors={})
    if case=="ground-face":ref=replace(ref,conductors={"guard":TraceFaceMetals.uniform(SurfaceMetal(58e6))})
    if case=="skin":f=[1.]
    if case=="frequency":f=[0.]
    if case=="core":metals["left"]=LayeredSurfaceMetal(58e6,coatings=(MetalLayer(3e-5,14e6),))
    with pytest.raises((ValueError,TypeError)):two_ground_conductor_loss(sec,f,conductors=metals,reference=ref,ground_thickness=35e-6)


def test_missing_capability_fails_explicitly(monkeypatch):
    def missing(name):raise ImportError("deliberately absent capability")
    monkeypatch.setattr(candidate,"import_module",missing)
    with pytest.raises(RuntimeError,match="installed capability is unavailable"):
        two_ground_current_factors(guarded())


def test_old_capability_without_explicit_controls_fails(monkeypatch):
    monkeypatch.setattr(candidate,"import_module",lambda name:SimpleNamespace(solve_two_ground_rectangle=lambda polygons:None))
    with pytest.raises(RuntimeError,match="explicit ground_modes"):
        two_ground_current_factors(guarded())


@pytest.mark.parametrize("row",ROWS,ids=[r["case"] for r in ROWS])
def test_two_adjacent_registered_panel_changes(row,record_property):
    sec=section(row);conductors,reference=metals([t.name for t in sec.traces]);levels=[]
    for count,expected in zip((64,128,256),row["panel_levels"]):
        loss=two_ground_conductor_loss(sec,F,conductors=conductors,reference=reference,
            ground_thickness=35e-6,panels_per_edge=count,interpolation_degree=row["degree"])
        level={"C0":loss.factors.C0,"R":loss.R,"L_internal":loss.L_internal}
        for key,value in level.items():np.testing.assert_allclose(value,expected[key],rtol=1e-10,atol=0)
        levels.append(level)
    changes=[]
    for a,b in zip(levels,levels[1:]):
        change={}
        for key in a:
            scale=np.maximum(abs(a[key]),abs(b[key]))
            difference=np.divide(abs(a[key]-b[key]),scale,out=np.zeros_like(scale),where=scale!=0)
            change[key]=float(difference.max())
            assert change[key]<=.01
        changes.append(change)
    record_property("two_ground_panel_changes",json.dumps(changes,sort_keys=True))
