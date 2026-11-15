# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite two-ground manufacturing grids and independent physical observations."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
import json
import numpy as np
import pytest
from scipy.linalg import sqrtm

from sipi import CrossSection, rlgc_characteristic
from sipi.dielectric import DebyeDielectric, dielectric_to_dict
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line, TwoGroundPanelLineError
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument as Document
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject
from test_execution_record import ARTIFACTS
from test_two_ground_pair_study import document as single_document
from test_sampled_panel_pair_goal import modal, targets, T
from test_panel_pair_study import expected_statistics, Q

F = [1e9, 2e9, 5e9]


def document(sampling=None, frequencies=F, *, physical=False):
    raw = single_document(sampling, physical=physical).to_dict()
    return Document(raw['study'], frequencies=list(frequencies), conductors=raw['conductors'],
        reference=raw['reference'], ground_thickness=raw['ground_thickness_m'], **raw['panel'])


def synthetic(monkeypatch, *, lossless=False, fail_at=None, interrupt=False):
    calls = []
    def analyze(self):
        calls.append(self.dumps())
        if len(calls) == fail_at:
            if interrupt:
                raise KeyboardInterrupt()
            cause = ArithmeticError('original current batch refusal')
            raise TwoGroundPanelLineError(cause, stage='current', input_json=self.dumps(),
                factors=None, settings=self.current_options, mesh_observation=None) from cause
        traces = self.cross_section.section.traces
        x = traces[0].width/.3e-3
        y = (traces[1].x0-traces[0].x1)/.2e-3
        f = np.array(self.to_dict()['frequency_hz'])
        matrices, _ = modal(x, y, f, lossless)
        return SimpleNamespace(input_json=self.dumps(), frequency=f, names=('positive','negative'),
            characteristic=lambda: rlgc_characteristic(f, **matrices, names=('positive','negative')),
            current_record=lambda: dict(kind='test-only-synthetic'),
            mesh_record=lambda: dict(kind='test-only-synthetic'),
            **{key: np.broadcast_to(value, (len(f),2,2)).copy() for key,value in matrices.items()})
    monkeypatch.setattr(Line, 'analyze', analyze)
    return calls


@pytest.mark.parametrize('lossless', [False, True])
def test_each_sample_has_one_atomic_grid_with_independent_statistics(monkeypatch, lossless):
    calls = synthetic(monkeypatch, lossless=lossless)
    doc = document(); result = doc.analyze(max_evaluations=4)
    assert not result.failed and len(calls) == len(result.rows) == 4
    assert result.frequencies == tuple(F) and result.variable_names == ('width','gap')
    for row,values in zip(result.rows, doc.samples()):
        np.testing.assert_allclose(row.values, targets(values[0]/.3e-3, values[1]/.2e-3,
            frequencies=F, lossless=lossless), rtol=1e-12, atol=0)
        assert row.input_json == calls[row.index] == row.result.input_json
        assert json.loads(row.input_json)['frequency_hz'] == F
        assert row.to_dict()['current_solver'] == row.to_dict()['dielectric_mesh'] == dict(kind='test-only-synthetic')
    for j in range(len(F)):
        for i,q in enumerate(Q):
            for key,value in expected_statistics([r.values[j][i] for r in result.rows]).items():
                assert result.summary[q][j][key] == pytest.approx(value, rel=1e-12)
    with pytest.raises(FrozenInstanceError): result.rows[0].index = 99
    with pytest.raises(TypeError): result.summary[Q[0]][0]['mean'] = 0


def test_independent_skrf_modes_at_every_frequency(monkeypatch):
    import skrf
    synthetic(monkeypatch)
    result = document().analyze(max_evaluations=4)
    transform = np.array([[1.,-1.],[.5,.5]])
    for row in result.rows:
        scales = np.array(row.sample_values)/[.3e-3,.2e-3]
        data = dict(R=np.array([300.,2.])*scales, L=np.array([200e-9,400e-9])*scales,
                    G=np.array([.005,.003])/scales, C=np.array([100e-12,80e-12])/scales)
        media = [skrf.media.DistributedCircuit(skrf.Frequency.from_f(F,unit='hz'),
                    **{key:value[i] for key,value in data.items()}) for i in range(2)]
        matrix = np.array([T@np.diag([m.z0[j] for m in media])@T.T for j in range(len(F))])
        np.testing.assert_allclose(row.values, np.diagonal(transform@matrix@transform.T,
            axis1=1,axis2=2).real, rtol=1e-12, atol=0)


