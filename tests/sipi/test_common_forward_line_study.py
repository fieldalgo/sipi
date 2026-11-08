# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Common-current sampling: independent matrices, convergence and failed rows."""
import json
import statistics

import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument
from sipi.templates import coupled_stripline
from sipi.dielectric import ConstantDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from test_common_forward_goal_document import source as pair_source
from test_common_forward_line_goal import MESH, QUANTITY, document as api_document, synthetic, reference_record
from test_line_study import document as scalar_document
from test_line_goal import install_fake
from crosscheck import require_tool, Stopwatch

SCHEMA = 'sipi.line-quantity-study/3'


def document():
    source = pair_source().to_dict()
    source['sampling'].update(count=3, variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)])
    return LineQuantityStudyDocument(source, conductor=api_document().to_dict()['conductor'],
                                      quantity=QUANTITY, schema=SCHEMA)


@pytest.fixture(scope='module')
def width_result():
    doc = document()
    return doc, doc.analyze()


def test_real_asymmetric_width_samples_replay_direct_lines_and_statistics(width_result):
    doc, result = width_result
    assert not result.failed and result.quantity == QUANTITY and result.unit == 'ohm'
    assert [row.index for row in result.rows] == list(range(len(result.rows)))
    values = []
    for row, width in zip(result.rows, doc.samples()[:, 0]):
        raw = api_document(width).to_dict(); raw['schema'] = 'sipi.transmission-line/6'
        direct = TransmissionLineDocument.from_dict(raw); line = direct.analyze()
        assert row.input_json == direct.dumps() and row.phase == 'complete'
        for key in ('R', 'L', 'G', 'C'):
            np.testing.assert_allclose(getattr(row.result, key), getattr(line, key), rtol=1e-10)
        np.testing.assert_allclose(row.result.characteristic().z_characteristic,
                                   line.characteristic().z_characteristic, rtol=1e-10)
        mixed = line.characteristic().mixed_mode().z_characteristic[0]
        assert row.value == pytest.approx(mixed[1, 1].real, rel=1e-10)
        assert abs(mixed[0, 1]) > 1e-3 and abs(mixed[1, 1].imag) > .1
        traces = raw['cross_section']['traces']
        assert traces[1]['x']-traces[0]['x'] == pytest.approx(.95e-3, rel=1e-12)
        values.append(row.value)
    ordered = sorted(values)
    def quantile(q):
        position = (len(values)-1)*q; i = int(position); fraction = position-i
        return ordered[i]*(1-fraction)+ordered[min(i+1, len(values)-1)]*fraction
    expected = dict(minimum=min(values), maximum=max(values), mean=statistics.mean(values),
        sample_std=statistics.stdev(values), p05=quantile(.05), p95=quantile(.95))
    for key, value in expected.items(): assert result.summary[key] == pytest.approx(value, rel=1e-12)
    assert result.input_json == doc.dumps() and result.variable_names == ('left_width',)


def test_each_asymmetric_sample_against_independent_forward_eigenspace(width_result):
    scipy = require_tool('scipy'); clock = Stopwatch(); errors = dict(Zc=0., Zcc=0.)
    for row in width_result[1].rows:
        line = row.result
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
            u = np.array([.5, .5])
        errors['Zc'] = max(errors['Zc'], float(abs(actual-expected).max()/abs(expected).max()))
        errors['Zcc'] = max(errors['Zcc'], float(abs(u@(actual-expected)@u)/abs(u@expected@u)))
    reference_record('common-line-study-forward-eigenspaces', 'scipy',
        'balanced 2N voltage/current eigenspace at each sampled RLGC', errors, clock)


