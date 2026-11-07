# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved Norton circuits: explicit units, source identity and field budgets."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import LineNetwork, terminate_norton_network
from sipi.circuit_document import _network_input, _complex_value
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.norton_circuit import NortonCircuitDocument
from test_periodic_document import KINDS, FREQUENCY, source, field, decoded


def document(kind='rlgc', *, pair=False, basis='single-ended'):
    raw=field(pair=True) if pair else source(kind)
    _,_,frequency,names=_network_input(raw)
    if basis=='mixed-mode':names=('d_near','d_far','c_near','c_far')
    count=len(frequency)
    currents={name:dict(real=[.001*(i+1)]*count,imag=(np.arange(count)*.0002).tolist())
        for i,name in reversed(list(enumerate(names)))}
    admittances={name:dict(real=[.01+.005*i]*count,imag=(np.arange(count)*.001).tolist())
        for i,name in enumerate(names)}
    currents[names[-1]]=0.;admittances[names[-1]]=0.
    return NortonCircuitDocument(raw,source_currents=currents,
        termination_admittances=admittances,basis=basis)


@pytest.mark.parametrize('kind',KINDS)
def test_all_sources_normalize_without_fields_and_snapshot(kind,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization solved fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(VolumeLineDocument,'analyze',forbidden)
    doc=document(kind)
    assert doc.frequency_count==3
    assert normalize_saved(doc.dumps())==NortonCircuitDocument.loads(doc.dumps()).dumps()==doc.dumps()
    copy=doc.to_dict();copy['source_currents'].clear()
    assert doc.to_dict()['source_currents']
    assert 'sipi.norton-circuit/1' in saved_schemas()


def direct(doc):
    data=doc.to_dict();obj,_,frequency,_=_network_input(data['network'])
    original=obj if isinstance(obj,LineNetwork) else obj.analyze().network
    net=original.mixed_mode() if data['basis']=='mixed-mode' else original
    currents,loads=({name:_complex_value(value,len(frequency))[0] for name,value in data[key].items()}
        for key in ('source_currents','termination_admittances'))
    return original,net,terminate_norton_network(net,source_currents=currents,termination_admittances=loads)


@pytest.mark.parametrize('kind',KINDS[:5])
def test_exact_api_json_diagnostics_and_per_frequency_power(kind):
    doc=document(kind);original,network,expected=direct(doc)
    actual=NortonCircuitDocument.loads(doc.dumps()).analyze(max_evaluations=3)
    assert actual.input_json==doc.dumps()
    np.testing.assert_array_equal(actual.source_network.s,original.s)
    np.testing.assert_array_equal(actual.network.s,network.s)
    out=execute_saved(doc.dumps(),max_evaluations=3)
    assert out['status']=='complete' and out['error'] is None and out['input']==doc.to_dict()
    result=out['result']
    assert result['coverage']=='sampled-frequency-boundary'
    assert result['power_convention']=='dc-weight-one-positive-peak'
    assert 'mean_power_w' not in result
    np.testing.assert_array_equal(decoded(result['network']['s']),network.s)
    np.testing.assert_array_equal(decoded(result['source_network']['s']),original.s)
    for key,attribute in [('source_current_a','source_currents'),('termination_admittance_s','termination_admittances'),
        ('incident_sqrt_w','a'),('reflected_sqrt_w','b'),('voltage_v','voltage'),('current_a','current')]:
        np.testing.assert_array_equal(decoded(result['response'][key]),getattr(expected,attribute))
        np.testing.assert_array_equal(getattr(actual.response,attribute),getattr(expected,attribute))
    for key in ('condition_number','kcl_residual','wave_residual'):
        np.testing.assert_array_equal(result['response'][key],getattr(expected,key))
    for key,attribute in [('network','network_power'),('terminations','termination_power'),('sources','source_power')]:
        np.testing.assert_array_equal(result['frequency_power_w'][key],getattr(expected,attribute))
    np.testing.assert_allclose(expected.source_power,expected.network_power+expected.termination_power,atol=1e-12,rtol=0)
    assert np.max(abs(expected.current[:,-1]))<1e-12
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('pair',[False,True])
def test_actual_pec_field_and_mixed_mode_once(pair,monkeypatch):
    doc=document('transmission-line',pair=pair,basis='mixed-mode' if pair else 'single-ended')
    _,net,expected=direct(doc)
    calls=[];original=TransmissionLineDocument.analyze
    def counted(self):calls.append(self.dumps());return original(self)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',counted)
    result=doc.analyze(max_evaluations=3)
    assert len(calls)==1 and result.extraction.input_json==calls[0]
    np.testing.assert_allclose(result.network.s,net.s,atol=1e-12,rtol=0)
    for key in ('a','b','voltage','current','network_power','termination_power','source_power'):
        np.testing.assert_allclose(getattr(result.response,key),getattr(expected,key),atol=1e-12,rtol=0)
    assert result.response.basis==doc.to_dict()['basis']
    np.testing.assert_array_equal(result.response.network.z_ref,net.z_ref)


@pytest.mark.parametrize('kind',['transmission-line','volume-line'])
def test_budget_and_single_source_extraction(kind,monkeypatch):
    doc=document(kind);cls=TransmissionLineDocument if kind=='transmission-line' else VolumeLineDocument
    _,_,_,names=_network_input(doc.to_dict()['network'])
    net=LineNetwork(FREQUENCY,np.zeros((3,len(names),len(names))),50.,names)
    calls=[]
    def fake(self):calls.append(self.dumps());return SimpleNamespace(network=net)
    monkeypatch.setattr(cls,'analyze',fake)
    with pytest.raises(ValueError,match='before field/feedback'):doc.analyze(max_evaluations=2)
    with pytest.raises(ValueError,match='before field/feedback'):execute_saved(doc.dumps(),max_evaluations=2)
    assert calls==[]
    result=doc.analyze(max_evaluations=3)
    assert len(calls)==1 and result.extraction.network is net


def test_budget_precedes_boundary_feedback(monkeypatch):
    import sipi.norton_circuit as module
    def forbidden(*args,**kwargs):pytest.fail('budget failure called boundary solver')
    monkeypatch.setattr(module,'terminate_norton_network',forbidden)
    with pytest.raises(ValueError,match='before field/feedback'):document().analyze(max_evaluations=2)


@pytest.mark.parametrize('drift',['frequency','ports','refs','basis'])
def test_source_identity_drift_is_rejected(drift,monkeypatch):
    doc=document('transmission-line');_,_,f,names=_network_input(doc.to_dict()['network'])
    refs=np.full(len(names),50.);basis='single-ended'
    if drift=='frequency':f=f*2
    elif drift=='ports':names=tuple(reversed(names))
    elif drift=='refs':refs[0]=75.
    else:basis='mixed-mode'
    net=LineNetwork(f,np.zeros((3,len(names),len(names))),refs,names,basis)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:SimpleNamespace(network=net))
    with pytest.raises(ValueError,match='changed the saved'):doc.analyze()


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.norton-circuit/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('basis'),lambda d:d.update(basis='wrong'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d['source_currents'].pop('near:s'),lambda d:d['termination_admittances'].pop('near:s'),
    lambda d:d['source_currents'].update(other=0),lambda d:d['termination_admittances'].update(other=0),
    lambda d:d['source_currents'].update({'near:s':True}),
    lambda d:d['source_currents'].update({'near:s':[0]*4}),
    lambda d:d['source_currents'].update({'near:s':dict(real=[0,0,0],imag=0)}),
    lambda d:d['source_currents'].update({'near:s':float('inf')}),
    lambda d:d['source_currents'].update({'near:s':dict(real=0,imag=False)}),
    lambda d:d['termination_admittances'].update({'near:s':True}),
    lambda d:d['termination_admittances'].update({'near:s':-1}),
    lambda d:d['termination_admittances'].update({'near:s':float('inf')}),
    lambda d:d['termination_admittances'].update({'near:s':'open'}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=[.01,-.01,.01],imag=[0,0,0])}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=[.01,.01],imag=[0,0])}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=.01,imag=0,unit='S')}),
    lambda d:d['network'].update(kind='norton-circuit')])
