# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved mixed circuits: explicit units, source identity and field budgets."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import LineNetwork, terminate_mixed_network
from sipi.circuit_document import _network_input, _complex_value
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.mixed_circuit import MixedCircuitDocument
from test_periodic_document import KINDS, FREQUENCY, source, field, decoded


def document(kind='rlgc', *, pair=False, basis='single-ended'):
    raw=field(pair=True) if pair else source(kind)
    _,_,frequency,names=_network_input(raw)
    if basis=='mixed-mode':names=('d_near','d_far','c_near','c_far')
    count=len(frequency)
    boundaries={}
    for i,name in reversed(list(enumerate(names))):
        if i%2==0:
            boundaries[name]=dict(kind='thevenin',source_voltage=dict(
                real=[.5+.1*i]*count,imag=(np.arange(count)*.02).tolist()),impedance=0 if i==0 else 50.)
        else:
            boundaries[name]=dict(kind='norton',source_current=.001*i,admittance=.02)
    boundaries[names[-1]]=dict(kind='norton',source_current=0.,admittance=0.)
    return MixedCircuitDocument(raw,boundaries=boundaries,basis=basis)



@pytest.mark.parametrize('kind',KINDS)
def test_all_sources_normalize_without_fields_and_snapshot(kind,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization solved fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(VolumeLineDocument,'analyze',forbidden)
    doc=document(kind)
    assert doc.frequency_count==3
    assert normalize_saved(doc.dumps())==MixedCircuitDocument.loads(doc.dumps()).dumps()==doc.dumps()
    copy=doc.to_dict();copy['boundaries'].clear()
    assert doc.to_dict()['boundaries']
    assert 'sipi.mixed-circuit/1' in saved_schemas()


def direct(doc):
    data=doc.to_dict();obj,_,frequency,_=_network_input(data['network'])
    original=obj if isinstance(obj,LineNetwork) else obj.analyze().network
    net=original.mixed_mode() if data['basis']=='mixed-mode' else original
    boundaries={name:{key:(value if key=='kind' else _complex_value(value,len(frequency))[0])
        for key,value in item.items()} for name,item in data['boundaries'].items()}
    return original,net,terminate_mixed_network(net,boundaries)



@pytest.mark.parametrize('kind',KINDS[:5])
def test_exact_api_json_diagnostics_and_per_frequency_power(kind):
    doc=document(kind);original,network,expected=direct(doc)
    actual=MixedCircuitDocument.loads(doc.dumps()).analyze(max_evaluations=3)
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
    for key,attribute in [('source_voltage_v','source_voltages'),('series_impedance_ohms','series_impedances'),
        ('source_current_a','source_currents'),('shunt_admittance_s','shunt_admittances'),
        ('incident_sqrt_w','a'),('reflected_sqrt_w','b'),('voltage_v','voltage'),('current_a','current')]:
        np.testing.assert_array_equal(decoded(result['response'][key]),getattr(expected,attribute))
        np.testing.assert_array_equal(getattr(actual.response,attribute),getattr(expected,attribute))
    for key in ('condition_number','boundary_residual','wave_residual'):
        np.testing.assert_array_equal(result['response'][key],getattr(expected,key))
    assert result['response']['kinds']==list(expected.kinds)
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
    import sipi.mixed_circuit as module
    def forbidden(*args,**kwargs):pytest.fail('budget failure called boundary solver')
    monkeypatch.setattr(module,'terminate_mixed_network',forbidden)
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
    lambda d:d.update(schema='sipi.mixed-circuit/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('basis'),lambda d:d.update(basis='wrong'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d.pop('boundaries'),lambda d:d.update(boundaries=[]),
    lambda d:d['boundaries'].pop('near:s'),lambda d:d['boundaries'].update(other={}),
    lambda d:d['boundaries'].update({'near:s':'short'}),
    lambda d:d['boundaries']['near:s'].update(kind='wrong'),
    lambda d:d['boundaries']['near:s'].update(extra=0),
    lambda d:d['boundaries']['near:s'].pop('source_voltage'),
    lambda d:d['boundaries']['far:s'].pop('admittance'),
    lambda d:d['boundaries']['near:s'].update(impedance=True),
    lambda d:d['boundaries']['far:s'].update(source_current=True),
    lambda d:d['boundaries']['near:s'].update(source_voltage=float('inf')),
    lambda d:d['boundaries']['far:s'].update(admittance=float('inf')),
    lambda d:d['boundaries']['near:s'].update(impedance=-1),
    lambda d:d['boundaries']['far:s'].update(admittance=-1),
    lambda d:d['boundaries']['near:s'].update(source_voltage=dict(real=[1,2,3],imag=0)),
    lambda d:d['boundaries']['near:s'].update(impedance=dict(real=[1,2],imag=[0,0])),
    lambda d:d['boundaries']['far:s'].update(admittance=dict(real=[.01,-.01,.01],imag=[0,0,0])),
    lambda d:d['boundaries']['far:s'].update(admittance=dict(real=0,imag=False)),
    lambda d:d['boundaries']['near:s'].update(source_voltage=dict(real=1,imag=0,unit='V')),
    lambda d:d['network'].update(kind='mixed-circuit')])
