# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved lossy goals, source reuse, strict budgets and retained failure evidence."""
import json
from importlib import metadata

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0

from sipi import CrossSection, CrossSectionDocument, stripline, layered_stripline, coplanar_stripline
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import ConstantDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_line_goal import MESH, document as api_document, install_fake
from test_face_line import metal
from crosscheck import require_tool, Stopwatch, emit, make_record, observable


def sweep(name='width', lower=.3e-3, upper=.8e-3):
    return dict(kind='sweep', count=2, variables=[dict(name=name, lower=lower, upper=upper)])


def study():
    return ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
        thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3), quantity='z0',
        frequency=1e9, materials={}, mesh=MESH, sampling=sweep())


def document():
    return LineQuantityDesignDocument(study(), conductor=dict(kind='surface', conductivity=58e6,
        relative_permeability=1., roughness=dict(kind='hammerstad', rms_m=.5e-6), ground_thickness=35e-6),
        quantity='impedance_real', target=50., tolerance=.5, max_evaluations=24)


@pytest.fixture(scope='module')
def solved():
    doc = document()
    return doc, doc.solve()


def test_saved_geometry_goal_matches_direct_api_exact_history_and_fields(solved):
    doc, result = solved
    def direct(width):
        raw = api_document(width, metal=True).to_dict()
        raw.update(schema='sipi.transmission-line/6', reference_ohms=50.)
        raw['conductor'] = doc.to_dict()['conductor']
        return TransmissionLineDocument.from_dict(raw)
    expected = seek_line_quantity(direct, [.3e-3, .8e-3], 50., quantity='impedance_real',
                                   tolerance=.5, max_evaluations=24)
    assert result.history == expected.history and result.to_dict() == expected.to_dict()
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(result.result, key), getattr(expected.result, key), rtol=1e-10)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .5
    assert result.document.to_dict()['schema'] == 'sipi.transmission-line/6'


def test_material_leaf_attenuation_goal_keeps_selected_model_and_closed_form():
    source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
        eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
        materials={'dielectric': ConstantDielectric(4., .02)},
        material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
        mesh=MESH, sampling=sweep('loss', .01, .1))
    doc = LineQuantityDesignDocument(source, conductor=dict(kind='perfect'), quantity='attenuation',
                                    target=1., tolerance=.001, max_evaluations=24)
    restored = LineQuantityDesignDocument.loads(doc.dumps()); result = restored.solve()
    scale = 2*np.pi*1e9*np.sqrt(mu_0*epsilon_0*4); s = 1/scale
    expected = 2*s*np.sqrt(1+s*s)
    assert result.parameter == pytest.approx(expected, rel=.005)
    assert max(abs(result.residual), abs(result.refined_residual)) <= .001
    for saved in (result.document, result.refined_document):
        assert saved.to_dict()['materials']['dielectric']['parameters']['tan_delta'] == result.parameter
    assert source.to_dict()['material_evaluation']['materials']['dielectric']['parameters']['tan_delta'] == .02
    assert result.document.analyze().propagation().alpha[0, 0] == pytest.approx(result.value, rel=1e-10)


def test_fixed_height_source_uses_existing_geometry_constraint_without_running_study(monkeypatch):
    import sipi.line_goal_document as implementation
    source = ImpedanceStudyDocument('layered_stripline', dict(width=.5e-3, lower_height=.4e-3,
        upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5., thickness=50e-6, box_width=4e-3),
        quantity='z0', frequency=1e9, materials={}, mesh=MESH,
        sampling=sweep('lower_height', .3e-3, .5e-3), fixed_plane_spacing_m=1e-3)
    doc = LineQuantityDesignDocument(source, conductor=dict(kind='perfect'), quantity='impedance_real',
                                    target=50., tolerance=.5)
    def forbidden(*args, **kwargs): pytest.fail('source study was executed')
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', forbidden)
    seen = []
    def inspect(factory, bounds, target, **options):
        for height in (.3e-3, .4e-3, .5e-3):
            actual = factory(height)
            expected = CrossSectionDocument(layered_stripline(width=.5e-3, lower_height=height,
                upper_height=1e-3-height, lower_eps_r=3., upper_eps_r=5., thickness=50e-6,
                box_width=4e-3), mesh=dict(MESH, min_angle=28.))
            assert actual.cross_section.to_dict() == expected.to_dict()
            seen.append(actual.to_dict())
        return 'factory inspected'
    monkeypatch.setattr(implementation, 'seek_line_quantity', inspect)
    assert doc.solve() == 'factory inspected' and len(seen) == 3


