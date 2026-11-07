# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved periodic mixed circuits: explicit units, source identity and field budgets."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import LineNetwork, periodic_mixed_response
from sipi.circuit_document import _network_input, _complex_value
from sipi.execution import execute_saved, normalize_saved, saved_schemas
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.periodic_mixed_circuit import PeriodicMixedCircuitDocument
from test_periodic_document import KINDS, FREQUENCY, source, field, decoded


def document(kind='rlgc', *, pair=False, basis='single-ended'):
    raw=field(pair=True) if pair else source(kind)
    _,_,frequency,names=_network_input(raw)
    if basis=='mixed-mode':names=('d_near','d_far','c_near','c_far')
    count=len(frequency)
    t=np.arange(2*count-1)/(2*count-1)
    boundaries={}
    for i,name in reversed(list(enumerate(names))):
        if i%2==0:
            boundaries[name]=dict(kind='thevenin',source_voltage=(.1*i+.2*np.cos(2*np.pi*t+i)).tolist(),impedance=0 if i==0 else 50.)
        else:
            boundaries[name]=dict(kind='norton',source_current=(.001*i+.002*np.sin(2*np.pi*t)).tolist(),admittance=dict(real=[.02]*count,imag=(np.arange(count)*.002).tolist()))
    boundaries[names[-1]]=dict(kind='norton',source_current=0.,admittance=0.)
    return PeriodicMixedCircuitDocument(raw,boundaries=boundaries,basis=basis)