def test_maximum_grid_keeps_row_budget(monkeypatch):
    calls = synthetic(monkeypatch)
    result = document(frequencies=np.geomspace(F[0],F[-1],64)).analyze(max_evaluations=4)
    assert len(calls) == 4 and not result.failed and len(result.summary[Q[0]]) == 64


def test_normalization_and_project_restore_are_field_free(monkeypatch):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a,**k: pytest.fail('preparation meshed'))
    monkeypatch.setattr(Line, 'analyze', lambda *a,**k: pytest.fail('preparation solved'))
    doc = document(); text = doc.dumps()
    assert normalize_saved(text) == Document.loads(text).dumps() == text
    raw = doc.to_dict(); raw['frequency_hz'].reverse()
    assert doc.dumps() == text
    request = SavedExecutionRequest(text)
    project = SavedProject(request, project_id='finite-grid', design_id='a', title='Grid', label='Source')
    assert SavedProject.loads(project.dumps()).prepare('a').request_id == request.request_id


@pytest.mark.parametrize('where', ['root','study','sampling','panel','conductors','top'])
@pytest.mark.parametrize('kind', ['missing','extra'])
def test_strict_nested_fields(where, kind):
    raw = document().to_dict()
    target = {'root':raw,'study':raw['study'],'sampling':raw['study']['sampling'],
              'panel':raw['panel'],'conductors':raw['conductors'],'top':raw['reference']['top']}[where]
    if kind == 'missing': target.pop(next(iter(target)))
    else: target['extra'] = 1
    with pytest.raises((ValueError,TypeError)): Document.from_dict(raw)


@pytest.mark.parametrize('frequencies', [[],[1e9],[1e9,1e9],[2e9,1e9],[0,1e9],[-1,1e9],
    [[1e9,2e9]],[1e9,float('inf')],list(np.geomspace(1e9,5e9,65)),[2e9,5e9]])
def test_invalid_grid_rejected_without_fields(monkeypatch, frequencies):
    monkeypatch.setattr(Line, 'analyze', lambda *a,**k: pytest.fail('invalid grid solved'))
    with pytest.raises((ValueError,TypeError)): document(frequencies=frequencies)


@pytest.mark.parametrize('kind', ['schema','duplicate','nan','source','scalar'])
def test_reject_invalid_saved_contract(kind):
    raw = document().to_dict(); text = None
    if kind == 'schema': raw['schema'] += 'unknown'
    if kind == 'duplicate': text = json.dumps(raw).replace('"ground_modes": 128','"ground_modes": 128, "ground_modes": 128')
    if kind == 'nan': text = json.dumps(raw).replace('"ground_modes": 128','"ground_modes": NaN')
    if kind == 'source': raw['study']['schema'] = 'sipi.impedance-study/1'
    if kind == 'scalar': raw['study']['quantity'] = 'z0'
    with pytest.raises((ValueError,TypeError)): Document.loads(text or json.dumps(raw))


@pytest.mark.parametrize('phase', ['parameters','materials','input','extraction','diagnostic'])
def test_failed_grid_is_one_unknown_with_later_rows_preserved(monkeypatch, phase):
    import sipi.sampled_panel_pair_study as shared
    import sipi.two_ground_sampled_pair_study as module
    calls = synthetic(monkeypatch, fail_at=2 if phase == 'extraction' else None)
    if phase in ('parameters','materials','input'):
        owner = module if phase == 'input' else shared
        name = {'parameters':'_parameters','materials':'_sample_material','input':'_sampled_line'}[phase]
        previous = getattr(owner,name); seen = []
        def fail(*a,**k):
            seen.append(1)
            if len(seen) == 2: raise ArithmeticError('original failed row')
            return previous(*a,**k)
        monkeypatch.setattr(owner,name,fail)
    if phase == 'diagnostic':
        previous = Line.analyze
        def fail(self):
            result = previous(self)
            if len(calls) == 2:
                def bad(): raise ArithmeticError('original failed row')
                result.characteristic = bad
            return result
        monkeypatch.setattr(Line,'analyze',fail)
    result = document().analyze(max_evaluations=4); row = result.rows[1]
    assert result.failed == 1 and result.summary is None and len(result.rows) == 4
    assert row.phase == phase and row.values is None
    assert all(result.rows[i].complete for i in (0,2,3))
    if phase == 'extraction':
        assert row.cause_details['input'] == json.loads(row.input_json)
        assert row.cause_details['current_solver'] is None
        copy = row.cause_details; copy['message'] = 'changed'
        assert row.cause_details['message'] == 'original current batch refusal'
    if phase == 'diagnostic': assert row.to_dict()['dielectric_mesh']['kind'] == 'test-only-synthetic'


