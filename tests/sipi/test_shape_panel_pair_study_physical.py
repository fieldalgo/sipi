# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual paired manufacturing rows and separately retained finite comparisons."""
import json
import numpy as np
import pytest

from sipi.constants import epsilon_0,mu_0
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument,shape_current_record
from sipi.panel_shape_conductor import panel_shape_current_factors
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from test_execution_record import ARTIFACTS
from test_layered_panel_goal import material
from test_layered_metal import transfer
from test_shape_panel_pair_goal_physical import independent,snapshot


def document(coated=False):
    source=ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=.5e-3,right_width=.5e-3,gap=.3e-3,substrate_height=.2e-3,
             eps_r=1.,tan_delta=0.,left_thickness=35e-6,right_thickness=50e-6,
             box_width=.008,air_height=.00375),
        quantity='z_diff_forward',frequency=1e9,materials={},
        mesh=dict(edge_size=10e-6,far_size=.2e-3,grade=.1),
        sampling=dict(kind='corners',variables=[dict(name='left_width',lower=.45e-3,upper=.55e-3),
                                              dict(name='gap',lower=.25e-3,upper=.35e-3)]))
    metal=(material() if coated else dict(conductivity=58e6,relative_permeability=1.,roughness={'kind':'smooth'}))
    conductor=dict(kind='surface-boundaries',conductors={'positive':metal,'negative':metal},
                   reference=metal,ground_thickness=35e-6)
    old=PanelForwardPairStudyDocument(source,conductor=conductor,panels_per_edge=16,
        ground_modes=512,interpolation_degree=16,
        schema='sipi.panel-forward-pair-study/2' if coated else 'sipi.panel-forward-pair-study/1')
    return ShapePanelForwardPairStudyDocument(old)


@pytest.fixture(scope='module',params=[False,True],ids=['legacy','coated'])
def actual(request):
    doc=document(request.param)
    return request.param,doc,doc.analyze(max_evaluations=4)