@pytest.mark.parametrize('kind',KINDS)
def test_all_sources_normalize_without_fields_and_snapshot(kind,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization solved fields')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(VolumeLineDocument,'analyze',forbidden)
    doc=document(kind)
    assert doc.sample_count==5
    assert normalize_saved(doc.dumps())==PeriodicMixedCircuitDocument.loads(doc.dumps()).dumps()==doc.dumps()
    copy=doc.to_dict();copy['boundaries'].clear()
    assert doc.to_dict()['boundaries']
    assert 'sipi.periodic-mixed-circuit/1' in saved_schemas()


def direct(doc):
    data=doc.to_dict();obj,_,frequency,_=_network_input(data['network'])
    original=obj if isinstance(obj,LineNetwork) else obj.analyze().network
    net=original.mixed_mode() if data['basis']=='mixed-mode' else original
    boundaries={name:{key:(value if key in ('kind','source_voltage','source_current') else _complex_value(value,len(frequency))[0])
        for key,value in item.items()} for name,item in data['boundaries'].items()}
    return original,net,periodic_mixed_response(net,boundaries)



@pytest.mark.parametrize('kind',KINDS[:5])
def test_exact_time_harmonics_power_and_api_replay(kind):
    doc=document(kind);original,network,expected=direct(doc)
    actual=PeriodicMixedCircuitDocument.loads(doc.dumps()).analyze(max_evaluations=5)
    assert actual.input_json==doc.dumps()
    np.testing.assert_array_equal(actual.source_network.s,original.s)
    np.testing.assert_array_equal(actual.network.s,network.s)
    out=execute_saved(doc.dumps(),max_evaluations=5)
    assert out['status']=='complete' and out['error'] is None and out['input']==doc.to_dict()
    data=out['result'];harmonic=expected.frequency_solution
    assert data['coverage']=='sampled-periodic-steady-state'
    assert data['harmonics']['convention']=='dc-mean-positive-peak'
    assert data['harmonics']['kinds']==list(harmonic.kinds)
    np.testing.assert_array_equal(decoded(data['network']['s']),network.s)
    for key,attribute in [('incident_sqrt_w','incident'),('reflected_sqrt_w','reflected'),
        ('voltage_v','voltage'),('current_a','current'),('time_s','time')]:
        np.testing.assert_array_equal(data['response'][key],getattr(expected.response,attribute))
        np.testing.assert_array_equal(getattr(actual.solution.response,attribute),getattr(expected.response,attribute))
    for key,attribute in [('source_voltage_v','source_voltages'),('source_current_a','source_currents'),
        ('termination_voltage_v','termination_voltages'),('termination_current_a','termination_currents')]:
        np.testing.assert_array_equal(data[key],getattr(expected,attribute))
    for key,attribute in [('source_voltage_v','source_voltages'),('source_current_a','source_currents'),
        ('series_impedance_ohms','series_impedances'),('shunt_admittance_s','shunt_admittances'),
        ('incident_sqrt_w','a'),('reflected_sqrt_w','b'),('voltage_v','voltage'),('current_a','current')]:
        np.testing.assert_array_equal(decoded(data['harmonics'][key]),getattr(harmonic,attribute))
    for key in ('condition_number','boundary_residual','wave_residual'):
        np.testing.assert_array_equal(data['harmonics'][key],getattr(harmonic,key))
    for key,attribute in [('network','network_power'),('terminations','termination_power'),('sources','source_power')]:
        np.testing.assert_array_equal(data['harmonics']['frequency_power_w'][key],getattr(harmonic,attribute))
        assert data['mean_power_w'][key]==sum(data['harmonics']['frequency_power_w'][key])
    from test_periodic_mixed import check_power
    check_power(actual.solution)
    json.dumps(out,allow_nan=False)


@pytest.mark.parametrize('pair',[False,True])
def test_actual_pec_field_and_mixed_mode_once(pair,monkeypatch):
    doc=document('transmission-line',pair=pair,basis='mixed-mode' if pair else 'single-ended')
    _,net,expected=direct(doc)
    calls=[];original=TransmissionLineDocument.analyze
    def counted(self):calls.append(self.dumps());return original(self)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',counted)
    result=doc.analyze(max_evaluations=5)
    assert len(calls)==1 and result.extraction.input_json==calls[0]
    np.testing.assert_allclose(result.network.s,net.s,atol=1e-12,rtol=0)
    for key in ('incident','reflected','voltage','current'):
        np.testing.assert_allclose(getattr(result.solution.response,key),getattr(expected.response,key),atol=1e-12,rtol=0)
    assert result.solution.response.basis==doc.to_dict()['basis']
    np.testing.assert_array_equal(result.solution.response.z_ref,net.z_ref)


@pytest.mark.parametrize('kind',['transmission-line','volume-line'])
def test_budget_and_single_source_extraction(kind,monkeypatch):
    doc=document(kind);cls=TransmissionLineDocument if kind=='transmission-line' else VolumeLineDocument
    _,_,_,names=_network_input(doc.to_dict()['network'])
    net=LineNetwork(FREQUENCY,np.zeros((3,len(names),len(names))),50.,names)
    calls=[]
    def fake(self):calls.append(self.dumps());return SimpleNamespace(network=net)
    monkeypatch.setattr(cls,'analyze',fake)
    with pytest.raises(ValueError,match='before field/FFT'):doc.analyze(max_evaluations=4)
    with pytest.raises(ValueError,match='before field/FFT'):execute_saved(doc.dumps(),max_evaluations=4)
    assert calls==[]
    result=doc.analyze(max_evaluations=5)
    assert len(calls)==1 and result.extraction.network is net


def test_budget_precedes_boundary_feedback(monkeypatch):
    import sipi.periodic_mixed_circuit as module
    def forbidden(*args,**kwargs):pytest.fail('budget failure called boundary solver')
    monkeypatch.setattr(module,'periodic_mixed_response',forbidden)
    with pytest.raises(ValueError,match='before field/FFT'):document().analyze(max_evaluations=4)


@pytest.mark.parametrize('drift',['frequency','ports','refs','basis','dc'])
def test_source_identity_drift_is_rejected(drift,monkeypatch):
    doc=document('transmission-line');_,_,f,names=_network_input(doc.to_dict()['network'])
    refs=np.full(len(names),50.);basis='single-ended'
    if drift=='frequency':f=f*2
    elif drift=='ports':names=tuple(reversed(names))
    elif drift=='refs':refs[0]=75.
    elif drift=='basis':basis='mixed-mode'
    s=np.zeros((3,len(names),len(names)),complex)
    if drift=='dc':s[0,0,0]=1e-20j
    net=LineNetwork(f,s,refs,names,basis)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:SimpleNamespace(network=net))
    with pytest.raises(ValueError,match='exactly real' if drift=='dc' else 'changed the saved'):doc.analyze()


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.periodic-mixed-circuit/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('basis'),lambda d:d.update(basis='wrong'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d.pop('boundaries'),lambda d:d.update(boundaries=[]),
    lambda d:d['boundaries'].pop('near:s'),lambda d:d['boundaries'].update(other={}),
    lambda d:d['boundaries'].update({'near:s':'short'}),
    lambda d:d['boundaries']['near:s'].update(kind='wrong'),
    lambda d:d['boundaries']['near:s'].update(extra=0),
    lambda d:d['boundaries']['near:s'].pop('source_voltage'),
    lambda d:d['boundaries']['far:s'].pop('admittance'),
    lambda d:d['boundaries']['near:s'].update(source_voltage=True),
    lambda d:d['boundaries']['far:s'].update(source_current=dict(real=0,imag=0)),
    lambda d:d['boundaries']['near:s'].update(source_voltage=[0]*4),
    lambda d:d['boundaries']['far:s'].update(source_current=float('inf')),
    lambda d:d['boundaries']['near:s'].update(impedance=True),
    lambda d:d['boundaries']['far:s'].update(admittance=-1),
    lambda d:d['boundaries']['near:s'].update(impedance=dict(real=1,imag=1e-20)),
    lambda d:d['boundaries']['far:s'].update(admittance=dict(real=.02,imag=1e-20)),
    lambda d:d['boundaries']['near:s'].update(impedance=dict(real=[1,2],imag=[0,0])),
    lambda d:d['boundaries']['far:s'].update(admittance=dict(real=[.02]*3,imag=0)),
    lambda d:d['network'].update(frequency_hz=[0,1,3]),
    lambda d:d['network'].update(kind='periodic-mixed-circuit')])
