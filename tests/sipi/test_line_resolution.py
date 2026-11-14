# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Real extracted inputs, finite agreement and retained nonacceptance."""
import json
import numpy as np
import pytest

from sipi import CrossSection, CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance, assess_line_resolution
from sipi.constants import epsilon_0, mu_0


def inputs():
    section=stripline(width=.5e-3,plane_spacing=1e-3,thickness=50e-6,
                     eps_r=4.,tan_delta=.02,box_width=.008)
    base=TransmissionLineDocument(CrossSectionDocument(section,
        mesh=dict(edge_size=5e-6,far_size=.2e-3,grade=.1)),[1e9,2e9],
        materials={},conductor={'kind':'perfect'},length=.02)
    outers=[]
    for width in (.012,.016):
        data=base.to_dict();data['cross_section']['box']['width']=width
        for key in ('edge_size','far_size','grade'):data['cross_section']['mesh'][key]*=.5
        outers.append(TransmissionLineDocument.from_dict(data))
    return base,outers


TOLERANCES={key:ResolutionTolerance(.005,0.) for key in ('C','G','C0','L_external')}


@pytest.fixture(scope='module')
def observed():
    base,outers=inputs()
    report=assess_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
    return base,outers,report


def test_finite_checks_keep_inputs_and_independent_uniform_identities(observed,record_property):
    base,outers,report=observed
    assert report.completed and report.accepted and report.failure is None
    assert len(report.evaluations)==4 and len(report.comparisons)==3
    assert [r.stage for r in report.evaluations]==['base','mesh','outer:0','outer:1']
    assert [r.reference_index for r in report.comparisons]==[0,1,1]
    assert report.evaluations[0].input_json==base.dumps()
    assert [r.input_json for r in report.evaluations[2:]]==[d.dumps() for d in outers]
    for evaluation in report.evaluations:
        result=evaluation.result;f=result.frequency
        np.testing.assert_allclose(result.C,4*np.broadcast_to(result.dielectric.C0,result.C.shape),rtol=1e-12)
        np.testing.assert_allclose(result.G,2*np.pi*f[:,None,None]*.02*result.C,rtol=1e-12)
        np.testing.assert_allclose(result.L@result.C,4*mu_0*epsilon_0*np.ones_like(result.C),rtol=1e-10)
        assert np.linalg.svd(result.network.s,compute_uv=False).max()<=1+1e-10
    rows=[dict(stage=r.stage,relative={k:float(r.differences[k].max()/r.allowances[k].max())
                                      for k in r.differences}) for r in report.comparisons]
    record_property('resolution_allowance_fractions',json.dumps(rows))
    assert set(report.tolerances)==set(TOLERANCES) and 'R' not in report.comparisons[0].differences
    with pytest.raises(TypeError): report.tolerances['R']=ResolutionTolerance(.05,0.)
    with pytest.raises(ValueError): report.comparisons[0].differences['C'][0,0,0]=0


def replay(monkeypatch,report):
    results={r.input_json:r.result for r in report.evaluations}
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:results[self.dumps()])


def test_exact_requested_agreement_can_complete_without_acceptance(observed,monkeypatch):
    base,outers,original=observed;replay(monkeypatch,original)
    report=assess_line_resolution(base,outer_documents=outers,
        tolerances={'C':ResolutionTolerance(0.,0.),'R':ResolutionTolerance(0.,0.)})
    assert report.completed and not report.accepted and report.failure is None
    assert not report.comparisons[0].accepted and report.comparisons[0].differences['C'].max()>0
    for row in report.comparisons:
        assert np.all(row.differences['R']==0) and np.all(row.allowances['R']==0)


def test_absolute_si_allowance_is_explicit_and_keeps_all_entries(observed,monkeypatch):
    base,outers,original=observed;replay(monkeypatch,original)
    maximum=max(row.differences['C'].max() for row in original.comparisons)
    exact=assess_line_resolution(base,outer_documents=outers,tolerances={'C':ResolutionTolerance(0.,maximum)})
    tight=assess_line_resolution(base,outer_documents=outers,tolerances={'C':ResolutionTolerance(0.,maximum/2)})
    assert exact.accepted and not tight.accepted
    for row in exact.comparisons:
        assert row.differences['C'].shape==(2,1,1) and np.all(row.allowances['C']==maximum)


@pytest.mark.parametrize('stage', ['base','mesh','outer:0','outer:1'])
def test_solver_failure_retains_completed_results_and_stops(observed,monkeypatch,stage):
    base,outers,previous=observed;values={e.input_json:e.result for e in previous.evaluations};calls=[]
    failing=next(e.input_json for e in previous.evaluations if e.stage==stage)
    def analyze(self):
        text=self.dumps();calls.append(text)
        if text==failing:raise ValueError('retained field refusal')
        return values[text]
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    report=assess_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
    count=[e.stage for e in previous.evaluations].index(stage)
    assert len(calls)==count+1 and len(report.evaluations)==count
    assert not report.completed and not report.accepted
    assert report.failure.stage==stage and report.failure.input_json==failing
    assert report.failure.kind=='ValueError' and report.failure.message=='retained field refusal'