def test_strict_tables_and_schema_before_fields(mutate,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid input solved fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    data=document().to_dict();mutate(data)
    with pytest.raises(ValueError):NortonCircuitDocument.from_dict(data)


@pytest.mark.parametrize('grid',[[1e8],[0.,1e8,3e8],[2e8,5e8,9e8]])
def test_general_frequency_grid_and_single_sample_are_not_periodic_constraints(grid):
    raw=source('rlgc');raw['frequency_hz']=grid
    doc=NortonCircuitDocument(raw,source_currents={'near:s':.001,'far:s':0.},
        termination_admittances={'near:s':.02,'far:s':0.})
    assert doc.frequency_count==len(grid)
    assert normalize_saved(doc.dumps())==doc.dumps()
    result=execute_saved(doc.dumps())
    np.testing.assert_array_equal(result['result']['network']['frequency_hz'],grid)


def test_complex_dc_is_frequency_domain_not_implicitly_real_periodic_input():
    net=LineNetwork([0.,1.],np.full((2,1,1),.1+.2j),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    doc=NortonCircuitDocument(raw,source_currents={'p':dict(real=.001,imag=.001)},
        termination_admittances={'p':dict(real=.02,imag=.01)})
    result=execute_saved(doc.dumps())
    np.testing.assert_array_equal(decoded(result['result']['source_network']['s']),net.s)


def test_constant_canonical_tables_and_zero_drive():
    data=document().to_dict()
    data['source_currents']={name:0 for name in data['source_currents']}
    data['termination_admittances']={name:.02 for name in data['termination_admittances']}
    doc=NortonCircuitDocument.from_dict(data)
    assert doc.to_dict()['termination_admittances']['near:s']==dict(real=.02,imag=0.)
    result=execute_saved(doc.dumps())['result']
    np.testing.assert_array_equal(decoded(result['response']['voltage_v']),0.)
    for values in result['frequency_power_w'].values():np.testing.assert_array_equal(values,0.)


def test_duplicate_nonfinite_json_and_power_overflow_are_not_complete_results():
    doc=document();text=doc.dumps()
    with pytest.raises(ValueError):NortonCircuitDocument.loads(text.replace('"basis":','"basis":"single-ended","basis":',1))
    for value in ('NaN','Infinity','1e999'):
        with pytest.raises(ValueError):NortonCircuitDocument.loads(text.replace('0.0',value,1))
    net=LineNetwork([0.,1.],np.zeros((2,1,1)),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    huge=NortonCircuitDocument(raw,source_currents={'p':1e154},termination_admittances={'p':.02})
    with pytest.raises(ValueError,match='power overflow'):execute_saved(huge.dumps())


def test_floating_open_is_not_partial_success():
    net=LineNetwork([0.,1.],np.ones((2,1,1)),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    doc=NortonCircuitDocument(raw,source_currents={'p':0},termination_admittances={'p':0})
    with pytest.raises(ValueError,match='condition|singular'):execute_saved(doc.dumps())


@pytest.mark.parametrize('bad',[True,1,10001,3.5])
def test_invalid_budget_and_diagnostics(bad):
    doc=document()
    with pytest.raises(ValueError):doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=bad)
    with pytest.raises(ValueError,match='top-level'):execute_saved(doc.dumps(),diagnostics=['characteristic'])
