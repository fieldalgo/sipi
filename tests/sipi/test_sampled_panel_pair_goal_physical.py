# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite-frequency physical goals, independent eigenspaces and material invariants."""
import json
import numpy as np
from scipy import linalg
from sipi import coupled_microstrip, CrossSectionDocument
from sipi.constants import mu_0, epsilon_0
from sipi.dielectric import DebyeDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances as seek
from test_pair_line_goal import document as single_document

F=np.array([.5e9,1e9,2e9]);A=np.array([[1.,-1.],[.5,.5]])


def document(width,gap,*,box=24e-3,air=10e-3):
    raw=single_document(width,gap,box=box,air=air).to_dict();raw['frequency_hz']=F.tolist()
    return PanelTransmissionLineDocument(TransmissionLineDocument.from_dict(raw))


def independent(line):
    actual=line.characteristic().z_characteristic
    for i,f in enumerate(F):
        z=line.R[i]+2j*np.pi*f*line.L[i];y=line.G[i]+2j*np.pi*f*line.C[i]
        scale=np.sqrt(abs(z).max()/abs(y).max())
        roots,vectors=linalg.eig(np.block([[np.zeros_like(z),z/scale],[scale*y,np.zeros_like(y)]]))
        mask=roots.imag>0
        assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
        v=vectors[:,mask];expected=scale*v[:2]@np.linalg.inv(v[2:])
        assert abs(actual[i]-expected).max()/abs(expected).max()<=1e-10
        np.testing.assert_allclose(np.diag(A@actual[i]@A.T).real,np.diag(A@expected@A.T).real,rtol=1e-10,atol=0)


def test_asymmetric_lossy_search_all_frequencies_refinements_and_outer_domains():
    goal=seek(document,[[.4e-3,.9e-3],[.2e-3,.6e-3]],F,[[110.,40.]]*3,
        tolerances=[[.5,.25]]*3,initial=[.7e-3,.35e-3],max_evaluations=64)
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert len(goal.history)<=64 and goal.result.input_json==goal.input_json
    assert [r.evaluation.stage for r in goal.refinements]==['volume-refinement','panel-refinement','joint-refinement']
    for row,line in [(next(x for x in goal.history if x.input_json==goal.input_json),goal.result)]+[(r.evaluation,r.result) for r in goal.refinements]:
        assert np.all(abs(np.array(row.impedances)-goal.targets)<=goal.tolerances)
        assert np.all(abs(np.array(row.impedances)/goal.impedances-1)<=.005)
        assert line.input_json==row.input_json
        independent(line)
    joint=goal.refinements[-1];base=np.asarray(joint.evaluation.impedances);values=[base]
    for refined in goal.refinements[:2]:
        assert np.all(abs(base/refined.evaluation.impedances-1)<=.005)
    for box,air in [(36e-3,15e-3),(48e-3,20e-3)]:
        raw=document(*goal.parameters,box=box,air=air).to_dict()
        raw['line']['cross_section']['mesh']=joint.document.to_dict()['line']['cross_section']['mesh']
        raw['panel']=joint.document.panel_options
        line=PanelTransmissionLineDocument.from_dict(raw).analyze();independent(line)
        q=np.diagonal(line.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real
        values.append(q)
        assert np.all(abs(q-goal.targets)<=goal.tolerances) and np.all(abs(q/base-1)<=.005)
    changes=abs(np.diff(np.asarray(values),axis=0))
    assert np.all(changes[1]<changes[0])


def test_uniform_debye_material_invariant_at_matched_initial_point():
    def factory(strength,pole):
        section=coupled_microstrip(width=.3e-3,gap=.2e-3,substrate_height=.5e-3,eps_r=4.,
            thickness=35e-6,air_height=2e-3,box_width=6e-3)
        material=DebyeDielectric(3.,(strength,),(pole,))
        line=TransmissionLineDocument(CrossSectionDocument(section,mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1)),
            F,materials=dict(substrate=material,air=material),length=0.,conductor=dict(kind='perfect'),schema='sipi.transmission-line/6')
        return PanelTransmissionLineDocument(line)
    doc=factory(.7,1e9);c0=panel_surface_current_factors(doc.line.cross_section.section).C0
    eps=3.+.7/(1+1j*F/1e9)
    expected=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(c0) for e in eps])
    target=np.diagonal(A@expected@A.T,axis1=1,axis2=2).real
    goal=seek(factory,[[.5,.9],[.8e9,1.2e9]],F,target,tolerances=target*.005,initial=[.7,1e9],max_evaluations=4)
    assert len(goal.history)==4 and goal.parameters==(.7,1e9)
    for physical,row in [(goal.result,goal.history[0])]+[(r.result,r.evaluation) for r in goal.refinements]:
        assert json.loads(row.input_json)['line']['materials']==doc.to_dict()['line']['materials']
        reference=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(physical.current_factors.C0) for e in eps])
        actual=physical.characteristic().z_characteristic
        assert abs(actual-reference).max()/abs(reference).max()<=1e-10
        np.testing.assert_allclose(row.impedances,np.diagonal(A@reference@A.T,axis1=1,axis2=2).real,rtol=1e-10,atol=0)
        np.testing.assert_allclose(physical.C,eps.real[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        np.testing.assert_allclose(physical.G,(-2*np.pi*F*eps.imag)[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        assert np.all(physical.R==0)
