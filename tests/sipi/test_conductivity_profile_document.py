# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved constitutive profile inputs: strict replay and pre-ODE limits."""
import json
import warnings

import numpy as np
import pytest

from sipi import GaussianConductivityProfile, ConductivityProfileDocument, ConductivityProfileResult
from sipi.constants import mu_0, epsilon_0
from sipi.execution import normalize_saved, execute_saved, saved_schemas
from crosscheck import require_tool


def document(*, rms=1e-6, cutoff=8, frequency=(1e9,4e9,10e9)):
    return ConductivityProfileDocument(GaussianConductivityProfile(conductivity=58e6,rms_m=rms),
                                       frequency,cutoff_rms=cutoff)


def test_canonical_replay_and_input_isolation_without_integration(monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('parsing integrated the profile')
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',forbidden)
    doc=document();raw=doc.to_dict();restored=ConductivityProfileDocument.from_dict(raw)
    canonical=restored.dumps();raw['model']['rms_m']=0;raw['frequency_hz'][0]=0
    assert doc.dumps()==restored.dumps()==canonical
    assert normalize_saved(canonical)==canonical
    assert ConductivityProfileDocument.loads(canonical).dumps()==canonical
    f=doc.frequency;f[0]=0
    assert doc.frequency[0]==1e9 and doc.profile.rms_m==1e-6 and doc.sample_count==3
    assert 'sipi.conductivity-profile/1' in saved_schemas()


def test_saved_execution_direct_and_independent_reference():
    tool=require_tool('scikit-rf');doc=document(cutoff=5)
    output=execute_saved(doc.dumps(),max_evaluations=3)
    assert output['schema']=='sipi.execution/1' and output['status']=='complete' and output['error'] is None
    assert output['input']==doc.to_dict()
    result=output['result'];z=np.array(result['surface_impedance_ohms']['real'])+1j*np.array(result['surface_impedance_ohms']['imag'])
    direct=doc.profile.analyze(doc.frequency,cutoff_rms=doc.cutoff_rms)
    np.testing.assert_array_equal(z,direct.impedance)
    np.testing.assert_array_equal(result['skin_depth_m'],direct.skin_depth)
    assert result['frequency_hz']==doc.frequency.tolist()
    assert result['reference_plane_m']==-doc.cutoff_rms*doc.profile.rms_m
    assert result['reference_plane_m']==direct.reference_plane_m and result['cutoff_rms']==5
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        reference=tool.tlineFunctions.surface_impedance(doc.frequency,dict(sigma=58e6,mu_r=1,ep_r=1),rms_roughness=1e-6,rtol=1e-9)
    assert not caught
    np.testing.assert_allclose(z,reference,rtol=1e-6,atol=0)
    assert json.loads(json.dumps(output,allow_nan=False))==output


def test_smooth_saved_limit_and_single_sample():
    doc=document(rms=0,frequency=[1e9]);out=execute_saved(doc.dumps(),max_evaluations=2)['result']
    z=complex(out['surface_impedance_ohms']['real'][0],out['surface_impedance_ohms']['imag'][0])
    expected=np.sqrt(1j*2*np.pi*1e9*mu_0/(58e6+1j*2*np.pi*1e9*epsilon_0))
    assert z==pytest.approx(expected,rel=1e-12)
    assert out['reference_plane_m']==0 and len(out['frequency_hz'])==1


def test_negative_exterior_reactance_preserved():
    f=1e-3*58e6/(2*np.pi*epsilon_0);delta=1/np.sqrt(np.pi*f*mu_0*58e6)
    doc=document(rms=10*delta,frequency=[f]);out=execute_saved(doc.dumps())['result']
    assert out['surface_impedance_ohms']['imag'][0]<0
    assert out['surface_impedance_ohms']['real'][0]>0
    assert out['reference_plane_m']==-8*doc.profile.rms_m


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.conductivity-profile/2'),
    lambda d:d.pop('cutoff_rms'),lambda d:d.update(units='mm'),lambda d:d.update(model=None),
    lambda d:d['model'].update(kind='smooth'),lambda d:d['model'].pop('rms_m'),
    lambda d:d['model'].update(ra_m=1e-6),lambda d:d['model'].update(rms_m=True),
    lambda d:d['model'].update(conductivity_s_per_m=0),lambda d:d['model'].update(rms_m=np.inf),
    lambda d:d.update(frequency_hz=[0]),lambda d:d.update(frequency_hz=[1e9,1e9]),
    lambda d:d.update(frequency_hz=[True]),lambda d:d.update(frequency_hz=[]),
    lambda d:d.update(frequency_hz=list(range(1,1026))),lambda d:d.update(frequency_hz=[1e30]),
    lambda d:d.update(cutoff_rms=True),lambda d:d.update(cutoff_rms=4.9),
    lambda d:d.update(cutoff_rms=10.1),lambda d:d.update(cutoff_rms=None),
])
def test_invalid_saved_input_before_integrator(mutate,monkeypatch):
    raw=document().to_dict();mutate(raw)
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',lambda *a,**kw:pytest.fail('invalid input solved'))
    with pytest.raises(ValueError):ConductivityProfileDocument.from_dict(raw)
    with pytest.raises(ValueError):normalize_saved(json.dumps(raw))


