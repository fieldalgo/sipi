# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved sampled goals: actual geometry replay and dispersive material invariant."""
import json
import numpy as np
from sipi.constants import epsilon_0, mu_0
from sipi.dielectric import DebyeDielectric
from sipi.execution import execute_saved
from sipi.line_input import _line_from_values
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument as Document
from sipi.study import ImpedanceStudyDocument
from test_pair_line_goal_document import source, Q
from test_pair_line_goal import document as line
from test_sampled_panel_pair_goal_physical import independent, F, A


def capture(monkeypatch):
    original=Document.solve;results=[]
    def recorded(self):
        result=original(self);results.append(result);return result
    monkeypatch.setattr(Document,'solve',recorded)
    return results


def test_saved_physical_selected_point_and_frozen_refinements(monkeypatch):
    results=capture(monkeypatch);study=source(physical=True).to_dict()
    study['material_evaluation']['frequency_hz']=float(F[0])
    point=[.0006035069001068527,.00040931740232325324]
    doc=Document(study,conductor=line(.6e-3,.4e-3).to_dict()['conductor'],frequencies=F.tolist(),
        targets={q:[v]*3 for q,v in zip(Q,[110.,40.])},
        tolerances={q:[v]*3 for q,v in zip(Q,[.5,.25])},initial=point,max_evaluations=4)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['result']['evaluations']==4 and len(results)==1
    goal=results[0];assert list(goal.parameters)==point
    for physical,row in [(goal.result,goal.history[0])]+[(r.result,r.evaluation) for r in goal.refinements]:
        independent(physical)
        assert physical.input_json==row.input_json
        assert np.all(abs(np.array(row.impedances)-goal.targets)<=goal.tolerances)
        assert np.all(abs(np.array(row.impedances)/goal.impedances-1)<=.005)
    assert output['result']==goal.to_dict() and output['input']==doc.to_dict()


def test_saved_uniform_debye_material_leaves_and_common_execution(monkeypatch):
    results=capture(monkeypatch);model=DebyeDielectric(3.,(.7,),(1e9,))
    study=ImpedanceStudyDocument('coupled_microstrip',dict(width=.3e-3,gap=.2e-3,substrate_height=.5e-3,
        eps_r=4.,thickness=35e-6,air_height=2e-3,box_width=6e-3),quantity='z_diff_forward',frequency=float(F[0]),
        materials={'substrate':model,'air':model},mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1),
        material_variables={'eps_substrate':dict(region='substrate',path=['eps_inf']),
                            'eps_air':dict(region='air',path=['eps_inf'])},
        sampling=dict(kind='corners',variables=[dict(name='eps_substrate',lower=2.,upper=4.),
                                              dict(name='eps_air',lower=2.,upper=4.)]))
    nominal=_line_from_values(study.to_dict(),{'kind':'perfect'},[3.,3.])
    c0=panel_surface_current_factors(nominal.cross_section.section).C0
    eps=3.+.7/(1+1j*F/1e9)
    expected=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(c0) for e in eps])
    target=np.diagonal(A@expected@A.T,axis1=1,axis2=2).real
    doc=Document(study,conductor={'kind':'perfect'},frequencies=F.tolist(),
        targets=dict(zip(Q,target.T.tolist())),tolerances=dict(zip(Q,(target*.005).T.tolist())),
        initial=[3.,3.],max_evaluations=4)
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and output['result']['evaluations']==4 and len(results)==1
    goal=results[0];assert goal.parameters==(3.,3.)
    for physical,row in [(goal.result,goal.history[0])]+[(r.result,r.evaluation) for r in goal.refinements]:
        assert json.loads(row.input_json)['line']['materials']==nominal.to_dict()['materials']
        reference=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(physical.current_factors.C0) for e in eps])
        actual=physical.characteristic().z_characteristic
        assert abs(actual-reference).max()/abs(reference).max()<=1e-10
        np.testing.assert_allclose(row.impedances,np.diagonal(A@reference@A.T,axis1=1,axis2=2).real,rtol=1e-10,atol=0)
        np.testing.assert_allclose(physical.C,eps.real[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        np.testing.assert_allclose(physical.G,(-2*np.pi*F*eps.imag)[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        assert np.all(physical.R==0)
    assert output['result']==goal.to_dict()
