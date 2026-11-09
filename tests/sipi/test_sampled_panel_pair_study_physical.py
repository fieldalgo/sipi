# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual finite-frequency manufactured samples, convergence and material invariants."""
import json
import numpy as np
from sipi.constants import epsilon_0,mu_0
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import _refinements
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument as Document
from sipi.execution import execute_saved
from test_pair_line_goal_document import source
from test_pair_line_goal import document as original_line
from test_sampled_panel_pair_goal_physical import independent,F,A
from test_panel_pair_study import expected_statistics


def capture(monkeypatch):
    original=Document.analyze;results=[]
    def recorded(self,**kwargs):
        result=original(self,**kwargs);results.append(result);return result
    monkeypatch.setattr(Document,'analyze',recorded)
    return results


def statistics_check(result):
    for f in range(len(F)):
        for i,q in enumerate(result.to_dict()['quantities']):
            expected=expected_statistics([row.values[f][i] for row in result.rows])
            for key in expected:
                np.testing.assert_allclose(result.summary[q][f][key],expected[key],rtol=1e-12,atol=0)


def test_real_four_corners_first_last_refinements_and_outer_domains(monkeypatch):
    captured=capture(monkeypatch);study=source(physical=True).to_dict()
    study['material_evaluation']['frequency_hz']=float(F[0])
    study['sampling']['variables']=[dict(name='left_width',lower=.60e-3,upper=.62e-3),dict(name='gap',lower=.40e-3,upper=.42e-3)]
    doc=Document(study,conductor=original_line(.6e-3,.4e-3).to_dict()['conductor'],frequencies=F.tolist())
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and len(captured)==1
    result=captured[0];assert result.failed==0 and len(result.rows)==4 and output['result']==result.to_dict()
    np.testing.assert_array_equal([row.sample_values for row in result.rows],doc.samples());statistics_check(result)
    for row in result.rows:
        independent(row.result);assert row.result.input_json==row.input_json
    for row in [result.rows[0],result.rows[-1]]:
        nominal=np.asarray(row.values);values=[];joint=None
        for stage,refined in _refinements(row.input_json).items():
            physical=refined.analyze();independent(physical)
            q=np.diagonal(physical.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real
            assert np.all(abs(q/nominal-1)<=.005);values.append(q)
            if stage=='joint-refinement':joint=refined
        base=values[-1];assert all(np.all(abs(base/v-1)<=.005) for v in values[:-1])
        domain_values=[base]
        for box,air in [(36e-3,15e-3),(48e-3,20e-3)]:
            raw=joint.to_dict();raw['line']['cross_section']['box']['width']=box
            for layer in raw['line']['cross_section']['layers']:
                if layer['name']=='air':layer['thickness']=air
            physical=PanelTransmissionLineDocument.from_dict(raw).analyze();independent(physical)
            q=np.diagonal(physical.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real
            assert np.all(abs(q/base-1)<=.005);domain_values.append(q)
        changes=abs(np.diff(np.asarray(domain_values),axis=0))
        assert np.all(changes[1]<changes[0])


def test_correlated_uniform_debye_samples_preserve_material_invariant(monkeypatch):
    captured=capture(monkeypatch);model=DebyeDielectric(3.,(.7,),(1e9,))
    study=ImpedanceStudyDocument('coupled_microstrip',dict(width=.3e-3,gap=.2e-3,substrate_height=.5e-3,
        eps_r=4.,thickness=35e-6,air_height=2e-3,box_width=6e-3),quantity='z_diff_forward',frequency=float(F[0]),
        materials={'substrate':model,'air':model},mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1),
        material_variables={'strength_substrate':dict(region='substrate',path=['strengths',0]),
                            'strength_air':dict(region='air',path=['strengths',0])},
        sampling=dict(kind='normal',count=4,seed=3,correlation=[[1.,1.],[1.,1.]],variables=[
            dict(name='strength_substrate',mean=.7,std=.05),dict(name='strength_air',mean=.7,std=.05)]))
    doc=Document(study,conductor={'kind':'perfect'},frequencies=F.tolist());samples=doc.samples()
    np.testing.assert_array_equal(samples[:,0],samples[:,1]);assert len(np.unique(samples[:,0]))==4
    output=execute_saved(doc.dumps(),max_evaluations=4)
    assert output['status']=='complete' and len(captured)==1
    result=captured[0];assert result.failed==0 and len(result.rows)==4 and output['result']==result.to_dict()
    for row,(strength,_) in zip(result.rows,samples):
        physical=row.result;models=json.loads(row.input_json)['line']['materials']
        assert all(models[k]['parameters']['strengths']==[strength] for k in ['substrate','air'])
        eps=3.+strength/(1+1j*F/1e9)
        reference=np.array([np.sqrt(mu_0*epsilon_0/e)*np.linalg.inv(physical.current_factors.C0) for e in eps])
        actual=physical.characteristic().z_characteristic
        assert abs(actual-reference).max()/abs(reference).max()<=1e-10
        np.testing.assert_allclose(row.values,np.diagonal(A@reference@A.T,axis1=1,axis2=2).real,rtol=1e-10,atol=0)
        np.testing.assert_allclose(physical.C,eps.real[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        np.testing.assert_allclose(physical.G,(-2*np.pi*F*eps.imag)[:,None,None]*physical.current_factors.C0,rtol=1e-12,atol=0)
        assert np.all(physical.R==0)
    statistics_check(result)
