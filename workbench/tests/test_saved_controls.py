"""Quick inputs survive serialization without changing the physical request."""
import json
from pathlib import Path
import sys
import numpy as np
import pytest
import sipi
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from engine import execute, TEMPLATES, ASYMMETRIC_PAIR_TEMPLATES, study_documents, document
from sipi.design_document import ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument
from sipi.quasistatic_line_document import QuasistaticLineDocument
from sipi.execution import execute_saved
CASES={row['template']:row for row in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/template_section/reference.json').read_text())['cases']}
CASES.update({r['template']:r for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/layered_microstrip/inputs.json').read_text())['cases']})
CASES.update({r['template']:r for r in json.loads((Path(__file__).resolve().parents[2]/'tests/sipi/reference_data/asymmetric_layered_microstrip/inputs.json').read_text())['cases']})

MESH=dict(edge_size=8e-6,far_size=.3e-3,grade=.25)
NETWORK=dict(start_hz=0.,stop_hz=2e8,points=3,length=.075,resistance=5.3,z_ref=47.)


def request(name='stripline',kind='study',mode='sweep'):
    p=dict(CASES[name]['supplied_parameters']);variable='left_width' if name in ASYMMETRIC_PAIR_TEMPLATES else 'width'
    width=p[variable];bounds=[width*.99,width*1.01]
    controls=(dict(mode=mode,variables=[dict(parameter=variable,lower=bounds[0],upper=bounds[1])],points=3,seed=31)
              if kind=='study' else dict(bounds=bounds,target=100 if name in ASYMMETRIC_PAIR_TEMPLATES else 50,tolerance=.5,
                                       **({'variable':variable} if name in ASYMMETRIC_PAIR_TEMPLATES else {})) if kind=='design' else NETWORK)
    return dict(action=kind+'-document',template=name,parameters=p,mesh=MESH,**{kind:controls})


@pytest.mark.parametrize('name',sorted(TEMPLATES))
@pytest.mark.parametrize('kind',['design','study','network'])
def test_all_editable_forms_save_and_reopen_without_calculating(name,kind,monkeypatch):
    monkeypatch.setattr(sipi.CrossSection,'mesh',lambda *a,**k:pytest.fail('Save/open meshed'))
    req=request(name,kind);saved=execute(req);opened=execute(dict(action=kind+'-open',text=saved['document_text']))
    assert opened['template']==name
    assert opened['document']['mesh']==document(req).to_dict()['mesh']
    again=execute(dict(action=kind+'-document',template=name,parameters=opened['parameters'],mesh=opened['document']['mesh'],**{kind:opened[kind]}))
    assert json.loads(again['document_text'])==json.loads(saved['document_text'])


@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
@pytest.mark.parametrize('name',sorted(TEMPLATES))
def test_saved_study_preserves_order_exact_samples_and_fixed_mesh(name,mode):
    req=request(name,mode=mode);nominal=document(req);_,samples=study_documents(req,nominal)
    saved=ImpedanceStudyDocument.loads(execute(req)['document_text'])
    rows=saved.sample_parameters()
    for (values,doc),sample in zip(samples,rows):
        assert all(sample[k]==v for k,v in values.items())
        assert doc.mesh_options==saved.to_dict()['mesh']
    assert len(rows)==len(samples)


@pytest.mark.parametrize('kind',['design','study','network'])
@pytest.mark.parametrize('key',['extra','document','document_text'])
def test_save_rejects_unknown_or_conflicting_inputs(kind,key):
    req=request(kind=kind);req[key]={}
    with pytest.raises(ValueError): execute(req)


@pytest.mark.parametrize('mode',['sweep','corners','monte_carlo'])
def test_real_study_quick_and_common_saved_execution_have_identical_rows(mode):
    req=request(mode=mode);saved=execute(req)['document_text']
    quick=execute({**req,'action':'study'})['study'];common=execute_saved(saved)['result']
    assert [r['impedance'] for r in quick['rows']]==[r['value'] for r in common['rows']]
    assert all(r['status']=='complete' for r in quick['rows'])


def test_saved_network_exact_full_matrix_and_touchstone():
    req=request('asymmetric_coupled_stripline',kind='network')
    saved=execute(req)['document_text'];direct=execute({**req,'action':'network'})['network']
    result=QuasistaticLineDocument.loads(saved).analyze()
    np.testing.assert_array_equal(np.array(direct['real'])+1j*np.array(direct['imag']),result.network.s)
    assert direct['touchstone']==result.network.touchstone()


@pytest.mark.parametrize('name',['stripline','coupled_stripline','asymmetric_coupled_stripline'])
def test_real_width_target_replays_same_history_and_refined_result(name):
    req=request(name,kind='design');variable=req['design'].get('variable','width');p=req['parameters'];lower=p[variable]*.99
    line=TEMPLATES[name](**{**p,variable:lower}).analyze(**MESH)
    quantity='z_diff_forward' if name in ASYMMETRIC_PAIR_TEMPLATES else 'z_diff' if name=='coupled_stripline' else 'z0'
    target=line.even_odd()['z_diff'] if quantity=='z_diff' else getattr(line,quantity)
    req['design'].update(target=target,tolerance=3.)
    saved=execute(req)['document_text'];quick=execute({**req,'action':'design'})['design'];result=ImpedanceDesignDocument.loads(saved).solve()
    assert quick['history']==[vars(row) for row in result.history]
    assert quick['impedance']==result.impedance and quick['refined_impedance']==result.refined_impedance
    assert result.history[-1].stage=='refinement'


@pytest.mark.parametrize('kind',['design','study','network'])
def test_bad_open_preserves_caller_request(kind):
    req=request(kind=kind);before=json.dumps(req,sort_keys=True)
    with pytest.raises(ValueError): execute(dict(action=kind+'-open',text='{"schema":1,"schema":2}'))
    assert json.dumps(req,sort_keys=True)==before


def test_nondefault_budget_and_too_many_samples_are_not_silently_changed():
    raw=json.loads(execute(request(kind='design'))['document_text']);raw['max_evaluations']=33
    with pytest.raises(ValueError,match='budget'): execute(dict(action='design-open',text=json.dumps(raw)))
    raw=json.loads(execute(request(mode='monte_carlo'))['document_text']);raw['sampling']['count']=33
    with pytest.raises(ValueError,match='32'): execute(dict(action='study-open',text=json.dumps(raw)))
