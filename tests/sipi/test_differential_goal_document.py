# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved forward-pair goals, source contracts and exact API replay."""
import json

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument
from sipi.templates import coupled_stripline, coupled_layered_stripline
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric, PrincipalAxisDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_differential_line_goal import MESH, QUANTITY, document as api_document, synthetic
from test_line_goal_document import document as scalar_document
from test_line_goal import install_fake
from crosscheck import require_tool, Stopwatch
from test_differential_line_goal import reference_record

SCHEMA = 'sipi.line-quantity-design/2'


def sweep(name='left_width', lower=.2e-3, upper=1e-3):
    return dict(kind='sweep', count=2, variables=[dict(name=name, lower=lower, upper=upper)])


def source():
    return ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3, substrate_height=.5e-3,
             eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
             air_height=5e-3, box_width=12e-3), quantity='z_diff_forward', frequency=1e9,
        materials={}, mesh=MESH, fixed_pitch_m=.95e-3, sampling=sweep())


def document():
    return LineQuantityDesignDocument(source(), conductor=api_document().to_dict()['conductor'],
        quantity=QUANTITY, target=100., tolerance=.5, max_evaluations=24, schema=SCHEMA)


@pytest.fixture(scope='module')
def solved():
    doc = document()
    return doc, doc.solve()


def test_saved_asymmetric_fixed_pitch_goal_matches_direct_api(solved):
    doc, result = solved
    def direct(width):
        raw = api_document(width).to_dict(); raw['schema'] = 'sipi.transmission-line/6'
        return TransmissionLineDocument.from_dict(raw)
    expected = seek_line_quantity(direct, [.2e-3, 1e-3], 100., quantity=QUANTITY,
                                   tolerance=.5, max_evaluations=24)
    assert result.history == expected.history and result.to_dict() == expected.to_dict()
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(result.result, key), getattr(expected.result, key), rtol=1e-10)
    np.testing.assert_allclose(result.result.characteristic().z_characteristic,
                               expected.result.characteristic().z_characteristic, rtol=1e-10)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .5
    assert abs(result.result.characteristic().mixed_mode().z_characteristic[0, 1, 0]) > 1
    for row in result.history:
        raw = row.to_dict()['input']; traces = raw['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x'] == pytest.approx(.95e-3, rel=1e-12)
        assert raw['schema'] == 'sipi.transmission-line/6' and raw['length_m'] == 0.
        assert raw['conductor'] == doc.to_dict()['conductor']


def test_uniform_pair_material_goal_matches_analytic_complex_scaling():
    parameters = dict(width=.3e-3, gap=.2e-3, plane_spacing=1e-3, eps_r=1.,
                      thickness=50e-6, box_width=6e-3)
    cross = CrossSectionDocument(coupled_stripline(**parameters), mesh=MESH)
    vacuum = cross.analyze().z_diff_forward; desired = 3.7; loss = .02
    target = (vacuum/np.sqrt(desired*(1-1j*loss))).real
    study = ImpedanceStudyDocument('coupled_stripline', parameters, quantity='z_diff_forward',
        frequency=1e9, materials={'dielectric': ConstantDielectric(4., loss)}, mesh=MESH,
        material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
        sampling=sweep('dk', 2., 6.))
    doc = LineQuantityDesignDocument(study, conductor=dict(kind='perfect'), quantity=QUANTITY,
        target=target, tolerance=.5, max_evaluations=24, schema=SCHEMA)
    result = LineQuantityDesignDocument.loads(doc.dumps()).solve()
    assert result.parameter == pytest.approx(desired, rel=.015)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .5
    assert result.value == pytest.approx((vacuum/np.sqrt(result.parameter*(1-1j*loss))).real, rel=1e-10)
    for selected in (result.document, result.refined_document):
        assert selected.to_dict()['materials']['dielectric']['parameters']['eps_r'] == result.parameter
    assert study.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['eps_r'] == 4.
    assert result.document.analyze().characteristic().mixed_mode().z_characteristic[0, 0, 0].real == pytest.approx(result.value, rel=1e-10)
    print(json.dumps(dict(case='saved-paired-material-goal', target_ohm=float(target),
        expected_eps=desired, selected_eps=result.parameter, relative_eps_error=abs(result.parameter/desired-1),
        requested_residual_ohm=result.residual, refined_residual_ohm=result.refined_residual)))


