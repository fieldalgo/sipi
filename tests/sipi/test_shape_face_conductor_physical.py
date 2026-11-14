# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual tapered face loss, separate field evidence and independent networks."""
from dataclasses import replace
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection,CrossSectionDocument
from sipi.constants import mu_0
from sipi.face_conductor import TraceFaceMetals,ReferenceSurfaceMetals
from sipi.boundary_conductor import SurfaceMetal,LayeredSurfaceMetal
from sipi.shape_face_conductor import panel_shape_conductor_loss_by_face as solve
import sipi.shape_face_conductor as implementation
import sipi.shape_reference_conductor as whole
from test_shape_face_conductor import geometry,materials,F,OPTIONS
from test_layered_metal import transfer,LAYERS
from test_panel_shape_face_conductor_physical import snapshot as current_snapshot


def snapshot(r,section):
    options=dict(OPTIONS,panels_per_edge=r.factors.base.samples[0].request.panels_per_edge)
    case=dict(cross_section=CrossSectionDocument(section).to_dict(),options=options)
    return dict(labels=r.boundary_labels,R=r.R.tolist(),L_internal=r.L_internal.tolist(),
        boundary_parts=r.boundary_parts.tolist(),depth=r.skin_depth.tolist(),roughness=r.roughness_factor.tolist(),
        surface_impedance_real=r.surface_impedance.real.tolist(),surface_impedance_imag=r.surface_impedance.imag.tolist(),
        current=current_snapshot(case,r.factors))


@pytest.fixture(scope='module')
def observed():
    signals,reference=materials()
    return [solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6,
        panels_per_edge=n,**OPTIONS) for n in (32,64)]


def replay(monkeypatch,observed):
    r=observed[-1]
    monkeypatch.setattr(implementation,'panel_shape_face_current_factors',lambda *a,**k:r.factors)
    monkeypatch.setattr(whole,'panel_shape_current_factors',lambda *a,**k:r.factors.base)
    return r


def test_actual_field_samples_and_panel_refinement(observed,record_property):
    record_property('shape_face_loss_fields',json.dumps([snapshot(r,geometry()) for r in observed],sort_keys=True,allow_nan=False))
    changes={}
    for name,a,b in [('R',observed[0].R,observed[1].R),('L_internal',observed[0].L_internal,observed[1].L_internal),
        ('C0',observed[0].factors.C0,observed[1].factors.C0)]:
        changes[name]=float(np.max(abs(a-b))/np.max(abs(b)))
    assert max(changes.values())<=1e-3
    record_property('shape_face_loss_panel_changes',json.dumps(changes,sort_keys=True))
    for r in observed:
        assert r.factors.diagnostics['solve_count']==65
        assert r.factors.diagnostics['whole_sum_relative_change']<=1e-4
        assert r.factors.base.current_error<=1e-10
        assert np.linalg.eigvalsh(r.R).min()>0 and np.linalg.eigvalsh(r.L_internal).min()>0


def test_independent_metal_transfer_and_four_port_network(observed,record_property):
    r=observed[-1];sigmas=[58e6,58e6,35e6,20e6]+[45e6]*4+[48e6,30e6,40e6,50e6,60e6]
    zs=np.sqrt(2j*np.pi*F[:,None]*mu_0/np.array(sigmas));zs[:,1]=[transfer(f) for f in F]
    expected=sum(zs[:,i,None,None]*r.boundary_parts[i] for i in range(len(sigmas)))
    np.testing.assert_allclose(r.R+2j*np.pi*F[:,None,None]*r.L_internal,expected,rtol=1e-12,atol=0)
    C=np.broadcast_to(4.2*r.factors.C0,r.R.shape);G=2*np.pi*F[:,None,None]*.02*C
    net=r.network(C=C,G=G,length=.02);errors=[]
    for i,f in enumerate(F):
        z=expected[i]+2j*np.pi*f*r.factors.L_external;y=G[i]+2j*np.pi*f*C[i]
        t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
        a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(s-net.s[i]))))
    assert max(errors)<=1e-10
    assert np.max(np.linalg.svd(net.s,compute_uv=False))<=1+1e-10
    np.testing.assert_allclose(net.s,net.s.transpose(0,2,1),rtol=0,atol=1e-10)
    record_property('shape_face_loss_network_errors',json.dumps(errors))


@pytest.mark.parametrize('coated',[False,True])
def test_uniform_faces_match_whole_derivative_with_original_sum_gate(observed,monkeypatch,record_property,coated):
    replay(monkeypatch,observed);metal=LayeredSurfaceMetal(58e6,coatings=LAYERS) if coated else SurfaceMetal(58e6)
    signals={n:TraceFaceMetals.uniform(metal) for n in ('a','b')}
    reference=ReferenceSurfaceMetals(metal,None,None,{'guard':metal})
    face=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6,**OPTIONS)
    original=whole.panel_shape_conductor_loss_with_reference_metals(geometry(),F,conductors={n:metal for n in signals},
        reference=reference,ground_thickness=35e-6,**OPTIONS)
    errors={}
    for name in ('R','L_internal'):
        a,b=getattr(face,name),getattr(original,name);difference=abs(a-b)/np.maximum(abs(a),abs(b))
        errors[name]=float(difference.max());assert errors[name]<=1e-4
    assert face.factors.base is original.factors
    record_property('shape_face_uniform_whole_changes',json.dumps(errors,sort_keys=True))


def test_same_ground_law_whole_or_four_faces_has_identical_physical_weight(observed,monkeypatch):
    replay(monkeypatch,observed);signals,reference=materials(False)
    a=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6,**OPTIONS)
    reference=replace(reference,conductors={'guard':TraceFaceMetals.uniform(reference.conductors['guard'])})
    b=solve(geometry(),F,conductors=signals,reference=reference,ground_thickness=35e-6,**OPTIONS)
    np.testing.assert_allclose(a.R,b.R,rtol=1e-12,atol=0)
    np.testing.assert_allclose(a.L_internal,b.L_internal,rtol=1e-12,atol=0)
    np.testing.assert_array_equal(a.boundary_parts[-1],b.boundary_parts[-4:].sum(axis=0))


def test_actual_trace_permutation_preserves_named_face_weights(observed,record_property):
    original=geometry();section=CrossSection(original.layers,list(reversed(original.traces)),original.width)
    signals,reference=materials();r=solve(section,F,conductors=signals,reference=reference,ground_thickness=35e-6,panels_per_edge=32,**OPTIONS)
    base=observed[0]
    np.testing.assert_allclose(r.R[:,::-1,::-1],base.R,rtol=1e-6,atol=0)
    np.testing.assert_allclose(r.L_internal[:,::-1,::-1],base.L_internal,rtol=1e-6,atol=0)
    for i,label in enumerate(base.boundary_labels):
        j=r.boundary_labels.index(label);np.testing.assert_allclose(r.boundary_parts[j,::-1,::-1],base.boundary_parts[i],rtol=1e-6,atol=0)
    record_property('shape_face_loss_permuted',json.dumps(snapshot(r,section),sort_keys=True,allow_nan=False))
