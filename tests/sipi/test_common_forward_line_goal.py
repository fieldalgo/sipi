# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit forward launch goals, independent matrix references and field gates."""
import json
from importlib import metadata
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import (asymmetric_coupled_microstrip, CrossSectionDocument,
                  rlgc_characteristic, rlgc_propagation)
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity, LineQuantityGoalError
from crosscheck import require_tool, Stopwatch, emit, make_record, observable

QUANTITY = 'common_forward_impedance_real'
MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)
T = np.array([[1., .3], [.2, 1.1]])
U = np.array([.5, .5])


def document(width=.6e-3, *, loss=.02, metal=True, box=24e-3, air=10e-3):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=.95e-3-(width+.5e-3)/2, substrate_height=.5e-3, eps_r=4., tan_delta=loss,
        left_thickness=35e-6, right_thickness=50e-6, air_height=air, box_width=box)
    def surface(sigma=58e6, rms=0.):
        return dict(conductivity=sigma, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    conductor = (dict(kind='surface-boundaries', conductors={
        'positive': surface(58e6, .5e-6), 'negative': surface(35e6, 1e-6)},
        reference=surface(), ground_thickness=35e-6) if metal else dict(kind='perfect'))
    return TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9],
        materials={}, length=0., conductor=conductor, schema='sipi.transmission-line/3')


def modal_values(x):
    diagonal = dict(R=np.array([300., 2.]), L=np.array([x*200e-9, 400e-9]),
                    G=np.array([.005, .003]), C=np.array([100e-12/x, 80e-12]))
    inverse = np.linalg.inv(T)
    matrices = {name: (T@np.diag(value)@T.T if name in ('R', 'L')
                      else inverse.T@np.diag(value)@inverse) for name, value in diagonal.items()}
    return diagonal, matrices


def synthetic(monkeypatch, *, broken=None, symmetric=False):
    calls = []
    def analyze(self):
        raw = self.to_dict(); calls.append(raw)
        x = raw['cross_section']['traces'][0]['width']/.3e-3
        _, matrices = modal_values(x)
        if symmetric:
            matrices = dict(R=np.array([[6., .4], [.4, 6.]]),
                L=np.array([[400., 80.], [80., 400.]])*1e-9,
                G=np.array([[.004, -.001], [-.001, .004]]),
                C=np.array([[100., -20.], [-20., 100.]])*1e-12)
        def characteristic():
            if broken == 'diagnostic': raise ArithmeticError('retained characteristic failure')
            names = ('changed', 'negative') if broken == 'names' else ('positive', 'negative')
            frequency = [2e9] if broken == 'frequency' else [1e9]
            result = rlgc_characteristic(frequency, **matrices, names=names)
            if broken == 'basis': return result.mixed_mode()
            return result
        def propagation(): pytest.fail('paired goal used scalar or symmetric modal propagation')
        return SimpleNamespace(frequency=np.array(raw['frequency_hz']), names=('positive', 'negative'),
            input_json=self.dumps(), characteristic=characteristic, propagation=propagation,
            **{key: value[None] for key, value in matrices.items()})
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', analyze)
    return calls


def factory(x):
    return document(x*.3e-3)


def reference_record(case, tool, tool_description, errors, clock):
    record = make_record(case=case, physics='lossy asymmetric pair forward-current launch',
        api='sipi.line_goal.seek_line_quantity', discretization='full RLGC characteristic matrix',
        tool=tool, tool_discretization=tool_description,
        matched=['same RLGC, frequency, ordered conductors and exp(+jwt) forward branch',
                 'Vc=(V1+V2)/2,Ic=I1+I2,launchId=0'],
        not_matched=['not independent geometry extraction, measured accuracy or finite terminal matching',
                     'no independent common eigenmode or downstream Id=0 assumption'],
        observables=[observable(name, 'ohm', 'max normwise relative difference', error, 1e-10)
                     for name, error in errors.items()],
        analytical_acceptance='symmetric modal and lossless forward limits; mesh and enlarged outer target gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi')); emit(record)
    assert max(errors.values()) < 1e-10