@pytest.mark.parametrize('change', ['material','trace','frequency','length','reference','mesh','shrink','no-growth','top-ground'])
def test_mixed_inputs_and_physical_plane_motion_refuse_before_field(change,monkeypatch):
    base,outers=inputs();raw=outers[0].to_dict();cross=raw['cross_section']
    if change=='material':cross['layers'][0]['eps_r']=5.
    if change=='trace':cross['traces'][0]['width']*=1.1
    if change=='frequency':raw['frequency_hz']=[2e9,3e9]
    if change=='length':raw['length_m']=.03
    if change=='reference':raw['reference_ohms']=60.
    if change=='mesh':cross['mesh']['grade']*=2
    if change=='shrink':cross['box']['width']=.004
    if change=='no-growth':cross['box']['width']=.008
    if change=='top-ground':cross['layers'][-1]['thickness']*=2
    altered=TransmissionLineDocument.from_dict(raw)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError):assess_line_resolution(base,outer_documents=[altered],tolerances=TOLERANCES)


@pytest.mark.parametrize('options', [dict(max_solves=3),dict(max_solves=True),dict(refinement_factor=1.),
    dict(refinement_factor=0.),dict(refinement_factor=True),dict(tolerances={}),
    dict(tolerances={'C':.005}),dict(tolerances={'unselected':ResolutionTolerance(.01,0.)})])
def test_budget_controls_and_explicit_tolerances_precede_mesh(options,monkeypatch):
    base,outers=inputs();settings=dict(outer_documents=outers,tolerances=TOLERANCES);settings.update(options)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises((ValueError,TypeError)):assess_line_resolution(base,**settings)


def test_resolved_default_cannot_be_mixed_with_old_outer_mesh(monkeypatch):
    base,outers=inputs();raw=base.to_dict();raw['cross_section']['mesh'].pop('grade')
    unknown=TransmissionLineDocument.from_dict(raw)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    assert 'grade' in unknown.to_dict()['cross_section']['mesh']
    with pytest.raises(ValueError,match='refined mesh'):assess_line_resolution(unknown,outer_documents=outers,tolerances=TOLERANCES)


def test_small_mutual_entry_cannot_hide_behind_large_diagonals(monkeypatch):
    # Controlled SPD capacitances isolate the comparison contract, not a field reference.
    from types import SimpleNamespace
    base,outers=inputs()
    def paired(doc):
        data=doc.to_dict();trace=data['cross_section']['traces'][0]
        data['cross_section']['traces']=[dict(trace,name='left',x=-.0005),dict(trace,name='right',x=.0005)]
        return TransmissionLineDocument.from_dict(data)
    base=paired(base);outers=[paired(d) for d in outers]
    def analyze(self):
        mutual=.001 if self.cross_section.mesh_options['grade']==.1 else .002
        return SimpleNamespace(names=('left','right'),frequency=np.array([1e9,2e9]),
            C=1e-10*np.broadcast_to([[2.,-mutual],[-mutual,2.]],(2,2,2)).copy())
    monkeypatch.setattr(TransmissionLineDocument,'analyze',analyze)
    report=assess_line_resolution(base,outer_documents=outers,tolerances={'C':ResolutionTolerance(.01,0.)})
    row=report.comparisons[0]
    assert report.completed and not report.accepted
    assert np.all(row.differences['C'][:,0,0]==0)
    assert np.all(row.differences['C'][:,0,1]>row.allowances['C'][:,0,1])


def test_grounded_side_motion_is_not_numerical_padding(monkeypatch):
    base,outers=inputs()
    def grounded(doc):
        data=doc.to_dict();data['cross_section']['box']['sides']='ground'
        return TransmissionLineDocument.from_dict(data)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('preflight meshed'))
    with pytest.raises(ValueError,match='grounded side'):
        assess_line_resolution(grounded(base),outer_documents=[grounded(d) for d in outers],tolerances=TOLERANCES)


def test_real_surface_loss_keeps_nonacceptance_and_independent_rl_ratio():
    base,outers=inputs()
    def metallic(doc):
        data=doc.to_dict();data['conductor']=dict(kind='surface',conductivity=58e6,
            ground_thickness=35e-6,relative_permeability=1.,roughness_rms=0.)
        return TransmissionLineDocument.from_dict(data)
    report=assess_line_resolution(metallic(base),outer_documents=[metallic(d) for d in outers],
        tolerances={key:ResolutionTolerance(0.,0.) for key in ('R','L_internal')})
    assert report.completed and not report.accepted
    assert report.comparisons[0].differences['R'].max()>0
    for row in report.evaluations:
        result=row.result
        np.testing.assert_allclose(result.R,
            2*np.pi*result.frequency[:,None,None]*result.conductor.L_internal,rtol=1e-12)


def test_user_interrupt_propagates_without_becoming_a_failed_solve(monkeypatch):
    base,outers=inputs()
    def interrupt(self):raise KeyboardInterrupt()
    monkeypatch.setattr(TransmissionLineDocument,'analyze',interrupt)
    with pytest.raises(KeyboardInterrupt):
        assess_line_resolution(base,outer_documents=outers,tolerances=TOLERANCES)