def identities(line,coated):
    np.testing.assert_array_equal(line.C,line.current_factors.C0[None])
    np.testing.assert_array_equal(line.G,np.zeros_like(line.C))
    np.testing.assert_allclose(line.dielectric.L@line.current_factors.C0,
        mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
    omega=2*np.pi*line.frequency[0]
    surface=transfer(line.frequency[0]) if coated else np.sqrt(1j*omega*mu_0/58e6)
    np.testing.assert_allclose(line.R[0]+1j*omega*line.conductor.L_internal[0],
        surface*line.current_factors.total,rtol=1e-10,atol=0.)
    return independent(line)


def test_actual_corner_fields_uniform_limits_and_independent_networks(actual,record_property):
    coated,doc,result=actual
    record_property('shape_study_actual',json.dumps(result.to_dict(),allow_nan=False))
    assert result.failed==0 and len(result.rows)==4
    fields=[snapshot(row.result) for row in result.rows]
    record_property('shape_study_fields',json.dumps(fields,allow_nan=False))
    np.testing.assert_array_equal([r.sample_values for r in result.rows],doc.samples())
    record_property('shape_study_independent',json.dumps([identities(row.result,coated) for row in result.rows]))


def test_actual_common_receipt_keeps_every_current_sample(actual,monkeypatch):
    _,doc,result=actual;values={r.input_json:r.result for r in result.rows};calls=[]
    def replay(self):
        calls.append(self.dumps());return values[self.dumps()]
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',replay)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4);receipt=request.run()
    assert receipt['execution']['status']=='complete' and receipt['execution']['result']==result.to_dict()
    assert calls==[r.input_json for r in result.rows]
    saved=SavedExecutionRecord(request,receipt,run_id='shape-study:actual',artifacts=ARTIFACTS)
    monkeypatch.setattr(ShapePanelTransmissionLineDocument,'analyze',lambda *a,**k:pytest.fail('restore solved'))
    assert SavedExecutionRecord.loads(saved.dumps()).receipt==receipt


def test_selected_corner_refinements_reject_small_outer_and_qualify_large_currents(actual,record_property):
    coated,_,study=actual;row=study.rows[3 if coated else 0]
    original=json.loads(row.input_json);records=[snapshot(row.result)]
    results=[row.result]
    for stage in ('volume','panel','joint','outer:16mm','outer:32mm'):
        raw=json.loads(row.input_json)
        cross=raw['line']['line']['cross_section']
        if stage!='panel':
            for key in ('edge_size','far_size','grade'):cross['mesh'][key]*=.5
        if stage!='volume':raw['line']['panel']['panels_per_edge']=32
        if stage.startswith('outer:'):
            factor=2 if stage=='outer:16mm' else 4
            cross['box']['width']*=factor
            cross['layers'][-1]['thickness']+=(factor-1)*sum(v['thickness'] for v in original['line']['line']['cross_section']['layers'])
            raw['line']['panel']['ground_modes']*=factor
        try:
            line=ShapePanelTransmissionLineDocument.from_dict(raw).analyze()
        except Exception as error:
            record_property('shape_study_axis_failure',json.dumps(dict(stage=stage,input=raw,
                cause=error.to_dict() if hasattr(error,'to_dict') else str(error),completed=records),allow_nan=False))
            raise
        results.append(line);records.append(snapshot(line))
    def change(a,b,key):
        aa=a.current_factors.C0 if key=='C0' else a.R
        bb=b.current_factors.C0 if key=='C0' else b.R
        return float(np.linalg.norm(aa-bb)/max(np.linalg.norm(aa),np.linalg.norm(bb)))
    panel={k:change(results[0],results[2],k) for k in ('C0','R')}
    outer={k:[change(results[3],results[4],k),change(results[4],results[5],k)] for k in ('C0','R')}
    record_property('shape_study_axes',json.dumps(dict(fields=records,panel=panel,outer=outer),allow_nan=False))
    # Bounded whole-matrix observations; these do not certify small mutual entries.
    assert max(panel.values())<=1e-3
    assert outer['C0'][1]<outer['C0'][0] and outer['C0'][1]<=1e-3
    # This small domain is an explicit counterexample, not an accepted outer gate.
    accepted=max(outer['R'])<=1e-3
    record_property('small_outer_accepted',json.dumps(accepted))
    assert not accepted
    np.testing.assert_array_equal(results[0].R,results[1].R)
    np.testing.assert_array_equal(results[2].C,results[3].C)
    for line in results:identities(line,coated)

    # Additional current-only boxes; no large-domain volume solve is claimed.
    source=json.loads(results[-1].input_json)
    width=source['line']['line']['cross_section']['box']['width']
    height=sum(v['thickness'] for v in source['line']['line']['cross_section']['layers'])
    extra=[];current_records=[]
    for width_mm,panels,modes in ((64,32,4096),(128,32,4096),(128,32,2048),(128,64,4096)):
        data=json.loads(results[-1].input_json)
        cross=data['line']['line']['cross_section'];factor=width_mm/1000/width
        cross['box']['width']*=factor;cross['layers'][-1]['thickness']+=(factor-1)*height
        data['line']['panel'].update(panels_per_edge=panels,ground_modes=modes)
        doc=ShapePanelTransmissionLineDocument.from_dict(data)
        try:
            current=panel_shape_current_factors(doc.line.line.cross_section.section,**doc.current_options)
        except Exception as error:
            record_property('extended_current_failure',json.dumps(dict(input=data,
                error_type=type(error).__name__,message=str(error),completed=current_records),allow_nan=False))
            raise
        extra.append(current)
        current_records.append(dict(input=data,current_solver=shape_current_record(current,doc.current_options)))
    def relative(a,b,key):
        a,b=(a.C0,b.C0) if key=='C0' else (a.total,b.total)
        return float(np.linalg.norm(a-b)/max(np.linalg.norm(a),np.linalg.norm(b)))
    series=[results[-1].current_factors,*extra[:2]]
    extended={k:[relative(series[0],series[1],k),relative(series[1],series[2],k)] for k in ('C0','Q')}
    controls={label:{k:relative(extra[1],extra[i],k) for k in ('C0','Q')}
              for label,i in (('modes',2),('panels',3))}
    record_property('extended_current_axes',json.dumps(dict(fields=current_records,
        outer=extended,controls=controls),allow_nan=False))
    assert extended['C0'][1]<extended['C0'][0] and extended['C0'][1]<=1e-3
    assert max(extended['Q'])<=1e-3
    assert max(v for row in controls.values() for v in row.values())<=1e-3
    # Every boundary uses the same metal in these two fixtures: R=Re(Zs)*Q.
    # The relative Q criterion is therefore also the relative R criterion.
