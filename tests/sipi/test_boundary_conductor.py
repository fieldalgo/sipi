# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Per-boundary metal power, independent surface law and geometry convergence."""
from importlib import metadata

import numpy as np
import pytest
from galerkin import rectangle_mesh, annulus_mesh
from sipi import CrossSection, coupled_microstrip, microstrip
from sipi.boundary_conductor import (SurfaceMetal, surface_conductor_loss_by_boundary,
                                     _boundary_from_factors)
from sipi.conductor import surface_current_factors, surface_conductor_loss
from sipi.constants import mu_0
from sipi.roughness import CausalHuray, CannonballHuray, GroissRMS
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

F = np.array([1e9, 4e9, 10e9])


def combine(factors, metals):
    samples = [m._samples(F) for m in metals]
    return _boundary_from_factors(factors, F, metals,
        np.column_stack([s[1] for s in samples]), np.column_stack([s[2] for s in samples]),
        np.column_stack([s[3] for s in samples]))


def test_distinct_plate_metals_match_independent_surface_law_and_power():
    skrf = require_tool('scikit-rf'); clock = Stopwatch()
    width = .002
    mesh = rectangle_mesh(width, .001, 8, 4)
    metals = (SurfaceMetal(58e6), SurfaceMetal(14.5e6, relative_permeability=2.))
    with clock('openphysics'):
        factors = surface_current_factors(mesh, {'s': mesh.boundary['top']}, mesh.boundary['bottom'])
        result = combine(factors, metals)
    with clock('reference'):
        zs = (1+1j)*np.column_stack([skrf.tlineFunctions.surface_resistivity(
            F, 1/m.conductivity, m.relative_permeability) for m in metals])
        expected_r = zs.real.sum(axis=1)/width
        expected_l = zs.imag.sum(axis=1)/(width*2*np.pi*F)
    error = max(np.max(abs(result.R[:, 0, 0]/expected_r-1)),
                np.max(abs(result.L_internal[:, 0, 0]/expected_l-1)))
    record = make_record(case='distinct_boundary_metals_plate', physics='PEC surface-current perturbation',
        api='sipi.boundary_conductor', discretization='shared P1 currents, separate boundary impedances',
        tool='scikit-rf', tool_discretization='independent good-conductor surface law with exact uniform plate current',
        matched=['same frequency, per-boundary conductivity and relative permeability', 'bounded uniform plate current 1/width'],
        not_matched=['roughness empirical validity', 'arbitrary PCB loss convergence or conductor diffusion'],
        observables=[observable('R and internal L', 'relative', 'maximum relative difference', error, 1e-10)],
        analytical_acceptance='exact plate, separate coax boundary factors/refinement and PCB mesh/outer gates', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert error < 1e-10
    np.testing.assert_allclose(result.resistance_parts[:, :, 0, 0], zs.real/width, rtol=1e-10)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
    assert result.boundary_labels == ('signal:s', 'reference')


def test_distinct_coax_metals_refine_each_boundary_and_combined_impedance():
    a, b = .5e-3, 2e-3
    metals = (SurfaceMetal(58e6), SurfaceMetal(14.5e6))
    zs = (1+1j)*np.sqrt(np.pi*F[:, None]*mu_0/np.array([58e6, 14.5e6]))
    exact = zs[:, 0]/(2*np.pi*a)+zs[:, 1]/(2*np.pi*b)
    errors = []; parts_errors = []
    for nr in (64, 128, 256):
        mesh = annulus_mesh(a, b, nr, 256)
        factors = surface_current_factors(mesh, {'inner': mesh.boundary['inner']}, mesh.boundary['outer'])
        result = combine(factors, metals)
        got = result.R[:, 0, 0]+2j*np.pi*F*result.L_internal[:, 0, 0]
        errors.append(np.max(abs(got/exact-1)))
        parts_errors.append(abs(factors.parts[:, 0, 0]/np.array([1/(2*np.pi*a), 1/(2*np.pi*b)])-1))
    assert errors[0] > errors[1] > errors[2] and errors[-1] < .02
    assert np.all(parts_errors[0] > parts_errors[1]) and np.all(parts_errors[1] > parts_errors[2])
    assert np.max(parts_errors[-1]) < .02


@pytest.fixture(scope='module')
def coupled():
    def section(width=None):
        kwargs = {} if width is None else dict(box_width=width)
        return coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
            thickness=.05e-3, eps_r=4, **kwargs)
    base = section(); names = [t.name for t in base.traces if not t.ground]
    metals = {names[0]: SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
              names[1]: SurfaceMetal(35e6, roughness_rms=.5e-6)}
    reference = SurfaceMetal(45e6, roughness=CannonballHuray(2e-6))
    common = dict(conductors=metals, reference=reference, ground_thickness=35e-6)
    coarse = surface_conductor_loss_by_boundary(base, F, **common, edge_size=5e-6, far_size=.2e-3, grade=.1)
    fine = surface_conductor_loss_by_boundary(base, F, **common, edge_size=2.5e-6, far_size=.1e-3, grade=.05)
    wider = surface_conductor_loss_by_boundary(section(base.width*2), F, **common,
        edge_size=2.5e-6, far_size=.1e-3, grade=.05)
    return base, coarse, fine, wider