def test_saved_selected_matrix_against_independent_forward_eigenspace(solved):
    scipy = require_tool('scipy'); clock = Stopwatch(); line = solved[1].result
    with clock('openphysics'): actual = line.characteristic().z_characteristic[0]
    with clock('reference'):
        omega = 2*np.pi*line.frequency[0]
        z = line.R[0]+1j*omega*line.L[0]; y = line.G[0]+1j*omega*line.C[0]
        scale = np.sqrt(abs(z).max()/abs(y).max())
        roots, vectors = scipy.linalg.eig(np.block([
            [np.zeros_like(z), z/scale], [scale*y, np.zeros_like(y)]]))
        selected = roots.imag > 0
        assert np.count_nonzero(selected) == 2 and np.all(roots[selected].real >= 0)
        v = vectors[:, selected]; expected = scale*v[:2]@np.linalg.inv(v[2:])
        u = np.array([1., -1.])
    reference_record('saved-differential-goal-forward-eigenspace', 'scipy',
        'balanced 2N voltage/current eigenspace at the saved selected RLGC',
        dict(Zc=float(abs(actual-expected).max()/abs(expected).max()),
             Zdd=float(abs(u@(actual-expected)@u)/abs(u@expected@u))), clock)


def test_fixed_total_height_and_tilted_material_source_without_preliminary_solve(monkeypatch):
    import sipi.line_goal_document as implementation
    parameters = dict(width=.3e-3, gap=.2e-3, lower_height=.4e-3, upper_height=.6e-3,
        lower_eps_r=3., upper_eps_r=5., thickness=35e-6, box_width=4e-3)
    material = PrincipalAxisDielectric(ConstantDielectric(3., .01), ConstantDielectric(5., .02), .2)
    study = ImpedanceStudyDocument('coupled_layered_stripline', parameters,
        quantity='z_diff_forward', frequency=1e9, materials={'lower': material}, mesh=MESH,
        sampling=sweep('lower_height', .3e-3, .5e-3), fixed_plane_spacing_m=1e-3)
    def forbidden(*args, **kwargs): pytest.fail('parsing or source reuse invoked a solve')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', forbidden)
    doc = LineQuantityDesignDocument(study, conductor=dict(kind='perfect'), quantity=QUANTITY,
                                    target=100., tolerance=.5, schema=SCHEMA)
    seen = []
    def inspect(factory, bounds, target, **options):
        for height in (.3e-3, .4e-3, .5e-3):
            line = factory(height)
            expected = CrossSectionDocument(coupled_layered_stripline(**dict(parameters,
                lower_height=height, upper_height=1e-3-height)), mesh=dict(MESH, min_angle=28.))
            assert line.cross_section.to_dict() == expected.to_dict()
            assert line.to_dict()['materials'] == study.to_dict()['material_evaluation']['materials']
            seen.append(line.dumps())
        assert options['quantity'] == QUANTITY and bounds == [.3e-3, .5e-3]
        return 'inspected'
    monkeypatch.setattr(implementation, 'seek_line_quantity', inspect)
    assert doc.solve() == 'inspected' and len(seen) == 3


def test_saved_roundtrip_and_shared_execution_exact_history(monkeypatch):
    synthetic(monkeypatch)
    raw = document().to_dict(); raw.update(target=90., tolerance=.01)
    doc = LineQuantityDesignDocument.from_dict(raw)
    assert normalize_saved(doc.dumps()) == doc.dumps()
    assert SCHEMA in saved_schemas()
    expected = doc.solve().to_dict()
    report = execute_saved(doc.dumps(), max_evaluations=24)
    assert report['status'] == 'complete' and report['input'] == doc.to_dict()
    assert report['result'] == expected and report['result']['quantity'] == QUANTITY
    raw['study']['parameters']['left_width'] = 1.
    assert LineQuantityDesignDocument.loads(doc.dumps()).dumps() == doc.dumps()
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation'])
def test_explicit_v2_scalar_goal_matches_v1_without_changing_default(monkeypatch, quantity):
    install_fake(monkeypatch)
    original = scalar_document().to_dict(); original.update(quantity=quantity, target=2., tolerance=.01)
    v1 = LineQuantityDesignDocument.from_dict(original)
    changed = dict(original, schema=SCHEMA); v2 = LineQuantityDesignDocument.from_dict(changed)
    assert v1.solve().to_dict() == v2.solve().to_dict()
    assert scalar_document().to_dict()['schema'] == 'sipi.line-quantity-design/1'