def test_goal_against_independent_nonorthogonal_modal_circuits(monkeypatch):
    skrf = require_tool('scikit-rf'); clock = Stopwatch(); calls = synthetic(monkeypatch)
    def expected(x):
        diagonal, _ = modal_values(x)
        media = [skrf.media.DistributedCircuit(skrf.Frequency.from_f([1e9], unit='hz'),
            **{name: value[i] for name, value in diagonal.items()}) for i in range(2)]
        return T@np.diag([m.z0[0] for m in media])@T.T
    with clock('reference'): target = float((U@expected(1.37)@U).real)
    factory_calls = []
    def counted(x): factory_calls.append(x); return factory(x)
    with clock('openphysics'):
        result = seek_line_quantity(counted, [.8, 2.], target, quantity=QUANTITY, tolerance=1e-7)
    with clock('reference'): zc = expected(result.parameter)
    actual = result.result.characteristic().z_characteristic[0]
    reference_record('common-forward-goal-known-modal-circuits', 'scikit-rf',
        'two DistributedCircuit media with known nonorthogonal power-dual transform',
        dict(Zc=float(abs(actual-zc).max()/abs(zc).max()),
             Zcc=float(abs(result.value-(U@zc@U).real)/abs((U@zc@U).real))), clock)
    assert result.parameter == pytest.approx(1.37, abs=1e-8)
    assert len(calls) == len(result.history) == len(factory_calls)+1
    assert result.unit == 'ohm' and 'common-forward' in result.to_dict()['scope']
    assert abs((U@zc@U).imag) > .01 and abs(abs(U@zc@U)-result.value) > 1e-4
    assert abs((np.array([1., -1.])@zc@U)) > 1e-3
    selected = result.document.to_dict(); refined = result.refined_document.to_dict()
    for key in ('edge_size', 'far_size', 'grade'): selected['cross_section']['mesh'][key] /= 2
    assert selected == refined
    json.dumps(result.to_dict(), allow_nan=False)


def test_symmetric_goal_reduces_to_existing_modal_common_value(monkeypatch):
    synthetic(monkeypatch, symmetric=True)
    line = factory(1.).analyze()
    expected = rlgc_propagation([1e9], **{key: getattr(line, key) for key in ('R', 'L', 'G', 'C')})
    target = expected.z_characteristic[0, 1].real
    result = seek_line_quantity(factory, [.8, 2.], target, quantity=QUANTITY,
                                tolerance=1e-10, max_evaluations=3)
    assert result.value == pytest.approx(target, rel=1e-10)
    assert len(result.history) == 3


@pytest.fixture(scope='module')
def finite_goal():
    return seek_line_quantity(document, [.2e-3, 1e-3], 40., quantity=QUANTITY,
                              tolerance=.125, max_evaluations=24)


def test_real_asymmetric_goal_refinement_and_outer_domain(finite_goal):
    result = finite_goal
    assert max(abs(result.residual), abs(result.refined_residual)) <= .125
    previous = result.refined_value
    changes = []
    outer_study = []
    for box, air in [(36e-3, 15e-3), (48e-3, 20e-3)]:
        outer = document(result.parameter, box=box, air=air).to_dict()
        outer['cross_section']['mesh'] = result.refined_document.to_dict()['cross_section']['mesh']
        outer_value = TransmissionLineDocument.from_dict(outer).analyze().characteristic().mixed_mode().z_characteristic[0, 1, 1].real
        assert abs(outer_value-result.target) <= .125
        assert abs(outer_value/result.refined_value-1) <= .005
        changes.append(abs(outer_value-previous))
        outer_study.append(dict(box_m=box, air_m=air, value=float(outer_value), successive_change=float(changes[-1])))
        previous = outer_value
    assert changes[1] < changes[0]
    mixed = result.result.characteristic().mixed_mode()
    assert abs(mixed.z_characteristic[0, 0, 1]) > 1e-3
    assert result.result.R[0, 0, 0] > 0 and result.result.G[0, 0, 0] > 0
    with pytest.raises(ValueError, match='exchange-symmetric'): result.result.propagation()
    replay = result.document.analyze()
    for key in ('R', 'L', 'G', 'C'):
        np.testing.assert_allclose(getattr(replay, key), getattr(result.result, key), rtol=1e-10)
    np.testing.assert_allclose(replay.characteristic().z_characteristic,
        result.result.characteristic().z_characteristic, rtol=1e-10)
    print(json.dumps(dict(case='asymmetric-lossy-goal', width_m=result.parameter,
        requested_residual_ohm=result.residual, refined_residual_ohm=result.refined_residual,
        outer_residual_ohm=float(outer_value-result.target),
        outer_relative_change=float(abs(outer_value/result.refined_value-1)), outer_study=outer_study)))


