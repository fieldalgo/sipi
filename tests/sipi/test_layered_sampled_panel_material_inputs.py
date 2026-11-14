# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Material leaves and manufactured variable ordering retain the fixed coatings."""
import json
import numpy as np
from sipi.dielectric import DebyeDielectric,dielectric_to_dict
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from test_sampled_panel_pair_goal import synthetic
from test_layered_sampled_panel_study import document,FREQUENCIES


def test_material_strength_corners_keep_fixed_pitch_and_coatings(monkeypatch):
    calls=synthetic(monkeypatch);raw=document().to_dict();study=raw['study']
    study['schema']='sipi.impedance-study/4';study['fixed_pitch_m']=.95e-3
    study['parameters'].update(left_width=.6e-3,gap=.4e-3)
    study['material_evaluation']['materials']['substrate']=dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))
    study['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    study['sampling']=dict(kind='corners',variables=[dict(name='left_width',lower=.4e-3,upper=.8e-3),
        dict(name='strength',lower=.5,upper=.9)])
    doc=SampledPanelForwardPairStudyDocument.from_dict(raw);result=doc.analyze(max_evaluations=4)
    assert not result.failed and len(calls)==len(result.rows)==4
    for row in result.rows:
        width,strength=row.sample_values;d=json.loads(row.input_json);t=d['line']['cross_section']['traces']
        assert d['line']['conductor']==raw['conductor'] and d['line']['frequency_hz']==FREQUENCIES
        assert d['line']['materials']['substrate']['parameters']['strengths']==[strength]
        assert t[0]['width']==width and abs(t[1]['x']-t[0]['x']-.95e-3)<1e-15
        assert json.loads(row.material_evaluation_json)['materials']['substrate']['parameters']['strengths']==[strength]


def test_reordered_variables_keep_names_and_each_full_frequency_row(monkeypatch):
    calls=synthetic(monkeypatch);raw=document().to_dict();raw['study']['sampling']['variables'].reverse()
    doc=SampledPanelForwardPairStudyDocument.from_dict(raw);result=doc.analyze(max_evaluations=8)
    assert result.variable_names==('gap','left_width') and not result.failed and len(calls)==8
    np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples())
    for row in result.rows:
        gap,width=row.sample_values;d=json.loads(row.input_json);t=d['line']['cross_section']['traces']
        assert t[0]['width']==width
        assert abs(t[1]['x']-t[0]['x']-(width+t[1]['width'])/2-gap)<1e-15
        assert d['line']['conductor']==raw['conductor'] and len(row.values)==len(FREQUENCIES)
