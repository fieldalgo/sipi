# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import json
import numpy as np
import pytest
from sipi import CrossSection
from sipi.dielectric import DebyeDielectric, TabulatedDielectric, dielectric_to_dict
from sipi.study import ImpedanceStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances as seek, SampledPanelForwardPairGoalError
from test_pair_line_goal_document import source, Q
from test_sampled_panel_pair_goal import F, synthetic, targets, document as line
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument as Document
import sipi.sampled_panel_pair_goal_document as implementation


def document():
    study=source().to_dict();study['material_evaluation']['frequency_hz']=float(F[0])
    return Document(study,conductor=line(.6e-3,.4e-3).to_dict()['line']['conductor'],frequencies=F.tolist(),
        targets=dict(zip(Q,targets().T.tolist())),tolerances={q:[1e-6]*3 for q in Q})


def test_saved_geometry_modal_root_matches_direct_api(monkeypatch):
    synthetic(monkeypatch);doc=document();result=doc.solve()
    direct=seek(lambda w,g:line(w,g),[[.15e-3,.6e-3],[.1e-3,.3e-3]],F,
        targets(),tolerances=np.full((3,2),1e-6))
    assert result.to_dict()==direct.to_dict()
    np.testing.assert_allclose(result.parameters,[1.35*.3e-3,.8*.2e-3],rtol=1e-6)
    assert Document.loads(doc.dumps()).dumps()==doc.dumps()
    raw=doc.to_dict();raw['frequency_hz'][0]=1.;raw['targets_ohm'][Q[0]][0]=1.
    assert doc.to_dict()['frequency_hz']==list(F) and doc.to_dict()['targets_ohm'][Q[0]][0]!=1.


def test_preflight_is_field_free(monkeypatch):
    def forbidden(*a,**k):pytest.fail('preflight invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    monkeypatch.setattr(PanelTransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(ImpedanceStudyDocument,'analyze',forbidden)
    doc=document();assert Document.loads(doc.dumps()).dumps()==doc.dumps()


@pytest.mark.parametrize('where',['root','panel','targets_ohm','tolerances_ohm'])
@pytest.mark.parametrize('change',['extra','missing'])
def test_exact_keys(where,change):
    raw=document().to_dict();target=raw if where=='root' else raw[where]
    if change=='extra':target['unexpected']=1
    else:target.pop(next(iter(target)))
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('frequencies',[[1e9],[0.,1e9],[1e9,1e9],[2e9,1e9],[True,1e9],[1e9,2e9],list(range(1,66))])
def test_invalid_grids_and_anchor(frequencies):
    raw=document().to_dict();raw['frequency_hz']=frequencies
    for key in ['targets_ohm','tolerances_ohm']:
        for q in Q:raw[key][q]=[1.]*len(frequencies)
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('value',[1.,[1.],[1.,2.],[[1.],[2.],[3.]],[1.,0.,1.],[1.,True,1.],[1.,float('inf'),1.]])
@pytest.mark.parametrize('key',['targets_ohm','tolerances_ohm'])
def test_no_broadcast_nonpositive_or_nonfinite_targets(key,value):
    raw=document().to_dict();raw[key][Q[0]]=value
    with pytest.raises(ValueError):Document.from_dict(raw)


@pytest.mark.parametrize('value',[3,True,4.,10001])
def test_reserved_budget(value):
    raw=document().to_dict();raw['max_evaluations']=value
    with pytest.raises(ValueError):Document.from_dict(raw)


def test_future_panel_refinements_and_material_band_preflight(monkeypatch):
    def forbidden(*a,**k):pytest.fail('invalid input invoked fields')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    raw=document().to_dict();raw['panel']['panels_per_edge']=256
    with pytest.raises(ValueError):Document.from_dict(raw)
    raw=document().to_dict()
    raw['study']['material_evaluation']['materials']['substrate']=dielectric_to_dict(TabulatedDielectric((F[0],1e9),(4.,4.),(.02,.02)))
    with pytest.raises(ValueError,match='outside'):Document.from_dict(raw)


def test_duplicate_schema_and_nonfinite_json():
    text=document().dumps()
    for changed in [text.replace('"ground_modes": 512','"ground_modes": 512, "ground_modes": 512'),
                    text.replace('"ground_modes": 512','"ground_modes": NaN'),
                    text.replace('sipi.sampled-panel-forward-pair-design/1','sipi.sampled-panel-forward-pair-design/2')]:
        with pytest.raises(ValueError):Document.loads(changed)


@pytest.mark.parametrize('attempt',[1,2,3,4])
def test_original_failure_grid_history_and_attempts(monkeypatch,attempt):
    calls=synthetic(monkeypatch,fail_at=attempt);raw=document().to_dict()
    raw['initial']=[1.35*.3e-3,.8*.2e-3];raw['max_evaluations']=4
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:Document.from_dict(raw).solve()
    error=caught.value
    assert error.attempts==len(calls)==attempt and len(error.history)==attempt-1
    assert error.frequencies==tuple(F) and error.cause_type=='ArithmeticError' and error.input_json==calls[-1]


def test_fixed_pitch_material_leaf_and_entire_grid_preserved(monkeypatch):
    raw=document().to_dict();study=raw['study'];study['schema']='sipi.impedance-study/4';study['fixed_pitch_m']=.95e-3
    study['material_evaluation']['materials']['substrate']=dielectric_to_dict(DebyeDielectric(3.,(.7,),(1e9,)))
    study['material_variables']={'strength':dict(region='substrate',path=['strengths',0])}
    study['sampling']['variables']=[dict(name='left_width',lower=.4e-3,upper=.8e-3),dict(name='strength',lower=.5,upper=.9)]
    raw['initial']=[.65e-3,.7];raw['panel']=dict(panels_per_edge=16,ground_modes=1024,interpolation_degree=12)
    doc=Document.from_dict(raw)
    def inspect(factory,bounds,frequencies,requested,**options):
        assert bounds==[[.4e-3,.8e-3],[.5,.9]] and frequencies==list(F) and options['initial']==[.65e-3,.7]
        np.testing.assert_array_equal(requested,targets())
        for width,strength in [(.4e-3,.5),(.65e-3,.7),(.8e-3,.9)]:
            d=factory(width,strength).to_dict();t=d['line']['cross_section']['traces']
            assert d['panel']==raw['panel'] and d['line']['frequency_hz']==list(F)
            assert d['line']['materials']['substrate']['parameters']['strengths']==[strength]
            assert abs((t[1]['x']-t[0]['x'])-.95e-3)<1e-15
        return 'inspected'
    monkeypatch.setattr(implementation,'seek_sampled_panel_forward_pair_impedances',inspect)
    assert doc.solve()=='inspected'