def test_independent_telegrapher_forward_eigenspace(finite_goal):
    scipy = require_tool('scipy'); clock = Stopwatch(); line = finite_goal.result
    with clock('openphysics'): actual = line.characteristic().z_characteristic[0]
    with clock('reference'):
        omega = 2*np.pi*line.frequency[0]
        z = line.R[0]+1j*omega*line.L[0]; y = line.G[0]+1j*omega*line.C[0]
        scale = np.sqrt(abs(z).max()/abs(y).max())
        block = np.block([[np.zeros_like(z), z/scale], [scale*y, np.zeros_like(y)]])
        roots, vectors = scipy.linalg.eig(block)
        selected = roots.imag > 0
        assert np.count_nonzero(selected) == 2 and np.all(roots[selected].real >= 0)
        forward = vectors[:, selected]
        reference = scale*forward[:2]@np.linalg.inv(forward[2:])
    reference_record('common-forward-goal-telegrapher-eigenspace', 'scipy',
        'balanced 2N voltage/current telegrapher eigenspace, positive-phase roots',
        dict(Zc=float(abs(actual-reference).max()/abs(reference).max()),
             Zcc=float(abs(U@(actual-reference)@U)/abs(U@reference@U))), clock)


def test_lossless_asymmetric_goal_matches_independent_spd_geometric_mean():
    doc=document(.6e-3,loss=0.,metal=False);line=doc.cross_section.analyze()
    ls=np.max(abs(line.L));cs=np.max(abs(line.C));values,vectors=np.linalg.eigh(line.L/ls)
    half=(vectors*np.sqrt(values))@vectors.T
    values,vectors=np.linalg.eigh(half@(line.C/cs)@half)
    zc=np.sqrt(ls/cs)*half@(vectors*(1/np.sqrt(values)))@vectors.T@half
    np.testing.assert_allclose(zc@line.C@zc,line.L,rtol=1e-10,atol=1e-20)
    expected=float(U@zc@U)
    result=seek_line_quantity(lambda width:document(width,loss=0.,metal=False),[.6e-3,.8e-3],expected,quantity=QUANTITY,tolerance=.125,max_evaluations=3)
    assert result.parameter==.6e-3 and result.value==pytest.approx(expected,rel=1e-10)
    assert abs(result.result.characteristic().mixed_mode().z_characteristic[0,1,1].imag)<1e-10


@pytest.mark.parametrize('broken', ['diagnostic', 'names', 'frequency', 'basis'])
def test_diagnostic_failure_keeps_failed_snapshot_and_attempt(monkeypatch, broken):
    synthetic(monkeypatch, broken=broken)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(factory, [.8, 2.], 100., quantity=QUANTITY, tolerance=.5)
    error = caught.value
    assert error.attempts == 1 and error.history == () and error.stage == 'search/diagnostic'
    assert error.input_json and error.__cause__ is not None
    assert error.cause_type == ('ArithmeticError' if broken == 'diagnostic' else 'ValueError')


