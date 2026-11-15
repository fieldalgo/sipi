# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical-face assignments and strict goal admission before field work."""
import json
import pytest
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from sipi.two_ground_face_line_goal import seek_two_ground_face_line_quantity as seek, TwoGroundFaceLineQuantityGoalError as GoalError
from test_two_ground_face_line_goal import factory, synthetic, target
from test_two_ground_face_line_study import QUANTITIES
from test_two_ground_line_goal import factory as whole_factory


@pytest.mark.parametrize('quantity', QUANTITIES)
def test_face_coatings_and_roughness_remain_on_frozen_physical_boundaries(monkeypatch, quantity):
    calls=synthetic(monkeypatch);original=factory(quantity)
    def build(width):
        data=original(width).to_dict();name=next(iter(data['conductors']))
        data['conductors'][name]['top']=dict(kind='layered',conductivity=58e6,
            relative_permeability=1.,coatings=[dict(thickness_m=2e-7,conductivity=14e6,relative_permeability=3.)])
        data['conductors'][name]['left']['roughness']=dict(kind='hammerstad',rms_m=1e-6)
        return Line.from_dict(data)
    result=seek(build,[.0003,.0005],target(quantity),quantity=quantity,tolerance=1e-8,max_evaluations=6)
    selected=result.document.to_dict()
    for row in result.refinements:
        for key in ('conductors','reference','ground_thickness_m','materials'):
            assert row.document.to_dict()[key]==selected[key]
    saved=result.to_dict();saved['input']['conductors'].clear()
    assert result.document.to_dict()['conductors']==selected['conductors']
    assert len(calls)==6
    json.dumps(result.to_dict(),allow_nan=False)


def test_whole_boundary_factory_refused_without_fields(monkeypatch):
    calls=synthetic(monkeypatch)
    with pytest.raises(GoalError) as caught:
        seek(whole_factory(),[.0003,.0005],40.,quantity='impedance_real',tolerance=.1)
    assert caught.value.stage=='search/factory' and caught.value.cause_type=='TypeError'
    assert caught.value.attempts==1 and not calls


@pytest.mark.parametrize('kind',['frequency','order','length','grid','scalar'])
def test_invalid_or_drifting_pair_contract_precedes_fields(monkeypatch,kind):
    calls=synthetic(monkeypatch);original=factory('differential_forward_impedance_real');made=[]
    def build(width):
        data=original(width).to_dict();made.append(width)
        if kind=='frequency' and len(made)>1:data['frequency_hz']=[2*data['frequency_hz'][0]]
        if kind=='order' and len(made)>1:data['cross_section']['traces'].reverse()
        if kind=='length':data['length_m']=.01
        if kind=='grid':data['frequency_hz']=[1e9,2e9]
        if kind=='scalar':
            data['cross_section']['traces']=data['cross_section']['traces'][:1]
            name=data['cross_section']['traces'][0]['name'];data['conductors']={name:data['conductors'][name]}
        return Line.from_dict(data)
    with pytest.raises(GoalError) as caught:
        seek(build,[.0003,.0005],40.,quantity='differential_forward_impedance_real',tolerance=.1)
    assert caught.value.stage=='search/validation'
    assert len(calls)==(1 if kind in ('frequency','order') else 0)
    assert caught.value.attempts==len(calls)+1
