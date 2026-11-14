# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent planar diffusion transfer, volume dissipation and half-space limits."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp
from scipy.linalg import expm

from sipi import MetalLayer, layered_surface_impedance
from sipi.conductor import surface_impedance
from sipi.constants import mu_0

F = np.geomspace(1e6, 1e10, 17)
LAYERS = (MetalLayer(.2e-6, 14e6, 3.), MetalLayer(1e-6, 40e6))
SIGMA = 58e6


def transfer(frequency, layers=LAYERS, base_depth=None):
    omega = 2*np.pi*frequency
    base = np.sqrt(1j*omega*mu_0/SIGMA)
    if base_depth is None:
        state = np.array([base, 1.], complex)
    else:
        delta = np.sqrt(2/(omega*mu_0*SIGMA))
        matrix = np.array([[0, 1j*omega*mu_0], [SIGMA, 0]])
        state = expm(matrix*(base_depth*delta))@np.array([0., 1.])
    for layer in reversed(layers):
        matrix = np.array([[0, 1j*omega*mu_0*layer.relative_permeability], [layer.conductivity, 0]])
        state = expm(matrix*layer.thickness_m)@state
    return state[0]/state[1]


def test_independent_matrix_exponential(record_property):
    result = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS)
    reference = np.array([transfer(f) for f in F])
    error = float(np.max(abs(result.impedance/reference-1)))
    record_property('transfer_relative_error', error)
    assert error < 1e-10


def test_independent_ode_and_integrated_volume_dissipation(record_property):
    reference, losses = [], []
    for f in F:
        omega = 2*np.pi*f
        scale = np.sqrt(omega*mu_0/(2*SIGMA))
        # Normalized E, H and dissipated power. The bulk load contributes
        # Re(eta_base)*|H_base|^2; each finite layer adds integral sigma*|E|^2 dx.
        state = np.array([1+1j, 1., 1.], complex)
        for layer in reversed(LAYERS):
            mu, sigma = mu_0*layer.relative_permeability, layer.conductivity
            delta = np.sqrt(2/(omega*mu*sigma))
            def derivative(u, y):
                return np.array([1j*omega*mu*delta/scale*y[1],
                    sigma*delta*scale*y[0], sigma*delta*scale*abs(y[0])**2])
            solution = solve_ivp(derivative, (0., layer.thickness_m/delta), state,
                                 method='DOP853', rtol=2e-11, atol=2e-12)
            assert solution.success
            state = solution.y[:, -1]
        reference.append(scale*state[0]/state[1])
        losses.append(scale*state[2].real/abs(state[1])**2)
    result = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS)
    field_error = float(np.max(abs(result.impedance/np.array(reference)-1)))
    power_error = float(np.max(abs(result.impedance.real/np.array(losses)-1)))
    record_property('ode_relative_error', field_error)
    record_property('dissipation_relative_error', power_error)
    assert field_error < 1e-8 and power_error < 1e-8


def test_finite_base_depth_converges_to_half_space(record_property):
    exact = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS).impedance
    errors = [float(np.max(abs(np.array([transfer(f, base_depth=n) for f in F])/exact-1)))
              for n in (8, 12, 16)]
    for i, error in enumerate(errors): record_property(f'base_depth_error_{(8,12,16)[i]}', error)
    assert errors[2] < errors[1] < errors[0]
    assert errors[2] < 1e-12


def test_no_layer_and_zero_thickness_preserve_existing_bulk_exactly():
    original = surface_impedance(F, conductivity=SIGMA, relative_permeability=2.)
    for layers in ((), (MetalLayer(0, 14e6, 3.), MetalLayer(0, 40e6))):
        result = layered_surface_impedance(F, conductivity=SIGMA, relative_permeability=2., layers=layers)
        np.testing.assert_array_equal(result.impedance, original)


def test_homogeneous_partition_and_layer_split():
    original = surface_impedance(F, conductivity=SIGMA)
    for count in (1, 2, 8, 32):
        layers = [MetalLayer(20e-6/count, SIGMA)]*count
        np.testing.assert_allclose(layered_surface_impedance(F, conductivity=SIGMA, layers=layers).impedance,
                                   original, rtol=1e-12)
    unsplit = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS).impedance
    split = tuple(MetalLayer(layer.thickness_m/4, layer.conductivity, layer.relative_permeability)
                  for layer in LAYERS for _ in range(4))
    np.testing.assert_allclose(layered_surface_impedance(F, conductivity=SIGMA, layers=split).impedance,
                               unsplit, rtol=1e-12)


def test_thick_top_limit_and_order_is_physical():
    layer = MetalLayer(1., 14e6, 3.)
    result = layered_surface_impedance(F, conductivity=SIGMA, layers=(layer,)+LAYERS)
    expected = surface_impedance(F, conductivity=layer.conductivity, relative_permeability=3.)
    np.testing.assert_allclose(result.impedance, expected, rtol=1e-12)
    forward = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS).impedance
    backward = layered_surface_impedance(F, conductivity=SIGMA, layers=LAYERS[::-1]).impedance
    assert np.max(abs(forward/backward-1)) > .1


def test_diffusion_scale_and_copied_readonly_result():
    f = F.copy(); layers = list(LAYERS)
    result = layered_surface_impedance(f, conductivity=SIGMA, layers=layers)
    scale = 4.
    scaled = layered_surface_impedance(F*scale, conductivity=SIGMA,
        layers=[MetalLayer(x.thickness_m/np.sqrt(scale), x.conductivity, x.relative_permeability) for x in LAYERS])
    np.testing.assert_allclose(scaled.impedance, result.impedance*np.sqrt(scale), rtol=1e-12)
    f[:] = 0; layers.clear()
    np.testing.assert_array_equal(result.frequency, F)
    assert result.layers == LAYERS
    assert result.skin_depth.shape == (len(F), 3)
    for key in ('frequency', 'impedance', 'skin_depth'): assert not getattr(result, key).flags.writeable


@pytest.mark.parametrize('key,value', [('thickness_m', -1), ('thickness_m', True),
    ('thickness_m', np.inf), ('conductivity', 0), ('conductivity', '1'),
    ('relative_permeability', -1), ('relative_permeability', 1j), ('relative_permeability', np.nan)])
def test_invalid_layer_materials(key, value):
    kw = dict(thickness_m=1e-6, conductivity=SIGMA, relative_permeability=1.); kw[key] = value
    with pytest.raises(ValueError): MetalLayer(**kw)


@pytest.mark.parametrize('change', [dict(frequency=[0]), dict(frequency=[1, 1]),
    dict(frequency=np.arange(1, 1026)), dict(layers=None), dict(layers=[{}]), dict(layers=[LAYERS[0]]*33),
    dict(conductivity=0), dict(relative_permeability=False), dict(layers=[MetalLayer(1e-6, 1.)]),
    dict(conductivity=1.)], ids=['dc', 'repeat', 'size', 'null', 'object', 'layers', 'sigma', 'mu', 'layer-gate', 'base-gate'])
def test_invalid_samples_and_good_conductor_gate(change):
    kw = dict(frequency=F, conductivity=SIGMA, layers=LAYERS); kw.update(change)
    with pytest.raises((ValueError, TypeError)): layered_surface_impedance(**kw)


def test_extreme_thickness_has_finite_thick_limit():
    result = layered_surface_impedance([1e9], conductivity=SIGMA, layers=[MetalLayer(1e308, 14e6)])
    np.testing.assert_allclose(result.impedance, surface_impedance([1e9], conductivity=14e6), rtol=1e-12)
