# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Guarded-line boundary partition with independent metal/network equations."""
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi.constants import mu_0
from sipi.face_conductor import ReferenceSurfaceMetals
from sipi.boundary_conductor import SurfaceMetal
from sipi.shape_reference_conductor import panel_shape_conductor_loss_with_reference_metals as solve
import sipi.shape_reference_conductor as implementation
import sipi.panel_shape_conductor as original
from sipi.shape_panel_line import shape_current_record
from test_panel_shape_conductor import guard
from test_shape_reference_conductor import metals,F
from test_layered_metal import transfer

OPTIONS=dict(ground_modes=1024,interpolation_degree=16,step_fraction=.001)


def relative(a,b):
    return float(np.max(abs(np.asarray(a)-b))/np.max(abs(b)))


def snapshot(result):
    return dict(labels=result.boundary_labels,R=result.R.tolist(),L_internal=result.L_internal.tolist(),
        boundary_parts=result.boundary_parts.tolist(),depth=result.skin_depth.tolist(),
        surface_impedance_real=result.surface_impedance.real.tolist(),surface_impedance_imag=result.surface_impedance.imag.tolist(),
        current=shape_current_record(result.factors,dict(OPTIONS,panels_per_edge=result.factors.samples[0].request.panels_per_edge)))


@pytest.fixture(scope='module')
def observed():
    signals,reference=metals()
    return [solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6,
        panels_per_edge=n,**OPTIONS) for n in (16,32,64)]


def replay(monkeypatch,observed):
    factors={r.factors.samples[0].request.panels_per_edge:r.factors for r in observed};calls=[]
    def extract(section,**options):calls.append(options);return factors[options['panels_per_edge']]
    monkeypatch.setattr(implementation,'panel_shape_current_factors',extract)
    monkeypatch.setattr(original,'panel_shape_current_factors',extract)
    return calls


def test_actual_panel_levels_preserve_every_boundary_and_report_small_entries(observed,record_property):
    record_property('separate_reference_fields',json.dumps([snapshot(r) for r in observed],allow_nan=False))
    changes=[];entries=[]
    for a,b in zip(observed,observed[1:]):
        changes.append(dict(C0=relative(a.factors.C0,b.factors.C0),
            Q=[relative(x,y) for x,y in zip(a.boundary_parts,b.boundary_parts)],R=relative(a.R,b.R)))
        denominator=np.maximum(abs(a.R),abs(b.R));ratio=np.zeros_like(denominator)
        np.divide(abs(a.R-b.R),denominator,out=ratio,where=denominator>0);entries.append(ratio.tolist())
    record_property('separate_reference_panel_changes',json.dumps(changes))
    record_property('separate_reference_entry_changes',json.dumps(entries))
    assert max(changes[-1]['C0'],changes[-1]['R'],*changes[-1]['Q'])<.01
    for result in observed:
        assert result.factors.names==('a','b') and result.factors.ground_trace_names==('guard',)
        assert len(result.factors.samples)==17
        np.testing.assert_array_equal(result.boundary_parts,result.factors.boundary_step_parts[-1,[0,2,3,1]])
        assert result.factors.current_error<1e-10 and result.factors.diagnostics['step_relative_change']<=1e-4


@pytest.mark.parametrize('coated',[False,True])
def test_independent_weighted_metal_and_four_port_network(observed,monkeypatch,record_property,coated):
    replay(monkeypatch,observed);signals,reference=metals(coated)
    r=solve(guard(),F,conductors=signals,reference=reference,ground_thickness=35e-6,panels_per_edge=64,**OPTIONS)
    expected=np.zeros_like(r.R,dtype=complex)
    zs=np.column_stack([np.sqrt(2j*np.pi*F*mu_0/s) for s in (58e6,35e6,45e6,20e6)])
    if coated:zs[:,-1]=[transfer(f) for f in F]
    for b in range(4):expected+=zs[:,b,None,None]*r.boundary_parts[b]
    np.testing.assert_allclose(r.R+2j*np.pi*F[:,None,None]*r.L_internal,expected,rtol=1e-12,atol=0)
    assert np.min(np.linalg.eigvalsh(r.R))>0
    C=np.broadcast_to(4.2*r.factors.C0,r.R.shape);G=2*np.pi*F[:,None,None]*.02*C
    net=r.network(C=C,G=G,length=.02);errors=[]
    for i,f in enumerate(F):
        z=r.R[i]+2j*np.pi*f*(r.factors.L_external+r.L_internal[i]);y=G[i]+2j*np.pi*f*C[i]
        t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
        a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(s-net.s[i]))))
    assert max(errors)<1e-10
    assert np.max(np.linalg.svd(net.s,compute_uv=False))<=1+1e-10
    np.testing.assert_allclose(net.s,net.s.transpose(0,2,1),rtol=0,atol=1e-10)
    record_property('separate_reference_weighted',json.dumps(snapshot(r),allow_nan=False))
    record_property('separate_reference_network_errors',json.dumps(errors))


@pytest.mark.parametrize('coated',[False,True])
def test_identical_reference_metals_preserve_original_common_api(observed,monkeypatch,coated):
    calls=replay(monkeypatch,observed);signals,reference=metals(coated);metal=reference.conductors['guard']
    ref=ReferenceSurfaceMetals(metal,None,None,{'guard':metal})
    separate=solve(guard(),F,conductors=signals,reference=ref,ground_thickness=35e-6,panels_per_edge=64,**OPTIONS)
    common=original.panel_shape_conductor_loss_by_boundary(guard(),F,conductors=signals,reference=metal,
        ground_thickness=35e-6,panels_per_edge=64,**OPTIONS)
    assert len(calls)==2 and common.factors is separate.factors
    np.testing.assert_allclose(separate.R,common.R,rtol=1e-12,atol=0)
    np.testing.assert_allclose(separate.L_internal,common.L_internal,rtol=1e-12,atol=0)
    np.testing.assert_array_equal(separate.factors.C0,common.factors.C0)
    np.testing.assert_array_equal(separate.factors.current_integrals,common.factors.current_integrals)


def test_actual_signal_permutation_keeps_named_reference_assignment(observed,record_property):
    signals,reference=metals();r=solve(guard(reverse=True),F,conductors=signals,reference=reference,
        ground_thickness=35e-6,panels_per_edge=32,**OPTIONS)
    a=observed[1]
    assert r.boundary_labels==('signal:b','signal:a','reference:bottom','reference:ground:guard')
    np.testing.assert_allclose(r.R[:,::-1,::-1],a.R,rtol=1e-6,atol=0)
    np.testing.assert_allclose(r.boundary_parts[[1,0,2,3],::-1,::-1],a.boundary_parts,rtol=1e-6,atol=0)
    record_property('separate_reference_permuted',json.dumps(snapshot(r),allow_nan=False))