@pytest.mark.parametrize('case', ['single', 'dc', 'grid', 'length', 'frequency_change', 'order_change'])
def test_pair_contract_rejects_before_invalid_input_field_solve(monkeypatch, case):
    calls = synthetic(monkeypatch)
    def changed(x):
        raw = factory(x).to_dict()
        if case == 'single':
            from test_line_goal import document as scalar
            return scalar()
        if case == 'dc':
            raw['frequency_hz'] = [0.]
            raw['conductor'] = dict(kind='perfect')
        if case == 'grid': raw['frequency_hz'] = [1e9, 2e9]
        if case == 'length': raw['length_m'] = .1
        if case == 'frequency_change' and x == 2.: raw['frequency_hz'] = [2e9]
        if case == 'order_change' and x == 2.: raw['cross_section']['traces'].reverse()
        return TransmissionLineDocument.from_dict(raw)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(changed, [.8, 2.], 100., quantity=QUANTITY, tolerance=.5)
    completed = 1 if case.endswith('change') else 0
    assert len(calls) == len(caught.value.history) == completed
    assert caught.value.attempts == completed+1 and caught.value.stage == 'search/validation'


@pytest.mark.parametrize('stage', ['budget', 'refinement'])
def test_pair_budget_and_refinement_failure_retain_prior_rows(monkeypatch, stage):
    calls = synthetic(monkeypatch); old = TransmissionLineDocument.analyze
    def analyze(self):
        if self.cross_section.mesh_options['edge_size'] == MESH['edge_size']/2:
            raise ArithmeticError('refinement extraction failed')
        return old(self)
    if stage == 'refinement': monkeypatch.setattr(TransmissionLineDocument, 'analyze', analyze)
    first = factory(.8).analyze().characteristic().mixed_mode().z_characteristic[0, 1, 1].real
    calls.clear()
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(factory, [.8, 2.], first if stage == 'refinement' else first+1,
            quantity=QUANTITY, tolerance=1e-10, max_evaluations=3)
    error = caught.value
    assert len(error.history) == 2 and error.attempts == (3 if stage == 'refinement' else 2)
    assert error.stage == ('refinement/extraction' if stage == 'refinement' else 'budget')


@pytest.mark.parametrize('kind', ['design', 'study'])
def test_scalar_saved_v1_does_not_implicitly_accept_new_pair_quantity(kind):
    if kind == 'design':
        from test_line_goal_document import document as saved
        from sipi.line_goal_document import LineQuantityDesignDocument as cls
    else:
        from test_line_study import document as saved
        from sipi.line_study import LineQuantityStudyDocument as cls
    raw = saved().to_dict(); raw['quantity'] = QUANTITY
    with pytest.raises(ValueError, match='quantity'): cls.from_dict(raw)


@pytest.mark.parametrize('kind',['design','study'])
def test_previous_paired_saved_version2_does_not_implicitly_accept_common_goal(kind):
    if kind=='design':
        from test_differential_goal_document import document as saved
        from sipi.line_goal_document import LineQuantityDesignDocument as cls
    else:
        from test_differential_line_study import document as saved
        from sipi.line_study import LineQuantityStudyDocument as cls
    raw=saved().to_dict();raw['quantity']=QUANTITY
    with pytest.raises(ValueError,match='quantity'):cls.from_dict(raw)


def test_original25ohm_physical_fixture_retains_unbracketed_history():
    def original(w):
        raw=document(w,box=12e-3,air=5e-3).to_dict()
        raw['cross_section']['mesh']['far_size']=.125e-3
        return TransmissionLineDocument.from_dict(raw)
    with pytest.raises(LineQuantityGoalError) as caught:
        seek_line_quantity(original,[.2e-3,1e-3],25.,quantity=QUANTITY,tolerance=.125,max_evaluations=24)
    error=caught.value
    assert error.stage=='bracket' and error.attempts==2 and len(error.history)==2
    assert [row.parameter for row in error.history]==[.2e-3,1e-3]
    assert all(row.value>25. and row.stage=='search' and row.input_json for row in error.history)
