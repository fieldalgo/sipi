# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit exterior-port profile: independent tools, power and truncation."""
from dataclasses import FrozenInstanceError
from importlib import metadata
import warnings

import numpy as np
import pytest
from scipy.integrate import solve_ivp, quad
from scipy.special import ndtr

from sipi import GaussianConductivityProfile, ConductivityProfileResult
from sipi.constants import mu_0, epsilon_0
from sipi.conductor import surface_impedance
from crosscheck import require_tool, Stopwatch, make_record, observable, emit


def inputs(rho, xi, sigma=58e6):
    f = xi*sigma/(2*np.pi*epsilon_0)
    delta = 1/np.sqrt(np.pi*f*mu_0*sigma)
    return GaussianConductivityProfile(conductivity=sigma, rms_m=rho*delta), f


def common_plane(z, f, distance):
    eta = np.sqrt(mu_0/epsilon_0)
    phase = 2*np.pi*f*np.sqrt(mu_0*epsilon_0)*distance
    tangent = np.tan(phase)
    return (z+1j*eta*tangent)/(1+1j*z/eta*tangent)


@pytest.mark.parametrize('rms', [1e-6, 1e-4])
def test_independent_tool_physical_scale_sweep(rms):
    tool = require_tool('scikit-rf')
    ratios = np.logspace(-3, 1, 9)
    f = ratios**2/(np.pi*mu_0*58e6*rms**2)
    model = GaussianConductivityProfile(conductivity=58e6, rms_m=rms)
    clock = Stopwatch()
    with clock('openphysics'):
        actual = model.analyze(f, cutoff_rms=5).impedance
    with clock('reference'), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        expected = tool.tlineFunctions.surface_impedance(f, dict(sigma=58e6,ep_r=1.,mu_r=1.),
            rms_roughness=rms, rtol=1e-9)
    assert not caught
    error = float(np.max(abs(actual/expected-1)))
    record=make_record(case=f'gaussian-profile-rms-{rms}', physics='1D full-Maxwell conductivity profile',
        api='sipi.GaussianConductivityProfile.analyze', discretization='normalized Riccati DOP853 integration',
        tool='scikit-rf', tool_discretization='Magnus/TL surface-impedance integration',
        matched=['nonmagnetic eps0 Gaussian CDF conductivity, bulk metal, positive frequency',
                 'transition +/-5 RMS, output plane at -5 RMS, displacement current'],
        not_matched=['no general 2D line extraction or measured foil calibration'],
        observables=[observable('surface impedance','ohm','max complex relative difference',error,1e-6)],
        analytical_acceptance='separate smooth identity, Maxwell scaling, field-energy balance and cutoff checks',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error < 1e-6


@pytest.mark.parametrize('xi', [1e-9, 1e-6, 1e-3])
@pytest.mark.parametrize('rho', [.001, .01, .1, 1., 3., 10.])
def test_independent_tool_parameter_boundary(rho, xi):
    tool = require_tool('scikit-rf')
    model, f = inputs(rho, xi)
    actual = model.analyze([f], cutoff_rms=5).impedance[0]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        expected = tool.tlineFunctions.surface_impedance(np.array([f]),
            dict(sigma=model.conductivity, ep_r=1., mu_r=1.), rms_roughness=model.rms_m, rtol=1e-9)[0]
    assert not caught
    error=float(abs(actual/expected-1))
    print('Gaussian boundary tool error',rho,xi,error)
    assert error < 1e-6


def linear_energy(rho, xi, cutoff):
    """Independent linear E/H state; no impedance Riccati equation."""
    bulk = (1+1j)/np.sqrt(1+1j*xi)
    def rhs(u, fields):
        e, h = fields
        return [-2j*rho*h, -rho*(ndtr(u)+1j*xi)*e]
    solved = solve_ivp(rhs, [cutoff,-cutoff], [bulk,1+0j], method='DOP853',
                       rtol=2e-12, atol=2e-13, dense_output=True)
    assert solved.success
    e_outer, h_outer = solved.y[:,-1]
    def density(u, real):
        e,h = solved.sol(u)/h_outer
        return float(rho*ndtr(u)*abs(e)**2 if real else rho*(2*abs(h)**2-xi*abs(e)**2))
    energy=[]
    for real, bulk_part in [(True,bulk.real),(False,bulk.imag)]:
        value,error=quad(density,-cutoff,cutoff,args=(real,),epsabs=1e-9,epsrel=1e-10,limit=400)
        assert error < 1e-7*max(1,abs(value))
        energy.append(value+bulk_part/abs(h_outer)**2)
    return e_outer/h_outer, complex(*energy)


@pytest.mark.parametrize('xi', [1e-9, 1e-6, 1e-3])
@pytest.mark.parametrize('rho', [.001, .01, .1, 1., 3., 10.])
def test_linear_maxwell_power_and_exact_reference_translation(rho, xi):
    model, f = inputs(rho,xi)
    rs = np.sqrt(np.pi*f*mu_0/model.conductivity)
    values={n:model.analyze([f],cutoff_rms=n).impedance[0] for n in (5,8,10)}
    linear, energy = linear_energy(rho,xi,8)
    errors=dict(linear=float(abs(values[8]/rs/linear-1)),energy=float(abs(values[8]/rs/energy-1)))
    assert errors['linear']<1e-8
    assert errors['energy']<1e-8
    assert values[8].real>0
    for cutoff,gate in [(5,1e-4),(8,1e-8)]:
        shifted=common_plane(values[cutoff],f,(10-cutoff)*model.rms_m)
        errors['cutoff'+str(cutoff)]=float(abs(shifted/values[10]-1))
        assert errors['cutoff'+str(cutoff)]<gate
    print('Gaussian field energy cutoff',rho,xi,errors)
    # Electric storage can exceed magnetic storage at this exterior port.
    if rho==10 and xi==1e-3:
        assert values[8].imag<0 and energy.imag<0


def layered(rho,xi,count,cutoff=8):
    h=2*cutoff/count
    y=(1+1j)/np.sqrt(1+1j*xi)
    for u in (np.linspace(-cutoff,cutoff,count+1)[:-1]+h/2)[::-1]:
        c=ndtr(u)+1j*xi
        q=rho*np.sqrt(2j*c)*h
        t=np.tanh(q)/q
        y=(y+2j*rho*h*t)/(1+rho*c*h*y*t)
    return y


@pytest.mark.parametrize('xi',[1e-9,1e-3])
@pytest.mark.parametrize('rho',[.1,1.,10.])
def test_piecewise_layer_mesh_convergence(rho,xi):
    model,f=inputs(rho,xi);rs=np.sqrt(np.pi*f*mu_0/model.conductivity)
    exact=model.analyze([f]).impedance[0]/rs
    errors=[abs(layered(rho,xi,n)/exact-1) for n in (2048,4096)]
    print('Gaussian layer convergence',rho,xi,errors)
    assert errors[1]<errors[0] and errors[1]<1e-5


def test_smooth_identity_and_dimensional_scaling():
    f=np.array([1e6,1e9,1e12]);sigma=58e6
    smooth=GaussianConductivityProfile(conductivity=sigma,rms_m=0).analyze(f)
    exact=np.sqrt(1j*2*np.pi*f*mu_0/(sigma+1j*2*np.pi*f*epsilon_0))
    np.testing.assert_allclose(smooth.impedance,exact,rtol=1e-12,atol=0)
    assert smooth.reference_plane_m==0
    model,f=inputs(3,1e-6);base=model.analyze([f]).impedance
    for factor in (1e-3,1e3):
        changed=GaussianConductivityProfile(conductivity=model.conductivity*factor,
            rms_m=model.rms_m/factor).analyze([f*factor])
        np.testing.assert_allclose(changed.impedance,base,rtol=1e-10,atol=0)


def test_reference_metadata_copy_isolation_and_type_boundary():
    frequencies=np.array([1e9,4e9]);model=GaussianConductivityProfile(conductivity=58e6,rms_m=1e-6)
    result=model.analyze(frequencies);frequencies[0]=0
    assert result.frequency[0]==1e9 and result.reference_plane_m==-8e-6
    assert not result.frequency.flags.writeable and not result.impedance.flags.writeable
    assert not result.skin_depth.flags.writeable
    with pytest.raises(ValueError):result.impedance[0]=0
    with pytest.raises(FrozenInstanceError):model.rms_m=0
    with pytest.raises(TypeError):surface_impedance([1e9],conductivity=58e6,roughness=model)
    raw=np.array([1+2j,3-4j]);copy=ConductivityProfileResult(model,[1e9,4e9],raw)
    raw[:]=0
    np.testing.assert_array_equal(copy.impedance,[1+2j,3-4j])


@pytest.mark.parametrize('key,value',[('conductivity',0),('conductivity',True),('conductivity',-1),
    ('conductivity',np.inf),('conductivity',1+0j),('conductivity',None),
    ('rms_m',True),('rms_m',-1),('rms_m',np.nan),('rms_m',None),('rms_m',1+0j)])
def test_invalid_material(key,value):
    with pytest.raises(ValueError):GaussianConductivityProfile(**dict(dict(conductivity=58e6,rms_m=1e-6),**{key:value}))


@pytest.mark.parametrize('frequency,cutoff',[(0,8),([0],8),([],8),([1,1],8),([2,1],8),
    ([True],8),([np.inf],8),([1+0j],8),([1e9],True),([1e9],4.9),([1e9],10.1),
    ([1e9],np.nan),(list(range(1,1026)),8),([1e9,1e30],8)])
def test_invalid_analysis_before_integrator(frequency,cutoff,monkeypatch):
    import sipi.conductivity_profile as module
    def forbidden(*args,**kwargs):pytest.fail('invalid input integrated')
    monkeypatch.setattr(module,'solve_ivp',forbidden)
    with pytest.raises(ValueError):GaussianConductivityProfile(conductivity=58e6,rms_m=1e-6).analyze(frequency,cutoff_rms=cutoff)


@pytest.mark.parametrize('rho,xi',[(10.001,1e-6),(.1,1.001e-3),
                                 (10*(1+1e-9),1e-6),(.1,1e-3*(1+1e-9))])
def test_out_of_model_range_before_integrator(rho,xi,monkeypatch):
    import sipi.conductivity_profile as module
    model,f=inputs(rho,xi)
    monkeypatch.setattr(module,'solve_ivp',lambda *a,**kw:pytest.fail('out-of-range input integrated'))
    with pytest.raises(ValueError):model.analyze([f])


def test_integration_failure_is_not_a_result(monkeypatch):
    import sipi.conductivity_profile as module
    from types import SimpleNamespace
    model=GaussianConductivityProfile(conductivity=58e6,rms_m=1e-6)
    monkeypatch.setattr(module,'solve_ivp',lambda *a,**kw:SimpleNamespace(success=False,message='controlled failure'))
    with pytest.raises(RuntimeError,match='controlled failure'):model.analyze([1e9])
    for value in [np.nan+1j, -1+1j, 0+1j]:
        monkeypatch.setattr(module,'solve_ivp',lambda *a,**kw:SimpleNamespace(success=True,y=np.array([[value]])))
        with pytest.raises(RuntimeError,match='invalid passive-port'):model.analyze([1e9])


@pytest.mark.parametrize('impedance',[[0+1j],[-1+1j],[np.inf+1j],[1j*np.nan],[1+1j,2+2j]])
def test_invalid_result(impedance):
    model=GaussianConductivityProfile(conductivity=58e6,rms_m=1e-6)
    with pytest.raises(ValueError):ConductivityProfileResult(model,[1e9],impedance)