@pytest.mark.parametrize('index', [0,1,2])
def test_one_nonfinite_frequency_invalidates_the_whole_row(monkeypatch, index):
    synthetic(monkeypatch); previous = Line.analyze
    def broken(self):
        result = previous(self); c = result.characteristic(); m = c.mixed_mode()
        matrix = m.z_characteristic.copy(); matrix[index,0,0] = np.nan
        result.characteristic = lambda: SimpleNamespace(basis=c.basis,names=c.names,frequency=c.frequency,
            mixed_mode=lambda: SimpleNamespace(basis=m.basis,names=m.names,frequency=m.frequency,z_characteristic=matrix))
        return result
    monkeypatch.setattr(Line,'analyze',broken)
    result = document().analyze(max_evaluations=4)
    assert result.failed == 4 and result.summary is None
    assert all(r.phase == 'diagnostic' and r.values is None and r.result is not None for r in result.rows)


def test_correlation_and_duplicate_vectors_are_not_resampled(monkeypatch):
    for sampling in (dict(kind='normal',count=8,seed=3,correlation=[[1.,.5],[.5,1.]],variables=[
            dict(name='width',mean=.2e-3,std=.3e-3),dict(name='gap',mean=.2e-3,std=.3e-3)]),
            dict(kind='sweep',count=4,variables=[dict(name='width',lower=.3e-3,upper=float(np.nextafter(.3e-3,np.inf)))])):
        calls = synthetic(monkeypatch); doc = document(sampling); result = doc.analyze(max_evaluations=8)
        np.testing.assert_array_equal([r.sample_values for r in result.rows], doc.samples())
        assert len(calls) == len(result.rows)-result.failed
        if sampling['kind'] == 'normal': assert 0 < result.failed < 8
        else: assert len(np.unique(doc.samples())) < 4 and len(calls) == 4


def test_fixed_pitch_and_sampled_debye_strength_remain_fixed_across_grid(monkeypatch):
    calls = synthetic(monkeypatch); raw = document().to_dict(); study = raw['study']
    study['schema'] = 'sipi.impedance-study/4'; study['fixed_pitch_m'] = .0008
    study['parameters']['gap'] = .0008-study['parameters']['width']
    study['material_evaluation']['materials'] = {'dielectric':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    study['material_variables'] = {'strength':dict(region='dielectric',path=['strengths',0])}
    study['sampling']['variables'] = [dict(name='width',lower=.0003,upper=.0004),dict(name='strength',lower=.5,upper=.9)]
    result = Document.from_dict(raw).analyze(max_evaluations=4)
    assert not result.failed
    for row,text in zip(result.rows,calls):
        data = json.loads(text); section = Line.loads(text).cross_section.section
        assert section.traces[1].x-section.traces[0].x == pytest.approx(.0008,rel=1e-14)
        assert data['frequency_hz'] == F
        assert data['materials']['dielectric']['parameters']['strengths'] == [row.sample_values[1]]
        assert json.loads(row.material_evaluation_json)['materials'] == data['materials']


@pytest.mark.parametrize('budget', [True,1,3,10001])
def test_budget_rejects_before_any_row(monkeypatch,budget):
    calls = synthetic(monkeypatch)
    with pytest.raises(ValueError): document().analyze(max_evaluations=budget)
    assert not calls


def test_interrupt_is_not_a_failed_row(monkeypatch):
    calls = synthetic(monkeypatch,fail_at=2,interrupt=True)
    with pytest.raises(KeyboardInterrupt): document().analyze(max_evaluations=4)
    assert len(calls) == 2


@pytest.mark.parametrize('failed', [False,True])
def test_shared_execution_record_and_project_preserve_grid(monkeypatch, failed):
    synthetic(monkeypatch,fail_at=2 if failed else None)
    doc = document(); request = SavedExecutionRequest(doc.dumps()); receipt = request.run()
    assert receipt['execution']['status'] == ('incomplete' if failed else 'complete')
    assert receipt['execution']['result']['failed'] == int(failed)
    record = SavedExecutionRecord(request,receipt,run_id='finite-grid:run',artifacts=ARTIFACTS)
    assert SavedExecutionRecord.loads(record.dumps()).receipt == receipt
    project = SavedProject(request,project_id='finite-grid',design_id='a',title='Grid',label='Source')
    project = project.attach_record('a',record)
    monkeypatch.setattr(Line,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedProject.loads(project.dumps()).prepare('a').request_id == request.request_id


@pytest.mark.parametrize('mode', ['budget','diagnostics','bytes'])
def test_execution_limits_remain_pre_solve(monkeypatch, mode):
    calls = synthetic(monkeypatch)
    kwargs = {'max_evaluations':3} if mode == 'budget' else {'diagnostics':['characteristic']} if mode == 'diagnostics' else {'max_input_bytes':16}
    with pytest.raises(ValueError): execute_saved(document().dumps(),**kwargs)
    assert not calls


def physical_document():
    raw = document(frequencies=[2e9,3.5e9,5e9],physical=True).to_dict()
    raw['study']['parameters']['gap'] = .00028
    raw['study']['sampling']['variables'] = [dict(name='width',lower=.00043,upper=.00044)]
    raw['study']['material_evaluation']['materials'] = {'dielectric':dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))}
    return Document.from_dict(raw)