def test_strict_topology_tables_and_schema_before_fields(mutate,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid input solved fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    data=document().to_dict();mutate(data)
    with pytest.raises(ValueError):MixedCircuitDocument.from_dict(data)


@pytest.mark.parametrize('grid',[[1e8],[0.,1e8,3e8],[2e8,5e8,9e8]])
def test_general_frequency_grid_is_not_constrained_to_periodic(grid):
    raw=source('rlgc');raw['frequency_hz']=grid
    doc=MixedCircuitDocument(raw,boundaries={
        'near:s':dict(kind='thevenin',source_voltage=1.,impedance=0.),
        'far:s':dict(kind='norton',source_current=0.,admittance=0.)})
    assert doc.frequency_count==len(grid) and normalize_saved(doc.dumps())==doc.dumps()
    result=execute_saved(doc.dumps())['result']
    np.testing.assert_array_equal(result['network']['frequency_hz'],grid)
    np.testing.assert_allclose(decoded(result['response']['voltage_v'])[:,0],1,atol=1e-12,rtol=0)
    np.testing.assert_allclose(decoded(result['response']['current_a'])[:,1],0,atol=1e-12,rtol=0)


def test_saved_lossless_ideal_voltage_open_line_analytic_response():
    f=np.array([0.,1e8,2e8]);theta=2*np.pi*f*.1*5e-9
    raw=dict(kind='rlgc',frequency_hz=f.tolist(),R=[[0.]],G=[[0.]],L=[[250e-9]],
        C=[[100e-12]],length_m=.1,reference_ohms=50.,names=['s'])
    doc=MixedCircuitDocument(raw,boundaries={
        'near:s':dict(kind='thevenin',source_voltage=1.,impedance=0.),
        'far:s':dict(kind='norton',source_current=0.,admittance=0.)})
    result=execute_saved(doc.dumps())['result']['response']
    np.testing.assert_allclose(decoded(result['voltage_v']),
        np.column_stack((np.ones(3),1/np.cos(theta))),atol=1e-12,rtol=0)
    np.testing.assert_allclose(decoded(result['current_a']),
        np.column_stack((1j*np.tan(theta)/50,np.zeros(3))),atol=1e-12,rtol=0)


def test_complex_dc_snapshot_and_zero_drive():
    net=LineNetwork([0.,1.],np.full((2,1,1),.1+.2j),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    doc=MixedCircuitDocument(raw,boundaries={'p':dict(kind='thevenin',
        source_voltage=dict(real=1,imag=.1),impedance=dict(real=50,imag=5))})
    result=execute_saved(doc.dumps())['result']
    np.testing.assert_array_equal(decoded(result['source_network']['s']),net.s)
    data=doc.to_dict();data['boundaries']['p']['source_voltage']=0
    zero=execute_saved(MixedCircuitDocument.from_dict(data).dumps())['result']
    np.testing.assert_array_equal(decoded(zero['response']['voltage_v']),0.)
    for value in zero['frequency_power_w'].values():np.testing.assert_array_equal(value,0.)
    assert doc.to_dict()['boundaries']['p']['source_voltage']==dict(real=1.,imag=.1)


def test_duplicate_nonfinite_floating_and_overflow_are_not_complete():
    text=document().dumps()
    with pytest.raises(ValueError):MixedCircuitDocument.loads(text.replace('"kind":','"kind":"norton","kind":',1))
    for value in ('NaN','Infinity','1e999'):
        with pytest.raises(ValueError):MixedCircuitDocument.loads(text.replace('0.0',value,1))
    for reflection,boundary in [(1.,dict(kind='norton',source_current=0,admittance=0)),
                               (-1.,dict(kind='thevenin',source_voltage=1,impedance=0))]:
        net=LineNetwork([0,1],np.full((2,1,1),reflection),50.,('p',))
        raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
        doc=MixedCircuitDocument(raw,boundaries={'p':boundary})
        with pytest.raises(ValueError,match='condition|singular'):execute_saved(doc.dumps())
    raw=dict(kind='touchstone',text=LineNetwork([0,1],np.zeros((2,1,1)),50.,('p',)).touchstone(),
        ports=1,port_names=['p'])
    huge=MixedCircuitDocument(raw,boundaries={'p':dict(kind='thevenin',source_voltage=1e200,impedance=50)})
    with pytest.raises(ValueError,match='power overflow'):execute_saved(huge.dumps())


@pytest.mark.parametrize('bad',[True,1,10001,3.5])
def test_invalid_budget_and_diagnostics(bad):
    doc=document()
    with pytest.raises(ValueError):doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=bad)
    with pytest.raises(ValueError,match='top-level'):execute_saved(doc.dumps(),diagnostics=['characteristic'])