def test_asymmetric_metals_keep_psd_mutual_loss_and_mesh_outer_convergence(coupled):
    section, coarse, fine, wider = coupled
    assert np.max(abs(fine.R-coarse.R))/np.max(abs(fine.R)) < .05
    assert np.max(abs(wider.R-fine.R))/np.max(abs(wider.R)) < .05
    assert fine.factors.current_error < coarse.factors.current_error < .05
    assert not np.allclose(fine.R[:, 0, 0], fine.R[:, 1, 1])
    for matrix in (fine.R, fine.L_internal):
        np.testing.assert_allclose(matrix, matrix.swapaxes(1, 2), rtol=0, atol=1e-10)
        assert np.linalg.eigvalsh(matrix).min() >= -1e-10
    dielectric = section.analyze(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
    net = fine.network(C=dielectric.C, G=np.zeros((2, 2)), length=.03)
    assert np.linalg.svd(net.s, compute_uv=False).max() <= 1+1e-10
    np.testing.assert_allclose(net.s, net.s.swapaxes(1, 2), rtol=0, atol=1e-10)
    for array in (fine.R, fine.L_internal, fine.skin_depth, fine.roughness_factor,
                  fine.surface_impedance, fine.resistance_parts):
        assert not array.flags.writeable


@pytest.mark.parametrize('metal', [SurfaceMetal(58e6), SurfaceMetal(58e6, roughness_rms=.8e-6),
    SurfaceMetal(58e6, roughness=GroissRMS(.8e-6)),
    SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.])),
    SurfaceMetal(58e6, roughness=CannonballHuray(2e-6))])
def test_identical_metals_reproduce_existing_common_model(metal):
    section = microstrip(width=.5e-3, substrate_height=1e-3, thickness=35e-6, eps_r=4)
    options = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
    expected = surface_conductor_loss(section, F, conductivity=metal.conductivity,
        ground_thickness=35e-6, relative_permeability=metal.relative_permeability,
        roughness_rms=metal.roughness_rms, roughness=metal.roughness, **options)
    result = surface_conductor_loss_by_boundary(section, F,
        conductors={t.name: metal for t in section.traces if not t.ground}, reference=metal,
        ground_thickness=35e-6, **options)
    np.testing.assert_allclose(result.R, expected.R, rtol=1e-12)
    np.testing.assert_allclose(result.L_internal, expected.L_internal, rtol=1e-12)


@pytest.mark.parametrize('changes', [dict(conductivity=True), dict(conductivity=0),
    dict(conductivity=float('inf')), dict(relative_permeability=-1), dict(roughness_rms=-1),
    dict(roughness_rms=True), dict(roughness='unknown'),
    dict(roughness_rms=1e-6, roughness=CausalHuray([.2e-6], [2.]))])
def test_invalid_metal_rejected(changes):
    with pytest.raises((TypeError, ValueError)): SurfaceMetal(**dict(dict(conductivity=58e6), **changes))


@pytest.mark.parametrize('case', ['missing', 'extra', 'wrong_type', 'ground_type', 'signal_depth',
                                 'reference_depth', 'zero_thickness', 'dc', 'underresolved'])
def test_each_boundary_gate_and_mapping_rejected_before_meshing(monkeypatch, case):
    section = microstrip(width=.5e-3, substrate_height=1e-3, thickness=35e-6 if case != 'zero_thickness' else 0, eps_r=4)
    name = next(t.name for t in section.traces if not t.ground)
    metals = {name: SurfaceMetal(58e6)}; reference = SurfaceMetal(58e6); frequency = F
    if case == 'missing': metals = {}
    if case == 'extra': metals['unknown'] = reference
    if case == 'wrong_type': metals[name] = {}
    if case == 'ground_type': reference = {}
    if case == 'signal_depth': metals[name] = SurfaceMetal(1e4)
    if case == 'reference_depth': reference = SurfaceMetal(1e4)
    if case == 'dc': frequency = [0]
    if case != 'underresolved':
        def forbidden(*args, **kwargs): pytest.fail('invalid boundary input reached meshing')
        monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError):
        surface_conductor_loss_by_boundary(section, frequency, conductors=metals,
            reference=reference, ground_thickness=35e-6,
            edge_size=50e-6, far_size=.4e-3, grade=.2)