def test_joint_material_corners_match_analytic_complex_scaling_and_exact_snapshots():
    parameters = dict(width=.3e-3, gap=.2e-3, plane_spacing=1e-3, eps_r=1.,
                      thickness=50e-6, box_width=6e-3)
    field=CrossSectionDocument(coupled_stripline(**parameters),mesh=MESH).analyze()
    ls=np.max(abs(field.L));cs=np.max(abs(field.C))
    values,vectors=np.linalg.eigh(field.L/ls);half=(vectors*np.sqrt(values))@vectors.T
    values,vectors=np.linalg.eigh(half@(field.C/cs)@half)
    zc=np.sqrt(ls/cs)*half@(vectors*(1/np.sqrt(values)))@vectors.T@half
    np.testing.assert_allclose(zc@field.C@zc,field.L,rtol=1e-10,atol=1e-20)
    u=np.array([.5,.5]);vacuum=float(u@zc@u)
    source = ImpedanceStudyDocument('coupled_stripline', parameters, quantity='z_diff_forward',
        frequency=1e9, materials={'dielectric': ConstantDielectric(4., .02)}, mesh=MESH,
        material_variables={'dk': dict(region='dielectric', path=['eps_r']),
                            'loss': dict(region='dielectric', path=['tan_delta'])},
        sampling=dict(kind='corners', variables=[dict(name='dk', lower=3., upper=5.),
                                                dict(name='loss', lower=0., upper=.04)]))
    doc = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'), quantity=QUANTITY, schema=SCHEMA)
    result = doc.analyze(); assert not result.failed and len(result.rows) == 4
    np.testing.assert_array_equal(doc.samples(), source.samples())
    for row, (eps, loss), evaluation in zip(result.rows, source.samples(), source.sample_material_evaluations()):
        expected = vacuum/np.sqrt(eps*(1-1j*loss))
        assert row.value == pytest.approx(expected.real, rel=1e-10)
        assert row.result.characteristic().mixed_mode().z_characteristic[0, 1, 1] == pytest.approx(expected, rel=1e-10)
        assert row.to_dict()['material_evaluation'] == evaluation
        assert row.to_dict()['input']['materials'] == evaluation['materials']
        assert row.sample_values == (eps, loss)
    json.dumps(result.to_dict(), allow_nan=False)


def test_correlated_normal_keeps_invalid_widths_and_gap_then_continues(monkeypatch):
    raw = pair_source().to_dict()
    raw['sampling'] = dict(kind='normal', count=8, seed=3, correlation=[[1., .5], [.5, 1.]],
        variables=[dict(name='left_width', mean=.6e-3, std=.5e-3),
                   dict(name='right_width', mean=.5e-3, std=.3e-3)])
    source = ImpedanceStudyDocument.from_dict(raw)
    doc = LineQuantityStudyDocument(source, conductor=api_document().to_dict()['conductor'],
                                     quantity=QUANTITY, schema=SCHEMA)
    calls = synthetic(monkeypatch); result = doc.analyze()
    assert result.failed == 3 and result.summary is None and len(calls) == 5
    assert [row.index for row in result.rows] == list(range(8))
    assert [row.index for row in result.rows if not row.complete] == [0, 3, 4]
    np.testing.assert_array_equal([row.sample_values for row in result.rows], source.samples())
    for row, parameters in zip(result.rows, source.sample_parameters()):
        assert row.to_dict()['parameters'] == parameters
        invalid = parameters['left_width'] <= 0 or parameters['right_width'] <= 0 or parameters['gap'] <= 0
        assert row.complete != invalid
        if invalid:
            assert row.phase == 'input' and row.input_json is None and row.value is None
        else:
            assert row.phase == 'complete' and row.value > 0
    report = execute_saved(doc.dumps())
    assert report['status'] == 'incomplete' and report['result'] == result.to_dict()
    assert len(report['result']['rows']) == 8
    json.dumps(report, allow_nan=False)


def test_fixed_stack_height_inputs_preserved_without_source_analysis(monkeypatch):
    source = ImpedanceStudyDocument('coupled_layered_stripline',
        dict(width=.3e-3, gap=.2e-3, lower_height=.4e-3, upper_height=.6e-3,
             lower_eps_r=3., upper_eps_r=5., thickness=35e-6, box_width=4e-3),
        quantity='z_diff_forward', frequency=1e9, materials={}, mesh=MESH,
        fixed_plane_spacing_m=1e-3, sampling=dict(kind='sweep', count=3,
            variables=[dict(name='lower_height', lower=.3e-3, upper=.5e-3)]))
    def forbidden(*args, **kwargs): pytest.fail('source study was analyzed')
    monkeypatch.setattr(ImpedanceStudyDocument, 'analyze', forbidden)
    synthetic(monkeypatch)
    result = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'),
        quantity=QUANTITY, schema=SCHEMA).analyze()
    assert not result.failed
    for row, parameters in zip(result.rows, source.sample_parameters()):
        assert row.to_dict()['parameters'] == parameters
        assert parameters['lower_height']+parameters['upper_height'] == pytest.approx(1e-3, rel=1e-12)
        layers = row.to_dict()['input']['cross_section']['layers']
        assert layers[0]['thickness'] == parameters['lower_height']
        assert layers[1]['thickness'] == parameters['upper_height']