def test_saved_goal_accepts_ground_face_conductor_and_keeps_diagnostics():
    source = ImpedanceStudyDocument('coplanar_stripline', dict(width=.5e-3, gap=.2e-3,
        ground_width=.5e-3, plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6,
        eps_r=4., tan_delta=.02, box_width=4e-3), quantity='z0', frequency=1e9, materials={},
        mesh=MESH, sampling=sweep(lower=.5e-3, upper=.6e-3))
    faces = ('bottom', 'top', 'left', 'right')
    conductor = dict(kind='surface-faces', ground_thickness=35e-6,
        conductors={'signal': {face: metal() for face in faces}},
        reference=dict(kind='surfaces', bottom=metal(), top=metal(), sides=None,
            conductors={'ground_left': dict(kind='faces', bottom=metal(), top=metal(58e6/4),
                left=metal(), right=metal()), 'ground_right': metal()}))
    direct = TransmissionLineDocument(CrossSectionDocument(coplanar_stripline(**source.to_dict()['parameters']),
        mesh=MESH), [1e9], materials={}, conductor=conductor, length=0., schema='sipi.transmission-line/6')
    target = direct.analyze().propagation().z_characteristic[0, 0].real
    result = LineQuantityDesignDocument(source, conductor=conductor, quantity='impedance_real',
        target=float(target), tolerance=.5, max_evaluations=3).solve()
    assert result.parameter == .5e-3 and len(result.history) == 3
    assert 'reference:ground:ground_left:top' in result.result.conductor.boundary_labels
    assert result.document.to_dict()['conductor'] == direct.to_dict()['conductor']


