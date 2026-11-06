# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Frequency-domain RMS law: numerical reference, limits and surface assembly."""
from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.integrate import quad
from scipy.stats import weibull_min

from galerkin import annulus_mesh
from sipi import CrossSection, CrossSectionDocument, microstrip
from sipi.conductor import surface_impedance, surface_current_factors, surface_conductor_loss
from sipi.line_model import TransmissionLineDocument
from sipi.roughness import GroissRMS

SIGMA=58e6
F=np.array([1e9,4e9,10e9])
MESH=dict(edge_size=5e-6,far_size=.2e-3,grade=.1)


@pytest.mark.parametrize('x',np.logspace(-2,1,9))
def test_factor_matches_independent_weibull_tail_integral(x):
    # The correction above one is a Weibull survival probability. Integrate
    # its density, independently of the implementation's log-domain formula.
    tail=quad(lambda t: 1.6*t**.6*np.exp(-t**1.6),x,np.inf,
              epsabs=1e-13,epsrel=1e-13)[0]
    actual=GroissRMS(.7e-6).factor([2*.7e-6*x])[0]
    np.testing.assert_allclose(actual,1+tail,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(actual,1+weibull_min.sf(x,1.6),rtol=1e-12,atol=1e-12)


def test_smooth_saturated_monotonic_and_extreme_finite_limits():
    depth=np.logspace(-300,300,61)
    with np.errstate(all='raise'):
        np.testing.assert_array_equal(GroissRMS(0).factor(depth),np.ones(depth.size))
        factor=GroissRMS(1).factor(depth)
        assert np.all(np.diff(factor)<=0) and np.all((factor>=1)&(factor<=2))
        assert factor[0]==2 and factor[-1]==1
        assert GroissRMS(1e300).factor([1e-300])[0]==2
        assert GroissRMS(1e-300).factor([1e300])[0]==1
    smooth=surface_impedance(F,conductivity=SIGMA)
    np.testing.assert_array_equal(surface_impedance(F,conductivity=SIGMA,roughness=GroissRMS(0)),smooth)
    saturated=surface_impedance(F,conductivity=SIGMA,roughness=GroissRMS(1e300))
    np.testing.assert_array_equal(saturated,2*smooth)


def test_full_impedance_phase_and_dimensional_similarity():
    model=GroissRMS(.5e-6)
    smooth=surface_impedance(F,conductivity=SIGMA)
    rough=surface_impedance(F,conductivity=SIGMA,roughness=model)
    assert np.all(rough.real>smooth.real) and np.all(rough.real<2*smooth.real)
    np.testing.assert_allclose(rough.imag,rough.real,rtol=1e-14)
    assert np.all(np.diff(rough.real/smooth.real)>0)
    np.testing.assert_allclose(surface_impedance(F,conductivity=4*SIGMA,roughness=GroissRMS(.25e-6)),rough/2,rtol=1e-12)
    np.testing.assert_allclose(surface_impedance(F,conductivity=SIGMA,relative_permeability=4,
                                               roughness=GroissRMS(.25e-6)),2*rough,rtol=1e-12)
    legacy=surface_impedance(F,conductivity=SIGMA,roughness_rms=model.rms_m)
    np.testing.assert_array_equal(legacy.imag,smooth.imag)
    assert np.all(rough.imag>legacy.imag)


@pytest.mark.parametrize('rms',[True,None,'1',[-1],-1,np.nan,np.inf,1j])
def test_invalid_rms(rms):
    with pytest.raises(ValueError):GroissRMS(rms)


@pytest.mark.parametrize('depth',[[],[True],[None],[0],[-1],[np.inf],[[1]],'1'])
def test_invalid_depth(depth):
    with pytest.raises(ValueError):GroissRMS(0).factor(depth)


def test_model_is_frozen_and_mixing_is_rejected():
    model=GroissRMS(1e-6)
    with pytest.raises(FrozenInstanceError):model.rms_m=2e-6
    with pytest.raises(ValueError,match='either'):
        surface_impedance(F,conductivity=SIGMA,roughness=model,roughness_rms=1e-6)
    with pytest.raises(ValueError,match='positive frequency'):
        surface_impedance([0,1e9],conductivity=SIGMA,roughness=model)


def test_coax_current_extraction_converges_in_r_and_internal_l():
    a,b=.5e-3,2e-3
    depth=1/np.sqrt(np.pi*F*mu_0*SIGMA)
    k=1+weibull_min.sf(depth/(2*.5e-6),1.6)
    # Independent smooth half-space and exact coaxial surface-current integral.
    exact=(1+1j)*np.sqrt(np.pi*F*mu_0/SIGMA)*k*(1/a+1/b)/(2*np.pi)
    zs=surface_impedance(F,conductivity=SIGMA,roughness=GroissRMS(.5e-6))
    errors=[]
    for nr in (64,128,256):
        mesh=annulus_mesh(a,b,nr,256)
        factor=surface_current_factors(mesh,{'inner':mesh.boundary['inner']},mesh.boundary['outer'])
        observed=zs*factor.total[0,0]
        errors.append(max(np.max(abs(observed.real/exact.real-1)),
                          np.max(abs((observed.imag/(2*np.pi*F))/(exact.imag/(2*np.pi*F))-1))))
    assert errors[0]>errors[1]>errors[2] and errors[-1]<.01
    print('Groiss coax relative R/internal-L errors',errors)


def document(**changes):
    cs=CrossSectionDocument(microstrip(width=.5e-3,substrate_height=1e-3,
        thickness=50e-6,eps_r=4),mesh=MESH)
    args=dict(cross_section=cs,frequency=F,materials={},length=.03,
        conductor=dict(kind='surface',conductivity=SIGMA,ground_thickness=35e-6,
                       relative_permeability=1,roughness=dict(kind='groiss',rms_m=.5e-6)),
        schema='sipi.transmission-line/2')
    args.update(changes)
    return TransmissionLineDocument(**args)


def test_saved_line_shared_mesh_rlgc_network_and_attenuation(monkeypatch):
    doc=document()
    restored=TransmissionLineDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()
    calls=[];original=CrossSection.mesh
    def counted(self,**kwargs):
        calls.append(kwargs);return original(self,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',counted)
    result=restored.analyze()
    assert len(calls)==1
    direct=surface_conductor_loss(doc.cross_section.section,F,conductivity=SIGMA,
        ground_thickness=35e-6,roughness=GroissRMS(.5e-6),**MESH)
    np.testing.assert_allclose(result.R,direct.R,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.L,result.dielectric.L+direct.L_internal,rtol=1e-10,atol=0)
    replay=doc.analyze()
    for name in ('R','L','G','C'):
        np.testing.assert_array_equal(getattr(result,name),getattr(replay,name))
    np.testing.assert_array_equal(result.network.s,replay.network.s)
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10
    propagation=result.propagation()
    assert np.all(propagation.gamma.real>0)
    fine=surface_conductor_loss(doc.cross_section.section,F,conductivity=SIGMA,
        ground_thickness=35e-6,roughness=GroissRMS(.5e-6),
        edge_size=2.5e-6,far_size=.1e-3,grade=.05)
    for a,b in ((direct.R,fine.R),(direct.L_internal,fine.L_internal)):
        assert np.max(abs(a-b))/np.max(abs(b))<.05
    assert fine.factors.current_error<direct.factors.current_error<.05


@pytest.mark.parametrize('mutate',[
    lambda d:d['conductor']['roughness'].update(rms_m=True),
    lambda d:d['conductor']['roughness'].update(radii_m=[1e-6]),
    lambda d:d['conductor']['roughness'].pop('rms_m'),
    lambda d:d['conductor'].update(roughness_rms=0),
    lambda d:d.update(schema='sipi.transmission-line/1'),
    lambda d:d.update(frequency_hz=[1e3,1e6]),
])
def test_invalid_saved_model_is_rejected_before_meshing(monkeypatch,mutate):
    data=document().to_dict()
    mutate(data)
    def forbidden(*args,**kwargs):pytest.fail('invalid input reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError):TransmissionLineDocument.from_dict(data)