@pytest.mark.parametrize('broken', ['diagnostic', 'names', 'frequency', 'basis'])
def test_characteristic_failures_preserve_all_inputs_and_later_attempts(monkeypatch, broken):
    calls = synthetic(monkeypatch, broken=broken)
    result = document().analyze()
    assert len(calls) == len(result.rows) == result.failed == 3 and result.summary is None
    assert all(row.phase == 'diagnostic' and row.value is None and row.input_json for row in result.rows)
    assert all(row.error_type == ('ArithmeticError' if broken == 'diagnostic' else 'ValueError') for row in result.rows)


def test_middle_extraction_failure_keeps_both_successful_neighbors(monkeypatch):
    synthetic(monkeypatch); old = TransmissionLineDocument.analyze; attempts = []
    def analyze(self):
        attempts.append(self.dumps())
        if len(attempts) == 2: raise ArithmeticError('middle sample failure')
        return old(self)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', analyze)
    result = document().analyze()
    assert len(attempts) == 3 and result.failed == 1 and result.summary is None
    assert [row.complete for row in result.rows] == [True, False, True]
    assert result.rows[1].phase == 'extraction' and result.rows[1].input_json == attempts[1]


@pytest.mark.parametrize('quantity', ['impedance_real', 'attenuation'])
def test_explicit_scalar_v3_matches_v1_and_preserves_default(monkeypatch, quantity):
    install_fake(monkeypatch)
    old = scalar_document(quantity)
    raw = old.to_dict(); raw['schema'] = SCHEMA
    changed = LineQuantityStudyDocument.from_dict(raw)
    assert changed.analyze().to_dict() == old.analyze().to_dict()
    assert old.to_dict()['schema'] == 'sipi.line-quantity-study/1'