def test_normalization_detached_no_field_or_source_study(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('normalization performed calculation')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', forbidden)
    original = study(); before = original.dumps(); doc = document(); raw = doc.to_dict()
    restored = LineQuantityDesignDocument.from_dict(raw)
    raw['study']['parameters']['width'] = 1.
    assert restored.dumps() == doc.dumps() == normalize_saved(doc.dumps())
    assert original.dumps() == before
    assert 'sipi.line-quantity-design/1' in saved_schemas()


def test_shared_execution_preserves_goal_snapshots_and_units(monkeypatch):
    install_fake(monkeypatch)
    raw = document().to_dict(); raw.update(target=2., tolerance=.01)
    doc = LineQuantityDesignDocument.from_dict(raw)
    expected = doc.solve().to_dict()
    actual = execute_saved(doc.dumps(), max_evaluations=24)
    assert actual['status'] == 'complete' and actual['result'] == expected
    assert actual['input'] == doc.to_dict() and actual['result']['unit'] == 'ohm'
    json.dumps(actual, allow_nan=False)


@pytest.mark.parametrize('mode', ['budget', 'diagnostics'])
def test_caller_controls_reject_before_field_or_source_solve(monkeypatch, mode):
    def forbidden(*args, **kwargs): pytest.fail('rejected execution performed calculation')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    monkeypatch.setattr(LineQuantityDesignDocument, 'solve', forbidden)
    with pytest.raises(ValueError):
        execute_saved(document().dumps(), **(dict(max_evaluations=23) if mode == 'budget'
                                            else dict(diagnostics=['characteristic'])))


@pytest.mark.parametrize('mode', ['bracket', 'extraction', 'refinement', 'skin'])
def test_execution_keeps_failure_evidence_and_no_success_result(monkeypatch, mode):
    calls = install_fake(monkeypatch, refined_offset=100. if mode == 'refinement' else 0.,
                         broken='extraction' if mode == 'extraction' else None)
    raw = document().to_dict(); raw.update(target=2., tolerance=.01)
    if mode == 'bracket': raw['target'] = 100.
    if mode == 'skin':
        raw['study']['sampling'] = sweep('thickness', 5e-6, 50e-6)
    actual = execute_saved(LineQuantityDesignDocument.from_dict(raw).dumps())
    assert actual['status'] == 'failed' and actual['result'] is None
    error = actual['error']; assert error['unit'] == 'ohm'
    expected = {'bracket': ('bracket', 2, 2), 'extraction': ('search/extraction', 1, 0),
                'refinement': ('refinement/acceptance', None, None), 'skin': ('search/factory', 1, 0)}[mode]
    assert error['stage'] == expected[0]
    if expected[1] is not None:
        assert error['attempts'] == expected[1] and len(error['history']) == expected[2]
    else:
        assert error['attempts'] == len(error['history']) and error['history'][-1]['stage'] == 'refinement'
    assert error['cause_type'] == ('ArithmeticError' if mode == 'extraction' else 'ValueError' if mode == 'skin' else None)
    if mode == 'skin': assert not calls and error['failed_parameter'] == 5e-6
    json.dumps(actual, allow_nan=False)


def test_independent_skrf_saved_goal_propagation(solved):
    skrf = require_tool('scikit-rf'); clock = Stopwatch(); line = solved[1].result
    with clock('openphysics'): actual = line.propagation()
    with clock('reference'):
        medium = skrf.media.DistributedCircuit(skrf.Frequency.from_f(line.frequency, unit='hz'),
            R=line.R[:, 0, 0], L=line.L[:, 0, 0], G=line.G[:, 0, 0], C=line.C[:, 0, 0])
        z, gamma = medium.z0, medium.gamma
    errors = [float(np.max(abs(actual.z_characteristic[:, 0]/z-1))),
              float(np.max(abs(actual.gamma[:, 0]/gamma-1)))]
    record = make_record(case='saved-lossy-goal-propagation', physics='uniform scalar lossy line',
        api='sipi.line_goal_document.LineQuantityDesignDocument', discretization='saved source and bounded lossy goal',
        tool='scikit-rf', tool_discretization='DistributedCircuit from identical extracted RLGC',
        matched=['same scalar RLGC, positive frequency, complex forward impedance and propagation'],
        not_matched=['field search excluded from timings; field accuracy and empirical material fitting not established'],
        observables=[observable(n, u, 'relative difference', e, 1e-10)
            for n, u, e in zip(('Zc', 'gamma'), ('ohm', '1/m'), errors)],
        analytical_acceptance='closed-form homogeneous attenuation; previous API Cohn/mesh/box evidence', stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors) < 1e-10


@pytest.mark.parametrize('case', ['schema', 'missing', 'extra', 'quantity', 'target', 'zero_target',
    'tolerance', 'budget', 'study_schema', 'study_quantity', 'pair', 'no_frequency', 'dc', 'count',
    'multivariable', 'corners', 'zero_bound', 'equal_bounds', 'bad_endpoint_geometry',
    'unknown_conductor', 'missing_roughness', 'extra_conductor', 'nominal_skin'])
def test_strict_input_rejection_before_mesh(monkeypatch, case):
    raw = document().to_dict(); source = raw['study']
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-design/3'
    if case == 'missing': del raw['target']
    if case == 'extra': raw['unknown'] = 0
    if case == 'quantity': raw['quantity'] = 'z0'
    if case == 'target': raw['target'] = True
    if case == 'zero_target': raw['target'] = 0
    if case == 'tolerance': raw['tolerance'] = 0
    if case == 'budget': raw['max_evaluations'] = 2
    if case == 'study_schema':
        source['schema'] = 'sipi.impedance-study/1'
        del source['material_evaluation']; del source['fixed_plane_spacing_m']
    if case == 'study_quantity': source['quantity'] = 'z_diff'
    if case == 'pair':
        raw['study'] = ImpedanceStudyDocument('coupled_microstrip',
            dict(width=.5e-3, gap=.3e-3, substrate_height=1e-3, eps_r=4.),
            quantity='z_diff', frequency=1e9, materials={}, mesh=MESH, sampling=sweep()).to_dict()
    if case == 'no_frequency': del source['material_evaluation']
    if case == 'dc': source['material_evaluation']['frequency_hz'] = 0
    if case == 'count': source['sampling']['count'] = 3
    if case == 'multivariable': source['sampling']['variables'].append(dict(name='thickness', lower=30e-6, upper=50e-6))
    if case == 'corners':
        source['sampling']['kind'] = 'corners'; del source['sampling']['count']
    if case == 'zero_bound': source['sampling']['variables'][0]['lower'] = 0
    if case == 'equal_bounds': source['sampling']['variables'][0]['upper'] = .3e-3
    if case == 'bad_endpoint_geometry': source['sampling']['variables'][0]['upper'] = 5e-3
    if case == 'unknown_conductor': raw['conductor']['kind'] = 'unknown'
    if case == 'missing_roughness': del raw['conductor']['roughness']
    if case == 'extra_conductor': raw['conductor']['extra'] = 0
    if case == 'nominal_skin': raw['conductor']['conductivity'] = 1e4
    def forbidden(*args, **kwargs): pytest.fail('invalid input reached meshing')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): LineQuantityDesignDocument.from_dict(raw)


@pytest.mark.parametrize('text', ['{"schema":1,"schema":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_duplicate_and_nonfinite_json_rejects(text):
    with pytest.raises(ValueError): LineQuantityDesignDocument.loads(text)