def test_real_debye_grid_matches_single_frequencies_and_finite_refinement(record_property):
    from sipi.constants import mu_0,epsilon_0
    from sipi.line_resolution import ResolutionTolerance
    from sipi.two_ground_resolution import assess_two_ground_line_resolution
    doc = physical_document(); result = doc.analyze(max_evaluations=2)
    record_property('two_ground_sampled_study',json.dumps(result.to_dict(),sort_keys=True))
    assert result.failed == 0 and len(result.rows) == 2
    transform = np.array([[1.,-1.],[.5,.5]])
    observations = []
    for row in result.rows:
        line = row.result; raw = json.loads(row.input_json); singles = []
        for i,f in enumerate(line.frequency):
            single_raw = dict(raw,frequency_hz=[float(f)]); single = Line.from_dict(single_raw).analyze()
            singles.append(dict(input=single_raw,R=single.R.tolist(),L=single.L.tolist(),G=single.G.tolist(),C=single.C.tolist(),current=single.current_record(),mesh=single.mesh_record()))
            record_property('two_ground_single_'+str(row.index)+'_'+str(i),json.dumps(singles[-1],sort_keys=True))
            for key in ('R','L','G','C'): np.testing.assert_allclose(getattr(line,key)[i],getattr(single,key)[0],rtol=1e-12,atol=0)
            assert line.current_record() == single.current_record()
            assert line.mesh_record() == single.mesh_record()
            omega = 2*np.pi*f; z = line.R[i]+1j*omega*line.L[i]; y = line.G[i]+1j*omega*line.C[i]
            gamma = np.asarray(sqrtm(z@y),dtype=complex)
            independent = np.diag(transform@np.linalg.solve(gamma,z)@transform.T).real
            np.testing.assert_allclose(row.values[i],independent,rtol=1e-10,atol=0)
            eps = 3.+.7/(1+1j*f/1e9); c0 = line.current_factors.C0
            np.testing.assert_allclose(line.C[i],eps.real*c0,rtol=.005,atol=0)
            np.testing.assert_allclose(line.G[i],omega*(-eps.imag)*c0,rtol=.005,atol=0)
            np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-12,atol=1e-28)
        observations.append(dict(input=raw,singles=singles))
    base = Line.loads(result.rows[0].input_json); finer = dict(base.current_options,panels_per_edge=128,ground_modes=256); outer=[]
    for width,modes in ((.016,512),(.032,1024)):
        raw = base.to_dict(); raw['cross_section']['box']['width'] = width
        raw['panel'] = dict(finer,ground_modes=modes)
        for key in ('edge_size','far_size','grade'): raw['cross_section']['mesh'][key] *= .5
        outer.append(Line.from_dict(raw))
    assessment = assess_two_ground_line_resolution(base,refined_panel_options=finer,outer_documents=outer,
        tolerances={key:ResolutionTolerance(.01,0.) for key in ('R','L_internal','L_external','C','G','C0')},
        refinement_factor=.5,max_solves=6)
    record_property('two_ground_sampled_finite_resolution',json.dumps(assessment.to_dict(),sort_keys=True))
    assert assessment.completed and assessment.accepted
