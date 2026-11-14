# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual matched fields, independent metals and four-port network checks."""
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import CrossSection, FEMShapeCurrentFactors
from sipi.constants import mu_0
from sipi.boundary_conductor import SurfaceMetal
import sipi.fem_shape_loss as api
from test_fem_shape_loss import geometry, arguments, F, OPTIONS
from test_layered_metal import transfer


def snapshot(result):
    f=result.factors
    return dict(R=result.R.tolist(),L_internal=result.L_internal.tolist(),C0=f.C0.tolist(),Q=f.extension_parts.tolist(),
        finite_differences=f.finite_difference_parts.tolist(),step_m=f.step_m,diagnostics=dict(f.diagnostics),
        original_parts=f.base.parts.tolist(),original_flux=f.current_integrals.tolist(),
        skin_depth=result.skin_depth.tolist(),impedance_real=result.surface_impedance.real.tolist(),impedance_imag=result.surface_impedance.imag.tolist())


@pytest.fixture(scope='module')
def observed():
    return [api.fem_shape_conductor_loss_by_boundary(geometry(),F,**(arguments()|{k:v*factor for k,v in OPTIONS.items()})) for factor in (1.,.5)]


def test_actual_shape_currents_metal_matrices_and_refinement(observed,record_property):
    record_property('fem_shape_loss_fields',json.dumps([snapshot(r) for r in observed]))
    changes={name:float(np.max(abs(getattr(observed[0],name)-getattr(observed[1],name)))/np.max(abs(getattr(observed[1],name)))) for name in ('R','L_internal')}
    changes['C0']=float(np.max(abs(observed[0].factors.C0-observed[1].factors.C0))/np.max(abs(observed[1].factors.C0)))
    record_property('fem_shape_loss_mesh_changes',json.dumps(changes))
    assert max(changes.values())<=.01
    for r in observed:
        assert isinstance(r.factors,FEMShapeCurrentFactors) and len(r.factors.samples)==24
        assert r.factors.current_error<=.05
        assert np.linalg.eigvalsh(r.R).min()>0 and np.linalg.eigvalsh(r.L_internal).min()>0
        np.testing.assert_allclose(r.resistance_parts.sum(axis=1),r.R,rtol=1e-12,atol=0)


def test_independent_surface_transfer_and_four_port(observed,record_property):
    r=observed[-1]
    zs=np.array([[transfer(f),np.sqrt(2j*np.pi*f*mu_0/35e6),np.sqrt(2j*np.pi*f*mu_0/58e6)] for f in F])
    expected=np.einsum('fb,bij->fij',zs,r.factors.parts)
    np.testing.assert_allclose(r.R+2j*np.pi*F[:,None,None]*r.L_internal,expected,rtol=1e-10,atol=0)
    C=np.broadcast_to(4*r.factors.C0,r.R.shape);G=2*np.pi*F[:,None,None]*.002*C
    network=r.network(C=C,G=G,length=.02);errors=[]
    for i,f in enumerate(F):
        z=expected[i]+2j*np.pi*f*r.factors.L_external;y=G[i]+2j*np.pi*f*C[i]
        t=expm(np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])*.02)
        a,b,c,d=t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:];eye=np.eye(2)
        s=np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        errors.append(float(np.max(abs(s-network.s[i]))))
    record_property('fem_shape_loss_network_errors',json.dumps(errors));assert max(errors)<=1e-10
    assert np.max(np.linalg.svd(network.s,compute_uv=False))<=1+1e-10
    np.testing.assert_allclose(network.s,network.s.transpose(0,2,1),rtol=0,atol=1e-10)


def test_reweighting_retains_the_exact_current_object(observed,monkeypatch):
    current=observed[-1].factors;calls=[];real=CrossSection.mesh
    def mesh(self,**kw):calls.append(kw);return real(self,**kw)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    monkeypatch.setattr(api,'fem_shape_current_factors',lambda *a:current)
    kw=arguments();metal=SurfaceMetal(58e6);kw['conductors']={n:metal for n in current.names};kw['reference']=metal
    result=api.fem_shape_conductor_loss_by_boundary(geometry(),F,**kw)
    assert result.factors is current and calls==[OPTIONS]
    z=np.sqrt(2j*np.pi*F*mu_0/58e6)
    np.testing.assert_allclose(result.R+2j*np.pi*F[:,None,None]*result.L_internal,z[:,None,None]*current.total,rtol=1e-12,atol=0)


def test_result_metal_order_and_readonly_matrices(observed):
    r=observed[-1]
    assert r.boundary_labels==('signal:positive','signal:negative','reference')
    for value in (r.R,r.L_internal,r.skin_depth,r.surface_impedance,r.resistance_parts):assert not value.flags.writeable
