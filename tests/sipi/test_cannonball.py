# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit Rz mapping: independent packing, relaxation integral and extraction."""
from dataclasses import FrozenInstanceError
import math

import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.integrate import quad
from scipy.spatial.distance import pdist

from conductor_diagnostics import record_conductor_refinement
from galerkin import annulus_mesh
from sipi import CrossSection, CrossSectionDocument, coupled_microstrip
from sipi.conductor import surface_impedance, surface_current_factors, surface_conductor_loss
from sipi.line_model import TransmissionLineDocument
from sipi.roughness import CannonballHuray, CausalHuray

F = np.array([1e9, 4e9, 10e9])
SIGMA = 58e6
MESH = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)
MODEL = CannonballHuray(3e-6)


def test_mapping_against_independent_packing_and_profile_integral():
    # Build 9/4/1 sphere centres, then derive height, tile and area independently.
    centres = np.array([[2*x+layer, 2*y+layer, 1+math.sqrt(2)*layer]
        for layer, n in enumerate((3, 2, 1)) for x in range(n) for y in range(n)])
    assert len(centres) == 14 and pdist(centres).min() == pytest.approx(2)
    height = centres[:, 2].max()+1
    tile = np.prod(np.ptp(centres[:, :2], axis=0)+2)
    profile_rms = math.sqrt(quad(lambda x: (x-.5)**2, 0, 1, epsabs=1e-14)[0])
    geometric_radius = MODEL.rz_10point_m*profile_rms/height
    assert MODEL.radius_m == pytest.approx(geometric_radius, rel=.005)
    area = sum(4*np.pi for _ in centres)/tile
    assert MODEL.surface_ratio == pytest.approx(area, rel=1e-14)
    # Published rounded examples: no measured trace/coupon is being reproduced.
    assert CannonballHuray(2.13e-6).radius_m == pytest.approx(.128e-6, abs=.0005e-6)
    assert CannonballHuray(2.50e-6).radius_m == pytest.approx(.150e-6, abs=.0005e-6)
    print('packing radius mapping relative rounding', MODEL.radius_m/geometric_radius-1)


def relaxation(z):
    def integrand(theta):
        return (2/np.pi)*z/(z+np.tan(theta)**2)
    return (quad(lambda t: integrand(t).real, 0, np.pi/2, epsabs=1e-12, epsrel=1e-12)[0]
            + 1j*quad(lambda t: integrand(t).imag, 0, np.pi/2, epsabs=1e-12, epsrel=1e-12)[0])


@pytest.mark.parametrize('omega_tau', np.logspace(-6, 6, 7))
def test_complex_surface_law_against_independent_relaxation_integral(omega_tau):
    # Published radius mapping, independent integral rather than complex sqrt.
    radius = .06*3e-6
    delta = radius*np.sqrt(2/omega_tau)
    expected = 1+(7*np.pi/3)*relaxation(1j*omega_tau)
    np.testing.assert_allclose(MODEL.factor([delta]), [expected], rtol=1e-10, atol=1e-10)


def test_real_loss_scaling_limits_and_equivalent_population():
    delta = 1/np.sqrt(np.pi*F*mu_0*SIGMA)
    rough = surface_impedance(F, conductivity=SIGMA, roughness=MODEL)
    smooth = surface_impedance(F, conductivity=SIGMA)
    expected_r = 1+(7*np.pi/3)/(1+delta/MODEL.radius_m+.5*(delta/MODEL.radius_m)**2)
    np.testing.assert_allclose(rough.real/smooth.real, expected_r, rtol=1e-12)
    np.testing.assert_allclose(rough/smooth, MODEL.factor(delta), rtol=1e-12)
    assert np.all(rough.imag > rough.real)
    equivalent = MODEL.to_huray()
    assert isinstance(equivalent, CausalHuray)
    np.testing.assert_array_equal(rough, surface_impedance(F, conductivity=SIGMA, roughness=equivalent))
    np.testing.assert_allclose(surface_impedance(F, conductivity=4*SIGMA,
        roughness=CannonballHuray(1.5e-6)), rough/2, rtol=1e-12)
    np.testing.assert_allclose(surface_impedance(F, conductivity=SIGMA, relative_permeability=4,
        roughness=CannonballHuray(1.5e-6)), 2*rough, rtol=1e-12)
    np.testing.assert_allclose(MODEL.factor([1e300, 1e-300]), [1, 1+7*np.pi/3], rtol=1e-12)
    for rz in (1e-300, 1e300):
        assert np.all(np.isfinite(CannonballHuray(rz).factor([1e-300, 1e300])))
    f = np.array([1e-10, 1e-8])
    extra = (surface_impedance(f, conductivity=SIGMA, roughness=MODEL)
             - surface_impedance(f, conductivity=SIGMA))
    expected_l = (7*np.pi/3)*mu_0*MODEL.radius_m
    np.testing.assert_allclose(extra.imag/(2*np.pi*f), expected_l, rtol=1e-5)


@pytest.mark.parametrize('value', [0, -1, True, None, '1', [1], 1j, np.nan, np.inf, np.nextafter(0., 1.)])
def test_invalid_or_unrepresentable_rz(value):
    with pytest.raises(ValueError):
        CannonballHuray(value)


@pytest.mark.parametrize('delta', [[], [0], [-1], [True], [None], [np.inf], [[1]], '1'])
def test_invalid_depth(delta):
    with pytest.raises(ValueError):
        MODEL.factor(delta)


