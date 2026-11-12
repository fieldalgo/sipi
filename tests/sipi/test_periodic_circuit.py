# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved source/load waveforms, original diagnostics and explicit power units."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import LineNetwork, periodic_terminated_response
from sipi.circuit_document import _network_input, _complex_value
from sipi.execution import execute_saved, normalize_saved
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.periodic_circuit import PeriodicCircuitDocument
from test_periodic_document import KINDS, FREQUENCY, source, field, decoded


def document(kind='rlgc', *, pair=False, basis='single-ended'):
    raw = field(pair=True) if pair else source(kind)
    _, _, frequency, names = _network_input(raw)
    if basis == 'mixed-mode': names = ('d_near', 'd_far', 'c_near', 'c_far')
    t = np.arange(2*len(frequency)-1)/(2*len(frequency)-1)
    voltages = {name:(.2*i+np.cos(2*np.pi*t+i)).tolist() for i,name in reversed(list(enumerate(names)))}
    loads = {name:dict(real=[30.+i*10]*len(frequency),
        imag=(np.arange(len(frequency))*3.).tolist()) for i,name in enumerate(names)}
    return PeriodicCircuitDocument(raw, source_voltages=voltages, terminations=loads, basis=basis)


@pytest.mark.parametrize('kind', KINDS)
def test_all_sources_normalize_without_fields(kind, monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization solved a field')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(VolumeLineDocument,'analyze',forbidden)
    doc = document(kind)
    assert doc.sample_count == 5
    assert normalize_saved(doc.dumps()) == PeriodicCircuitDocument.loads(doc.dumps()).dumps() == doc.dumps()
    copy = doc.to_dict(); copy['terminations'].clear()
    assert doc.to_dict()['terminations']


def direct(doc):
    data = doc.to_dict()
    obj, _, frequency, _ = _network_input(data['network'])
    net = obj if isinstance(obj,LineNetwork) else obj.analyze().network
    if data['basis']=='mixed-mode':net=net.mixed_mode()
    loads = {name:_complex_value(value,len(frequency))[0] for name,value in data['terminations'].items()}
    return net, periodic_terminated_response(net,source_voltages=data['source_voltages'],terminations=loads)


@pytest.mark.parametrize('kind', KINDS[:5])
def test_exact_api_json_diagnostics_and_power_replay(kind):
    doc = document(kind)
    network, expected = direct(doc)
    actual = PeriodicCircuitDocument.loads(doc.dumps()).analyze(max_evaluations=5)
    assert actual.input_json == doc.dumps()
    np.testing.assert_array_equal(actual.network.s, network.s)
    output = execute_saved(doc.dumps(), max_evaluations=5)
    assert output['input']==doc.to_dict() and output['status']=='complete' and output['error'] is None
    data = output['result']; harmonic=expected.frequency_solution
    assert data['coverage']=='sampled-periodic-steady-state'
    assert data['harmonics']['convention']=='dc-mean-positive-peak'
    np.testing.assert_array_equal(decoded(data['network']['s']),network.s)
    np.testing.assert_array_equal(decoded(data['source_network']['s']),actual.source_network.s)
    for key, field_name in [('incident_sqrt_w','incident'),('reflected_sqrt_w','reflected'),
        ('voltage_v','voltage'),('current_a','current'),('time_s','time')]:
        np.testing.assert_array_equal(data['response'][key],getattr(expected.response,field_name))
        np.testing.assert_array_equal(getattr(actual.solution.response,field_name),getattr(expected.response,field_name))
    for key,field_name in [('source_voltage_v','source_voltages'),('termination_voltage_v','termination_voltages')]:
        np.testing.assert_array_equal(data[key],getattr(expected,field_name))
    for key,field_name in [('source_voltage_v','source_voltages'),('termination_ohms','terminations'),
        ('incident_sqrt_w','a'),('reflected_sqrt_w','b'),('voltage_v','voltage'),('current_a','current')]:
        np.testing.assert_array_equal(decoded(data['harmonics'][key]),getattr(harmonic,field_name))
    for key in ('condition_number','kvl_residual','wave_residual'):
        np.testing.assert_array_equal(data['harmonics'][key],getattr(harmonic,key))
    for label,attribute,voltage in [('network','network_power',expected.response.voltage),
        ('terminations','termination_power',expected.termination_voltages),
        ('sources','source_power',expected.source_voltages)]:
        np.testing.assert_array_equal(data['harmonics']['frequency_power_w'][label],getattr(harmonic,attribute))
        assert data['mean_power_w'][label]==sum(data['harmonics']['frequency_power_w'][label])
        assert abs(data['mean_power_w'][label]-np.mean(np.sum(voltage*expected.response.current,axis=1)))<1e-12
    json.dumps(output,allow_nan=False)


def test_dc_and_two_harmonic_power_totals_replay_from_saved_components():
    data = document('lumped-network').to_dict()
    phase = 2*np.pi*np.arange(5)/5
    for i, name in enumerate(data['source_voltages']):
        data['source_voltages'][name] = (100*(i+1) + np.cos(phase+i) + np.cos(2*phase-i)).tolist()
    doc = PeriodicCircuitDocument.from_dict(data)
    result = execute_saved(doc.dumps())['result']
    restored = json.loads(json.dumps(result, allow_nan=False))
    for name, values in restored['harmonics']['frequency_power_w'].items():
        assert restored['mean_power_w'][name] == sum(values)
    response = restored['response']
    time_mean = np.mean(np.sum(np.array(response['voltage_v'])*response['current_a'], axis=1))
    np.testing.assert_allclose(restored['mean_power_w']['network'], time_mean, rtol=1e-14, atol=0)


@pytest.mark.parametrize('pair',[False,True])
def test_actual_pec_field_and_mixed_mode_once(pair,monkeypatch):
    doc=document('transmission-line',pair=pair,basis='mixed-mode' if pair else 'single-ended')
    net,expected=direct(doc)
    calls=[]; original=TransmissionLineDocument.analyze
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
    doc=document(kind); cls=TransmissionLineDocument if kind=='transmission-line' else VolumeLineDocument
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


@pytest.mark.parametrize('drift',['frequency','ports','refs','basis','dc'])
def test_source_identity_and_dc_rejection(drift,monkeypatch):
    doc=document('transmission-line'); _,_,f,names=_network_input(doc.to_dict()['network'])
    refs=np.full(len(names),50.);s=np.zeros((3,len(names),len(names)),complex);basis='single-ended'
    if drift=='frequency':f=f*2
    elif drift=='ports':names=tuple(reversed(names))
    elif drift=='refs':refs[0]=75.
    elif drift=='basis':basis='mixed-mode'
    else:s[0,0,0]=1e-20j
    net=LineNetwork(f,s,refs,names,basis)
    monkeypatch.setattr(TransmissionLineDocument,'analyze',lambda self:SimpleNamespace(network=net))
    with pytest.raises(ValueError,match='exactly real' if drift=='dc' else 'changed the saved'):
        doc.analyze()


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.periodic-circuit/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('basis'),lambda d:d.update(basis='wrong'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d['source_voltages'].pop('near:s'),lambda d:d['terminations'].pop('near:s'),
    lambda d:d['source_voltages'].update(other=0),lambda d:d['terminations'].update(other=50),
    lambda d:d['source_voltages'].update({'near:s':True}),
    lambda d:d['source_voltages'].update({'near:s':[0]*4}),
    lambda d:d['source_voltages'].update({'near:s':dict(real=0,imag=0)}),
    lambda d:d['source_voltages'].update({'near:s':float('inf')}),
    lambda d:d['terminations'].update({'near:s':True}),
    lambda d:d['terminations'].update({'near:s':-1}),
    lambda d:d['terminations'].update({'near:s':float('inf')}),
    lambda d:d['terminations'].update({'near:s':'open'}),
    lambda d:d['terminations'].update({'near:s':dict(real=50,imag=.1)}),
    lambda d:d['terminations'].update({'near:s':dict(real=[50,50],imag=[0,0])}),
    lambda d:d['terminations'].update({'near:s':dict(real=[50,50,50],imag=0)}),
    lambda d:d['network'].update(frequency_hz=[0,1,3]),
    lambda d:d['network'].update(kind='periodic-circuit')])
