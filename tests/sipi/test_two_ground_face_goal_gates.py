# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Face goals preserve original acceptance and physical boundary assignments."""
import json
import pytest
from sipi import rlgc_characteristic
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Document
from sipi.two_ground_face_pair_goal import seek_two_ground_face_forward_pair_impedances as seek
from sipi.pair_line_goal import ForwardPairGoalError
from test_two_ground_face_pair_goal import factory, synthetic
from test_two_ground_pair_goal import physical_document as whole_document
from test_panel_pair_goal import modal, quantities, ROOT, BOUNDS, STAGES


@pytest.mark.parametrize('stage', STAGES)
@pytest.mark.parametrize('failure', ['target', 'convergence'])
def test_each_refinement_retains_absolute_and_relative_limits(monkeypatch, stage, failure):
    calls = synthetic(monkeypatch)
    original = Document.analyze
    def changed(self):
        result = original(self)
        if len(calls) == STAGES.index(stage) + 2:
            matrices, _ = modal(ROOT[0] * 1.02, ROOT[1] * 1.02)
            result.characteristic = lambda: rlgc_characteristic(
                [1e9], **matrices, names=('positive', 'negative'))
        return result
    monkeypatch.setattr(Document, 'analyze', changed)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory, BOUNDS, quantities(*ROOT),
             tolerances=[1e-8 if failure == 'target' else 100.] * 2,
             initial=ROOT, max_evaluations=4)
    assert caught.value.stage == stage + '/' + failure
    assert len(caught.value.history) == STAGES.index(stage) + 2
    assert caught.value.input_json == calls[-1]


def test_joint_compared_with_both_single_axes(monkeypatch):
    calls = synthetic(monkeypatch)
    original = Document.analyze
    def changed(self):
        result = original(self)
        factor = [1., .996, 1., 1.004][len(calls) - 1]
        matrices, _ = modal(ROOT[0] * factor, ROOT[1] * factor)
        result.characteristic = lambda: rlgc_characteristic(
            [1e9], **matrices, names=('positive', 'negative'))
        return result
    monkeypatch.setattr(Document, 'analyze', changed)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(factory, BOUNDS, quantities(*ROOT), tolerances=[100.] * 2,
             initial=ROOT, max_evaluations=4)
    assert caught.value.stage == 'joint-refinement/convergence'
    assert caught.value.attempts == 4


def test_all_faces_and_coatings_survive_frozen_refinements(monkeypatch):
    synthetic(monkeypatch)
    data = factory(*ROOT).to_dict()
    data['conductors']['positive']['top'] = dict(kind='layered', conductivity=58e6,
        relative_permeability=1., coatings=[dict(thickness_m=2e-7,
        conductivity=14e6, relative_permeability=3.)])
    data['conductors']['negative']['left']['roughness'] = dict(kind='hammerstad', rms_m=1e-6)
    result = seek(lambda *args: Document.from_dict(data), BOUNDS, quantities(*ROOT),
                  tolerances=[1e-8] * 2, initial=ROOT, max_evaluations=4)
    for item in [result.document, *[row.document for row in result.refinements]]:
        actual = item.to_dict()
        for key in ('conductors', 'reference', 'materials', 'ground_thickness_m'):
            assert actual[key] == data[key]
    saved = result.to_dict()
    saved['input']['conductors'].clear()
    assert result.document.to_dict()['conductors'] == data['conductors']
    json.dumps(result.to_dict(), allow_nan=False)


def test_whole_boundary_document_not_implicitly_converted(monkeypatch):
    calls = synthetic(monkeypatch)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(lambda x, y: whole_document(x*.0003, y*.0002, 1e9), BOUNDS,
             quantities(*ROOT), tolerances=[1e-8]*2)
    assert caught.value.stage == 'search/factory'
    assert caught.value.cause_type == 'TypeError' and not calls


@pytest.mark.parametrize('kind', ['frequency', 'order', 'length', 'grid', 'scalar'])
def test_invalid_or_drifting_line_stops_before_field(monkeypatch, kind):
    calls = synthetic(monkeypatch)
    made = []
    def bad(x, y):
        data = factory(x, y).to_dict()
        made.append(1)
        if kind == 'frequency' and len(made) > 1:
            data['frequency_hz'] = [2e9]
        elif kind == 'order' and len(made) > 1:
            data['cross_section']['traces'].reverse()
        elif kind == 'length':
            data['length_m'] = .01
        elif kind == 'grid':
            data['frequency_hz'] = [1e9, 2e9]
        elif kind == 'scalar':
            data['cross_section']['traces'] = data['cross_section']['traces'][:1]
            data['conductors'] = {'positive': data['conductors']['positive']}
        return Document.from_dict(data)
    with pytest.raises(ForwardPairGoalError) as caught:
        seek(bad, BOUNDS, quantities(*ROOT), tolerances=[1e-8]*2)
    assert caught.value.stage == 'search/validation'
    assert len(calls) == (1 if kind in ('frequency', 'order') else 0)
    assert caught.value.attempts == len(calls) + 1