def test_frozen_model_no_mixed_correction_or_dc():
    with pytest.raises(FrozenInstanceError):
        MODEL.rz_10point_m = 1
    with pytest.raises(ValueError, match='either'):
        surface_impedance(F, conductivity=SIGMA, roughness=MODEL, roughness_rms=1e-6)
    with pytest.raises(ValueError, match='positive frequency'):
        surface_impedance([0, 1], conductivity=SIGMA, roughness=MODEL)


def test_coax_extraction_against_independent_constitutive_and_geometric_reference():
    a, b = .5e-3, 2e-3
    radius = .06*3e-6
    h = np.array([1+(7*np.pi/3)*relaxation(1j*2*np.pi*f*mu_0*SIGMA*radius**2) for f in F])
    exact = (1+1j)*np.sqrt(np.pi*F*mu_0/SIGMA)*h*(1/a+1/b)/(2*np.pi)
    zs = surface_impedance(F, conductivity=SIGMA, roughness=MODEL)
    errors = []
    for nr in (64, 128, 256):
        mesh = annulus_mesh(a, b, nr, 256)
        factors = surface_current_factors(mesh, {'inner': mesh.boundary['inner']}, mesh.boundary['outer'])
        observed = zs*factors.total[0, 0]
        errors.append(max(np.max(abs(observed.real/exact.real-1)), np.max(abs(observed.imag/exact.imag-1))))
    print('Cannonball coax R/internal-L errors', errors)
    assert errors[0] > errors[1] > errors[2] and errors[-1] < .01


def line(roughness=None, mesh=None):
    cs = CrossSectionDocument(coupled_microstrip(width=.5e-3, gap=.3e-3,
        substrate_height=1e-3, thickness=50e-6, eps_r=4), mesh=mesh or MESH)
    return TransmissionLineDocument(cs, frequency=F, materials={}, length=.03,
        conductor=dict(kind='surface', conductivity=SIGMA, ground_thickness=35e-6,
            relative_permeability=1, roughness=roughness or dict(kind='cannonball-huray', rz_10point_m=3e-6)),
        schema='sipi.transmission-line/2')


def test_saved_line_replay_equivalent_huray_and_pair_refinement(monkeypatch, record_property):
    doc = line()
    assert TransmissionLineDocument.loads(doc.dumps()).dumps() == doc.dumps()
    data = doc.to_dict(); data['conductor']['roughness']['rz_10point_m'] = 7
    assert doc.to_dict()['conductor']['roughness']['rz_10point_m'] == 3e-6
    calls = []
    original = CrossSection.mesh
    def counted(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)
    monkeypatch.setattr(CrossSection, 'mesh', counted)
    result = doc.analyze()
    assert len(calls) == 1
    replay = TransmissionLineDocument.loads(doc.dumps()).analyze()
    explicit = line(dict(kind='causal-huray', radii_m=[.18e-6], surface_ratios=[14*np.pi/9])).analyze()
    for other in (replay, explicit):
        for key in ('R', 'L', 'G', 'C'):
            np.testing.assert_allclose(getattr(result, key), getattr(other, key), rtol=1e-12, atol=0)
        np.testing.assert_allclose(result.network.s, other.network.s, rtol=0, atol=1e-10)
    coarse = surface_conductor_loss(doc.cross_section.section, F, conductivity=SIGMA,
        ground_thickness=35e-6, roughness=MODEL, **MESH)
    fine = surface_conductor_loss(doc.cross_section.section, F, conductivity=SIGMA,
        ground_thickness=35e-6, roughness=MODEL,
        **{key: value/2 for key, value in MESH.items()})
    errors = [float(np.max(abs(getattr(coarse, key)-getattr(fine, key)))/np.max(abs(getattr(fine, key))))
              for key in ('R', 'L_internal')]
    record_conductor_refinement(record_property, doc.cross_section.section, coarse, fine,
        MESH, {key: value/2 for key, value in MESH.items()})
    print('pair mesh R/internal-L changes', errors)
    assert max(errors) < .05
    assert fine.factors.current_error < coarse.factors.current_error < .05
    np.testing.assert_allclose(result.network.s, result.network.s.swapaxes(1, 2), rtol=0, atol=1e-10)
    assert np.max(np.linalg.svd(result.network.s, compute_uv=False)) <= 1+1e-10


@pytest.mark.parametrize('edit', [
    lambda d: d.update(rz_10point_m=0), lambda d: d.update(rz_10point_m=True),
    lambda d: d.update(rz_10point_m=float('inf')), lambda d: d.pop('rz_10point_m'),
    lambda d: d.update(rms_m=3e-6), lambda d: d.update(rz_m=3e-6),
    lambda d: d.update(radii_m=[1e-6]), lambda d: d.update(surface_ratios=[4.9]),
])
def test_invalid_saved_kind_rejected_before_mesh(edit, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail('invalid roughness reached mesh')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    spec = dict(kind='cannonball-huray', rz_10point_m=3e-6)
    edit(spec)
    with pytest.raises(ValueError):
        line(spec)


def test_version_one_and_duplicate_keys_are_rejected():
    data = line().to_dict(); data['schema'] = 'sipi.transmission-line/1'
    with pytest.raises(ValueError):
        TransmissionLineDocument.from_dict(data)
    text = line().dumps().replace('"rz_10point_m": 3e-06', '"rz_10point_m": 3e-06, "rz_10point_m": 4e-06')
    assert text != line().dumps()
    with pytest.raises(ValueError, match='duplicate'):
        TransmissionLineDocument.loads(text)