def test_strict_tables_and_grid_before_fields(mutate,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('invalid input solved a field')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    data=document().to_dict();mutate(data)
    with pytest.raises(ValueError):PeriodicMixedCircuitDocument.from_dict(data)


def test_saved_ideal_voltage_open_line_against_analytic_periodic_synthesis():
    from test_periodic_termination import phasors,samples
    f=np.arange(5)*1e8;t=np.arange(9)/9
    drive=.3+.2*np.cos(2*np.pi*t)+.1*np.sin(4*np.pi*t)
    source_peak=phasors(drive[:,None])[:,0];theta=2*np.pi*f*.1*5e-9
    raw=dict(kind='rlgc',frequency_hz=f.tolist(),R=[[0]],G=[[0]],L=[[250e-9]],
        C=[[100e-12]],length_m=.1,reference_ohms=50,names=['s'])
    doc=PeriodicMixedCircuitDocument(raw,boundaries={
        'near:s':dict(kind='thevenin',source_voltage=drive.tolist(),impedance=0),
        'far:s':dict(kind='norton',source_current=0,admittance=0)})
    result=execute_saved(doc.dumps(),max_evaluations=9)['result']
    v=samples(np.column_stack((source_peak,source_peak/np.cos(theta))),9)
    i=samples(np.column_stack((1j*np.tan(theta)*source_peak/50,np.zeros(5))),9)
    np.testing.assert_allclose(result['response']['voltage_v'],v,atol=1e-12,rtol=0)
    np.testing.assert_allclose(result['response']['current_a'],i,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(result['termination_voltage_v'],0.)
    np.testing.assert_array_equal(result['termination_current_a'],0.)


def test_constant_sources_and_zero_drive_preserve_kinds_and_columns():
    data=document().to_dict()
    for item in data['boundaries'].values():
        item['source_voltage' if item['kind']=='thevenin' else 'source_current']=0.
    doc=PeriodicMixedCircuitDocument.from_dict(data);result=execute_saved(doc.dumps())['result']
    for key in ('source_voltage_v','source_current_a','termination_voltage_v','termination_current_a'):
        np.testing.assert_array_equal(result[key],0.)
    np.testing.assert_array_equal(result['response']['voltage_v'],0.)
    assert result['mean_power_w']==dict(network=0.,terminations=0.,sources=0.)


def test_duplicate_nonfinite_and_power_sum_rejection(monkeypatch):
    doc=document();text=doc.dumps()
    with pytest.raises(ValueError):PeriodicMixedCircuitDocument.loads(text.replace('"kind":','"kind":"norton","kind":',1))
    for value in ('NaN','Infinity','1e999'):
        with pytest.raises(ValueError):PeriodicMixedCircuitDocument.loads(text.replace('0.0',value,1))
    huge=np.full(3,1e308)
    fake=SimpleNamespace(solution=SimpleNamespace(frequency_solution=SimpleNamespace(
        network_power=huge,termination_power=huge,source_power=huge)))
    monkeypatch.setattr(PeriodicMixedCircuitDocument,'analyze',lambda *args,**kwargs:fake)
    with pytest.raises(ValueError,match='nonfinite'):execute_saved(text)


def test_floating_open_and_nonreal_dc_network_rejected():
    for value in [1.,1e-20j]:
        net=LineNetwork([0,1],np.full((2,1,1),value),50.,('p',))
        raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
        if value==1:
            doc=PeriodicMixedCircuitDocument(raw,boundaries={'p':dict(kind='norton',source_current=0,admittance=0)})
            with pytest.raises(ValueError,match='condition|singular'):execute_saved(doc.dumps())
        else:
            with pytest.raises(ValueError,match='DC S'):
                PeriodicMixedCircuitDocument(raw,boundaries={'p':dict(kind='thevenin',source_voltage=0,impedance=50)})


@pytest.mark.parametrize('bad',[True,1,10001,3.5])
def test_invalid_budget_and_diagnostics(bad):
    doc=document()
    with pytest.raises(ValueError):doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=bad)
    with pytest.raises(ValueError,match='top-level'):execute_saved(doc.dumps(),diagnostics=['characteristic'])