def test_strict_tables_and_schema(mutate):
    data=document().to_dict();mutate(data)
    with pytest.raises(ValueError):PeriodicCircuitDocument.from_dict(data)


def test_constant_sources_canonical_loads_and_zero_drive():
    data=document().to_dict()
    data['source_voltages']={name:0 for name in data['source_voltages']}
    data['terminations']={name:50 for name in data['terminations']}
    doc=PeriodicCircuitDocument.from_dict(data)
    assert doc.to_dict()['terminations']['near:s']==dict(real=50.,imag=0.)
    result=execute_saved(doc.dumps())['result']
    np.testing.assert_array_equal(result['response']['voltage_v'],0.)
    assert result['mean_power_w']==dict(network=0.,sources=0.,terminations=0.)


def test_duplicate_nonfinite_json_and_power_sum_guard(monkeypatch):
    doc=document();text=doc.dumps()
    with pytest.raises(ValueError):PeriodicCircuitDocument.loads(text.replace('"basis":','"basis":"single-ended","basis":',1))
    for value in ('NaN','Infinity','1e999'):
        with pytest.raises(ValueError):PeriodicCircuitDocument.loads(text.replace('0.0',value,1))
    huge=np.full(3,1e308)
    fake=SimpleNamespace(solution=SimpleNamespace(frequency_solution=SimpleNamespace(
        network_power=huge,termination_power=huge,source_power=huge)))
    monkeypatch.setattr(PeriodicCircuitDocument,'analyze',lambda *args,**kwargs:fake)
    with pytest.raises(ValueError,match='nonfinite'):execute_saved(text)


def test_singular_circuit_is_not_partial_success():
    net=LineNetwork([0,1],-np.ones((2,1,1)),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    doc=PeriodicCircuitDocument(raw,source_voltages={'p':1},terminations={'p':0})
    with pytest.raises(ValueError,match='condition|singular'):execute_saved(doc.dumps())


@pytest.mark.parametrize('bad',[True,1,10001,3.5])
def test_invalid_budget_and_diagnostics(bad):
    doc=document()
    with pytest.raises(ValueError):doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=bad)
    with pytest.raises(ValueError,match='top-level'):execute_saved(doc.dumps(),diagnostics=['characteristic'])