@pytest.mark.parametrize('mode', ['budget', 'diagnostics'])
def test_execution_controls_reject_before_source_or_field_solve(monkeypatch, mode):
    def forbidden(*args, **kwargs): pytest.fail('invalid execution controls invoked solve')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(LineQuantityDesignDocument, 'solve', forbidden)
    with pytest.raises(ValueError):
        execute_saved(document().dumps(), **(dict(max_evaluations=23) if mode == 'budget'
                                            else dict(diagnostics=['characteristic'])))


@pytest.mark.parametrize('mode', ['diagnostic', 'refinement', 'skin'])
def test_shared_execution_retains_pair_failures_and_available_input(monkeypatch, mode):
    calls = synthetic(monkeypatch, broken='diagnostic' if mode == 'diagnostic' else None)
    raw = document().to_dict()
    if mode == 'refinement':
        old = TransmissionLineDocument.analyze
        endpoint = api_document(.2e-3).analyze().characteristic().mixed_mode().z_characteristic[0, 0, 0].real
        raw.update(target=float(endpoint), tolerance=.01); calls.clear()
        def fail_refinement(self):
            if self.cross_section.mesh_options['edge_size'] == MESH['edge_size']/2:
                raise ArithmeticError('retained refinement failure')
            return old(self)
        monkeypatch.setattr(TransmissionLineDocument, 'analyze', fail_refinement)
    if mode == 'skin':
        raw['study']['fixed_pitch_m'] = None
        raw['study']['sampling'] = sweep('left_thickness', 1e-6, 35e-6)
    result = execute_saved(LineQuantityDesignDocument.from_dict(raw).dumps())
    assert result['status'] == 'failed' and result['result'] is None
    error = result['error']
    assert error['quantity'] == QUANTITY and error['unit'] == 'ohm'
    assert error['stage'] == dict(diagnostic='search/diagnostic', refinement='refinement/extraction', skin='search/factory')[mode]
    assert error['attempts'] == (3 if mode == 'refinement' else 1)
    assert len(error['history']) == (2 if mode == 'refinement' else 0)
    assert (error['input'] is not None) == (mode != 'skin')
    if mode == 'skin': assert not calls
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('case', ['v1', 'schema', 'scalar_quantity', 'scalar_source', 'modal_source',
    'unknown_quantity', 'missing', 'extra', 'dc', 'count', 'multiple', 'zero_target',
    'endpoint_gap', 'endpoint_material', 'conductor_names'])
def test_strict_pair_input_rejection_before_mesh(monkeypatch, case):
    raw = document().to_dict(); study = raw['study']
    if case == 'v1': raw['schema'] = 'sipi.line-quantity-design/1'
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-design/999'
    if case == 'scalar_quantity': raw['quantity'] = 'impedance_real'
    if case == 'scalar_source': raw['study'] = scalar_document().to_dict()['study']
    if case == 'modal_source':
        raw['study'] = ImpedanceStudyDocument('coupled_stripline', dict(width=.3e-3, gap=.2e-3,
            plane_spacing=1e-3, eps_r=4.), quantity='z_diff', frequency=1e9, materials={},
            mesh=MESH, sampling=sweep('width', .2e-3, .4e-3)).to_dict()
    if case == 'unknown_quantity': raw['quantity'] = 'differential_attenuation'
    if case == 'missing': del raw['target']
    if case == 'extra': raw['launch'] = 'differential'
    if case == 'dc': study['material_evaluation']['frequency_hz'] = 0.
    if case == 'count': study['sampling']['count'] = 3
    if case == 'multiple': study['sampling']['variables'].append(dict(name='right_width', lower=.4e-3, upper=.6e-3))
    if case == 'zero_target': raw['target'] = 0.
    if case == 'endpoint_gap': study['sampling']['variables'][0]['upper'] = 2e-3
    if case == 'endpoint_material':
        study.update(schema='sipi.impedance-study/4', fixed_pitch_m=None,
            material_variables={'dk': dict(region='substrate', path=['eps_r'])}, sampling=sweep('dk', .5, 4.))
        study['material_evaluation']['materials'] = {'substrate': {'schema': 'sipi.dielectric/1', 'kind': 'constant', 'parameters': {'eps_r': 4., 'tan_delta': .02}}}
    if case == 'conductor_names': raw['conductor']['conductors']['renamed'] = raw['conductor']['conductors'].pop('positive')
    def forbidden(*args, **kwargs): pytest.fail('invalid saved input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError, match='relative permittivity' if case == 'endpoint_material' else None):
        LineQuantityDesignDocument.from_dict(raw)


def test_scalar_study_v1_still_rejects_pair_source():
    with pytest.raises(ValueError):
        LineQuantityStudyDocument(source(), conductor=dict(kind='perfect'), quantity='impedance_real')
