# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Every finite-grid cell and refinement axis keeps its original acceptance gate."""
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.two_ground_face_sampled_pair_goal import seek_two_ground_face_sampled_forward_pair_impedances as seek
from sipi.sampled_panel_pair_goal import SampledPanelForwardPairGoalError
from test_two_ground_face_sampled_pair_goal import factory,synthetic,F,STAGES
from test_two_ground_sampled_pair_goal import factory as whole_factory
from test_sampled_panel_pair_goal import BOUNDS,targets


@pytest.mark.parametrize('stage',STAGES)
@pytest.mark.parametrize('frequency',range(3))
@pytest.mark.parametrize('gate',['target','convergence'])
def test_all_refined_frequency_cells_keep_absolute_and_relative_gates(monkeypatch,stage,frequency,gate):
    calls=synthetic(monkeypatch);original=Line.analyze
    def shifted(self):
        line=original(self)
        if len(calls)==STAGES.index(stage)+2:
            c=line.characteristic();m=c.mixed_mode();matrix=m.z_characteristic.copy();matrix[frequency,0,0]*=1.01
            line.characteristic=lambda:SimpleNamespace(names=c.names,basis=c.basis,frequency=c.frequency,
                mixed_mode=lambda:SimpleNamespace(names=m.names,basis=m.basis,frequency=m.frequency,z_characteristic=matrix))
        return line
    monkeypatch.setattr(Line,'analyze',shifted)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8 if gate=='target' else 1000.),initial=[1.35,.8],max_evaluations=4)
    assert caught.value.stage==stage+'/'+gate
    assert caught.value.attempts==len(calls)==STAGES.index(stage)+2
    assert caught.value.input_json==calls[-1]


def test_face_coatings_and_reference_laws_remain_frozen_across_grid(monkeypatch):
    calls=synthetic(monkeypatch);made=[]
    def build(x,y):
        made.append((x,y));data=factory(x,y).to_dict()
        data['conductors']['positive']['top']=dict(kind='layered',conductivity=58e6,relative_permeability=1.,
            coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
        data['conductors']['negative']['left']['roughness']=dict(kind='hammerstad',rms_m=1e-6)
        return Line.from_dict(data)
    result=seek(build,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8),initial=[1.35,.8],max_evaluations=4)
    assert len(made)==1 and len(calls)==4
    selected=result.document.to_dict()
    for item in result.refinements:
        for key in ('conductors','reference','materials','ground_thickness_m','frequency_hz'):
            assert item.document.to_dict()[key]==selected[key]
    raw=result.to_dict();raw['input']['conductors'].clear()
    assert result.document.to_dict()['conductors']==selected['conductors']
    json.dumps(result.to_dict(),allow_nan=False)


def test_whole_boundary_grid_factory_refused_before_field(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(SampledPanelForwardPairGoalError) as caught:
        seek(whole_factory,BOUNDS,F,targets(frequencies=F),tolerances=np.full((3,2),1e-8))
    assert caught.value.stage=='search/factory' and caught.value.cause_type=='TypeError'
    assert not calls and caught.value.attempts==1