@pytest.mark.parametrize('token',['NaN','Infinity','1e999'])
def test_nonfinite_json(token):
    text=document().dumps().replace('"rms_m": 1e-06','"rms_m": '+token)
    assert token in text
    for parse in (ConductivityProfileDocument.loads,normalize_saved):
        with pytest.raises(ValueError):parse(text)


@pytest.mark.parametrize('key,value',[('schema','"sipi.conductivity-profile/1"'),
    ('rms_m','1e-6'),('cutoff_rms','8')])
def test_duplicate_json_keys(key,value):
    text=document().dumps();needle='"'+key+'":'
    text=text.replace(needle,needle+value+', '+needle,1)
    for parse in (ConductivityProfileDocument.loads,normalize_saved):
        with pytest.raises(ValueError):parse(text)


@pytest.mark.parametrize('budget',[True,1,0,10001,2.5,None])
def test_invalid_budget_before_solver(budget,monkeypatch):
    doc=document()
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',lambda *a,**kw:pytest.fail('invalid budget solved'))
    with pytest.raises(ValueError):doc.analyze(max_evaluations=budget)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=budget)


def test_frequency_and_input_budgets_and_diagnostics_before_solver(monkeypatch):
    doc=document()
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',lambda *a,**kw:pytest.fail('budget/diagnostics solved'))
    with pytest.raises(ValueError,match='before integration'):doc.analyze(max_evaluations=2)
    with pytest.raises(ValueError,match='before integration'):execute_saved(doc.dumps(),max_evaluations=2)
    with pytest.raises(ValueError,match='max_input_bytes'):execute_saved(doc.dumps(),max_input_bytes=10)
    with pytest.raises(ValueError,match='diagnostics'):execute_saved(doc.dumps(),diagnostics=['modes'])


@pytest.mark.parametrize('changed',['frequency','model','cutoff','type'])
def test_solver_cannot_change_saved_metadata(changed,monkeypatch):
    doc=document();model=doc.profile;f=doc.frequency;cutoff=doc.cutoff_rms
    if changed=='frequency':f=f*1.01
    if changed=='model':model=GaussianConductivityProfile(conductivity=57e6,rms_m=1e-6)
    if changed=='cutoff':cutoff=5
    fake=object() if changed=='type' else ConductivityProfileResult(model,f,np.ones(3)+1j,cutoff)
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',lambda *a,**kw:fake)
    with pytest.raises(ValueError,match='saved model'):doc.analyze()
    with pytest.raises(ValueError,match='saved model'):execute_saved(doc.dumps())


def test_failed_integration_propagates(monkeypatch):
    doc=document()
    def failed(*args,**kwargs):raise RuntimeError('profile integration failed')
    monkeypatch.setattr(GaussianConductivityProfile,'analyze',failed)
    with pytest.raises(RuntimeError,match='integration failed'):execute_saved(doc.dumps())