def test_shared_complete_report_roundtrip_and_budget_before_fields(monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('normalization or rejected budget invoked fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    doc = document(); assert normalize_saved(doc.dumps()) == doc.dumps() and SCHEMA in saved_schemas()
    with pytest.raises(ValueError, match='sample count'): doc.analyze(max_evaluations=2)
    with pytest.raises(ValueError, match='sample count'): execute_saved(doc.dumps(), max_evaluations=2)
    with pytest.raises(ValueError, match='diagnostics'): execute_saved(doc.dumps(), diagnostics=['characteristic'])
    synthetic(monkeypatch)
    expected = doc.analyze().to_dict(); report = execute_saved(doc.dumps())
    assert report['status'] == 'complete' and report['result'] == expected
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('case', ['v1', 'v2', 'schema', 'modal_source', 'scalar_source', 'scalar_quantity',
    'quantity', 'missing', 'extra', 'dc', 'wrong_conductor', 'bad_endpoint'])
def test_strict_pair_contract_before_mesh(monkeypatch, case):
    raw = document().to_dict()
    if case == 'v1': raw['schema'] = 'sipi.line-quantity-study/1'
    if case == 'v2': raw['schema'] = 'sipi.line-quantity-study/2'
    if case == 'schema': raw['schema'] = 'sipi.line-quantity-study/999'
    if case == 'modal_source':
        raw['study'] = ImpedanceStudyDocument('coupled_stripline', dict(width=.3e-3, gap=.2e-3,
            plane_spacing=1e-3, eps_r=4.), quantity='z_diff', frequency=1e9, materials={}, mesh=MESH,
            sampling=dict(kind='sweep', count=3, variables=[dict(name='width', lower=.2e-3, upper=.4e-3)])).to_dict()
    if case == 'scalar_source': raw['study'] = scalar_document().to_dict()['study']
    if case == 'scalar_quantity': raw['quantity'] = 'impedance_real'
    if case == 'quantity': raw['quantity'] = 'differential_attenuation'
    if case == 'missing': del raw['quantity']
    if case == 'extra': raw['launch'] = 'common'
    if case == 'dc': raw['study']['material_evaluation']['frequency_hz'] = 0.
    if case == 'wrong_conductor': raw['conductor']['conductors']['unexpected'] = raw['conductor']['conductors'].pop('positive')
    if case == 'bad_endpoint': raw['study']['sampling']['variables'][0]['upper'] = 2e-3
    def forbidden(*args, **kwargs): pytest.fail('invalid paired input reached fields')
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    with pytest.raises(ValueError): LineQuantityStudyDocument.from_dict(raw)


def test_each_width_has_separate_mesh_and_finite_outer_convergence(width_result):
    for row,width in zip(width_result[1].rows,width_result[0].samples()[:,0]):
        refined=json.loads(row.input_json)
        for key in ('edge_size','far_size','grade'):refined['cross_section']['mesh'][key]/=2
        refined_value=float(TransmissionLineDocument.from_dict(refined).analyze().characteristic().mixed_mode().z_characteristic[0,1,1].real)
        assert abs(refined_value/row.value-1)<=.005
        previous=refined_value;changes=[];records=[]
        for box,air in [(36e-3,15e-3),(48e-3,20e-3)]:
            raw=api_document(width,box=box,air=air).to_dict();raw['schema']='sipi.transmission-line/6'
            raw['cross_section']['mesh']=refined['cross_section']['mesh']
            value=float(TransmissionLineDocument.from_dict(raw).analyze().characteristic().mixed_mode().z_characteristic[0,1,1].real)
            assert abs(value/refined_value-1)<=.005
            changes.append(abs(value-previous));previous=value
            records.append(dict(box_m=box,air_m=air,value=value,relative_change=abs(value/refined_value-1)))
        assert changes[1]<changes[0]
        print(json.dumps(dict(case='common-study-width-convergence',width_m=float(width),requested=row.value,refined=refined_value,outer=records,successive_changes=changes)))


def test_explicit_v3_differential_study_preserves_v2_exactly(monkeypatch):
    from test_differential_line_study import document as old_document
    from test_differential_line_goal import synthetic as differential_synthetic
    differential_synthetic(monkeypatch)
    original=old_document();changed=LineQuantityStudyDocument.from_dict(dict(original.to_dict(),schema=SCHEMA))
    changed_result = changed.analyze(); original_result = original.analyze()
    assert [row.index for row in changed_result.rows] == list(range(len(changed_result.rows)))
    assert [row.index for row in original_result.rows] == list(range(len(original_result.rows)))
    assert changed_result.to_dict()==original_result.to_dict()
    np.testing.assert_array_equal(changed.samples(),original.samples())


@pytest.mark.parametrize('quantity',['impedance_real','differential_forward_impedance_real',QUANTITY])
@pytest.mark.parametrize('consumer',['assessment','saved-yield','saved-selection'])
def test_previous_yield_consumers_do_not_implicitly_admit_new_study_version(monkeypatch,quantity,consumer):
    from sipi.line_yield import assess_line_yield,LineQuantityYieldDocument
    from sipi.yield_design import YieldDesignDocument
    if quantity=='impedance_real':
        raw=scalar_document().to_dict();install_fake(monkeypatch)
    elif quantity=='differential_forward_impedance_real':
        from test_differential_line_study import document as old_document
        raw=old_document().to_dict();synthetic(monkeypatch)
    else:
        raw=document().to_dict();synthetic(monkeypatch)
    raw['schema']=SCHEMA;raw['study']['sampling'].update(kind='uniform',count=4,seed=17)
    doc=LineQuantityStudyDocument.from_dict(raw);result=doc.analyze()
    assert not result.failed and len(result.rows)==4
    assert [row.index for row in result.rows] == list(range(4))
    def forbidden(*args,**kwargs):pytest.fail('yield rejection reached fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='study/1 or /2'):
        if consumer=='assessment':assess_line_yield(result,minimum=1.)
        elif consumer=='saved-yield':LineQuantityYieldDocument(doc,minimum=1.)
        else:YieldDesignDocument([dict(name='candidate',cost=1.,study=doc.to_dict())],cost_unit='relative',minimum=1.,minimum_yield=.8,schema='sipi.yield-design/2')
