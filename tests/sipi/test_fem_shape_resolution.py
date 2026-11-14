# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Admission and per-entry finite observations for checked FEM lines."""
import numpy as np
import pytest
from types import SimpleNamespace
from sipi import CrossSection, assess_fem_shape_line_resolution
from sipi.line_resolution import ResolutionTolerance
from test_fem_shape_line import document, Document


def inputs():
    base=document();outer=[]
    for width in (.016,.032):
        raw=document(.5).to_dict();raw['cross_section']['box']['width']=width
        outer.append(Document.from_dict(raw))
    return base,outer


TOLERANCES={k:ResolutionTolerance(.01,0.) for k in ('R','L_internal','L_external','C','G','C0')}


@pytest.mark.parametrize('change',['material','trace','frequency','length','port','mesh','shrink','no-growth','top-ground','metal','reference-metal','ground-thickness','interface'])
def test_physical_changes_refuse_before_fields(change,monkeypatch):
    base,outer=inputs();raw=outer[0].to_dict();cross=raw['cross_section']
    if change=='material':cross['layers'][0]['eps_r']=5.
    if change=='trace':cross['traces'][0]['width']*=1.1
    if change=='frequency':raw['frequency_hz']=[3e9,4e9]
    if change=='length':raw['length_m']=.03
    if change=='port':raw['reference_ohms']=60.
    if change=='mesh':cross['mesh']['grade']*=2
    if change=='shrink':cross['box']['width']=.004
    if change=='no-growth':cross['box']['width']=.008
    if change=='top-ground':cross['layers'][-1]['thickness']*=2
    if change=='metal':raw['conductors']['negative']['conductivity']=36e6
    if change=='reference-metal':raw['reference']['conductivity']=57e6
    if change=='ground-thickness':raw['ground_thickness_m']=40e-6
    if change=='interface':cross['layers'].append(dict(cross['layers'][-1],name='extra'))
    changed=Document.from_dict(raw)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('preflight reached fields'))
    with pytest.raises(ValueError):assess_fem_shape_line_resolution(base,outer_documents=[changed],tolerances=TOLERANCES)


@pytest.mark.parametrize('options',[dict(max_solves=3),dict(max_solves=True),dict(refinement_factor=1.),
    dict(refinement_factor=0.),dict(refinement_factor=True),dict(tolerances={}),dict(tolerances={'C':.01}),
    dict(tolerances={'unknown':ResolutionTolerance(.01,0.)}),dict(outer_documents=[]),dict(outer_documents=[None])])
def test_preflight_budget_and_contract(options,monkeypatch):
    base,outer=inputs();kw=dict(outer_documents=outer,tolerances=TOLERANCES);kw.update(options)
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('preflight reached fields'))
    with pytest.raises((ValueError,TypeError)):assess_fem_shape_line_resolution(base,**kw)


def test_requires_explicit_mesh_and_correct_document_type(monkeypatch):
    from test_line_resolution import inputs as original
    base,outer=inputs();raw=base.to_dict();raw['cross_section']['mesh'].pop('grade')
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**kw:pytest.fail('preflight reached fields'))
    with pytest.raises(ValueError,match='explicit'):assess_fem_shape_line_resolution(Document.from_dict(raw),outer_documents=outer,tolerances=TOLERANCES)
    with pytest.raises(TypeError):assess_fem_shape_line_resolution(original()[0],outer_documents=outer,tolerances=TOLERANCES)


def test_mutual_entry_has_no_diagonal_floor(monkeypatch):
    base,outer=inputs()
    def analyze(self):
        mutual=.001 if self.cross_section.mesh_options['grade']==.1 else .002
        return SimpleNamespace(names=('positive','negative'),frequency=np.array([2e9,3e9]),
            C=1e-10*np.broadcast_to([[2.,-mutual],[-mutual,2.]],(2,2,2)).copy())
    monkeypatch.setattr(Document,'analyze',analyze)
    report=assess_fem_shape_line_resolution(base,outer_documents=outer,tolerances={'C':ResolutionTolerance(.01,0.)})
    assert report.completed and not report.accepted and report.failure is None
    row=report.comparisons[0]
    assert np.all(row.differences['C'][:,0,0]==0)
    assert np.all(row.differences['C'][:,0,1]>row.allowances['C'][:,0,1])


def test_interrupt_propagates(monkeypatch):
    base,outer=inputs()
    def stop(self):raise KeyboardInterrupt('requested')
    monkeypatch.setattr(Document,'analyze',stop)
    with pytest.raises(KeyboardInterrupt):assess_fem_shape_line_resolution(base,outer_documents=outer,tolerances=TOLERANCES)
