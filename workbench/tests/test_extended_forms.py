"""Registered forms preserve field matrices and independent boundary waves."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
from scipy.linalg import expm
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute,TEMPLATES,EXTENDED_TEMPLATES,FORWARD_PAIR_TEMPLATES
from sipi.template_document import TemplateSectionDocument
from sipi.design_document import ImpedanceDesignDocument

CASES={r['template']:r['resolved_parameters'] for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/template_section/reference.json').read_text())['cases']}
CASES.update({r['template']:r['resolved_parameters'] for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/layered_microstrip/inputs.json').read_text())['cases']})
CASES.update({r['template']:r['resolved_parameters'] for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/asymmetric_layered_microstrip/inputs.json').read_text())['cases']})
CASES.update({r['template']:r['resolved_parameters'] for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/layered_grounded_coplanar/inputs.json').read_text())['cases']})
MESH=dict(edge_size=8e-6,far_size=.3e-3,grade=.25)
SETTINGS=dict(start_hz=0.,stop_hz=2e8,points=3,length=.075,resistance=5.3,z_ref=47.)


@pytest.mark.parametrize('name',sorted(TEMPLATES))
def test_all_forms_full_network_matches_independent_voltage_current_boundary(name):
    req=dict(template=name,parameters=CASES[name],mesh=MESH)
    doc=TemplateSectionDocument(name,CASES[name],mesh=MESH)
    line=doc.cross_section.analyze()
    result=execute(dict(**req,action='network',network=SETTINGS))
    assert result['document']==doc.cross_section.to_dict()
    for key in ('C','C0','L','C_loss'):
        np.testing.assert_array_equal(result['line'][key],getattr(line,key))
    if name in FORWARD_PAIR_TEMPLATES:
        assert result['line']['z_diff_forward']==line.z_diff_forward
        assert not {'z_diff','z_common','eps_eff_odd'} & result['line'].keys()
    n=len(line.names);eye=np.eye(n);zero=np.zeros((n,n));expected=[]
    for f in result['network']['frequency']:
        z=5.3*eye+2j*np.pi*f*line.L;y=line.G(f)+2j*np.pi*f*line.C
        transfer=expm(-.075*np.block([[zero,z],[y,zero]]))
        av=np.block([[eye,zero],[eye/47.,zero]])
        bv=np.block([[eye,zero],[-eye/47.,zero]])
        af=np.block([[zero,eye],[zero,-eye/47.]])
        bf=np.block([[zero,eye],[zero,eye/47.]])
        expected.append(np.linalg.solve(bf-transfer@bv,transfer@av-af))
    actual=np.array(result['network']['real'])+1j*np.array(result['network']['imag'])
    np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-11)
    np.testing.assert_allclose(actual,actual.transpose(0,2,1),rtol=1e-10,atol=1e-11)
    assert all(np.linalg.svd(s,compute_uv=False)[0]<=1+1e-11 for s in actual)


@pytest.mark.parametrize('name',EXTENDED_TEMPLATES)
def test_extended_study_retains_forward_launch_and_fixed_mesh(name):
    p=CASES[name];key='left_width' if 'left_width' in p else 'width'
    req=dict(template=name,parameters=p,mesh=MESH,action='study',study=dict(
        mode='sweep',points=2,seed=31,variables=[dict(parameter=key,lower=p[key]*.99,upper=p[key]*1.01)]))
    study=execute(req)['study'];assert study['quantity']=='z_diff_forward'
    assert study['failed']==0 and len(study['rows'])==2
    for row in study['rows']:
        assert row['impedance']==row['line']['z_diff_forward']
        assert row['document']['mesh']==study['nominal_document']['mesh']


@pytest.mark.parametrize('name',EXTENDED_TEMPLATES)
def test_extended_target_saved_replay_preserves_history_and_refinement(name):
    p=CASES[name];key='left_width' if 'left_width' in p else 'width'
    lower,upper=p[key]*.99,p[key]*1.01
    target=TEMPLATES[name](**{**p,key:lower}).analyze(**MESH).z_diff_forward
    options=dict(bounds=[lower,upper],target=target,tolerance=3.)
    if key!='width': options['variable']=key
    req=dict(template=name,parameters=p,mesh=MESH,design=options)
    saved=execute(dict(**req,action='design-document'))['document_text']
    replay=ImpedanceDesignDocument.loads(saved).solve()
    result=execute(dict(**req,action='design'))
    assert result['design']['history']==[vars(r) for r in replay.history]
    assert result['design']['history'][-1]['stage']=='refinement'
    assert result['design']['refined_impedance']==replay.refined_impedance
    assert abs(replay.refined_residual)<=3. and abs(replay.residual)<=3.
    assert lower<=replay.parameter<=upper
    assert result['line']['forward_launch']['quantity']=='z_diff_forward'
