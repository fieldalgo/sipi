# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved source/load waveforms, original diagnostics and explicit power units."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from sipi import LineNetwork, periodic_norton_response
from sipi.circuit_document import _network_input, _complex_value
from sipi.execution import execute_saved, normalize_saved
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument
from sipi.periodic_norton_circuit import PeriodicNortonCircuitDocument
from test_periodic_document import KINDS, FREQUENCY, source, field, decoded


def document(kind='rlgc', *, pair=False, basis='single-ended'):
    raw = field(pair=True) if pair else source(kind)
    _, _, frequency, names = _network_input(raw)
    if basis == 'mixed-mode': names = ('d_near', 'd_far', 'c_near', 'c_far')
    t = np.arange(2*len(frequency)-1)/(2*len(frequency)-1)
    voltages = {name:(.0002*i+.001*np.cos(2*np.pi*t+i)).tolist() for i,name in reversed(list(enumerate(names)))}
    loads = {name:dict(real=[.01+i*.01]*len(frequency),
        imag=(np.arange(len(frequency))*.002).tolist()) for i,name in enumerate(names)}
    return PeriodicNortonCircuitDocument(raw, source_currents=voltages, termination_admittances=loads, basis=basis)


@pytest.mark.parametrize('kind', KINDS)
def test_all_sources_normalize_without_fields(kind, monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('normalization solved a field')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    monkeypatch.setattr(VolumeLineDocument,'analyze',forbidden)
    doc = document(kind)
    assert doc.sample_count == 5
    assert normalize_saved(doc.dumps()) == PeriodicNortonCircuitDocument.loads(doc.dumps()).dumps() == doc.dumps()
    copy = doc.to_dict(); copy['termination_admittances'].clear()
    assert doc.to_dict()['termination_admittances']


def direct(doc):
    data = doc.to_dict()
    obj, _, frequency, _ = _network_input(data['network'])
    net = obj if isinstance(obj,LineNetwork) else obj.analyze().network
    if data['basis']=='mixed-mode':net=net.mixed_mode()
    loads = {name:_complex_value(value,len(frequency))[0] for name,value in data['termination_admittances'].items()}
    return net, periodic_norton_response(net,source_currents=data['source_currents'],termination_admittances=loads)


@pytest.mark.parametrize('kind', KINDS[:5])
def test_exact_api_json_diagnostics_and_power_replay(kind):
    doc = document(kind)
    network, expected = direct(doc)
    actual = PeriodicNortonCircuitDocument.loads(doc.dumps()).analyze(max_evaluations=5)
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
    for key,field_name in [('source_current_a','source_currents'),('termination_current_a','termination_currents')]:
        np.testing.assert_array_equal(data[key],getattr(expected,field_name))
    for key,field_name in [('source_current_a','source_currents'),('termination_admittance_s','termination_admittances'),
        ('incident_sqrt_w','a'),('reflected_sqrt_w','b'),('voltage_v','voltage'),('current_a','current')]:
        np.testing.assert_array_equal(decoded(data['harmonics'][key]),getattr(harmonic,field_name))
    for key in ('condition_number','kcl_residual','wave_residual'):
        np.testing.assert_array_equal(data['harmonics'][key],getattr(harmonic,key))
    for label,attribute,current in [('network','network_power',expected.response.current),
        ('terminations','termination_power',expected.termination_currents),
        ('sources','source_power',expected.source_currents)]:
        np.testing.assert_array_equal(data['harmonics']['frequency_power_w'][label],getattr(harmonic,attribute))
        assert data['mean_power_w'][label]==sum(data['harmonics']['frequency_power_w'][label])
        assert abs(data['mean_power_w'][label]-np.mean(np.sum(expected.response.voltage*current,axis=1)))<1e-12
    json.dumps(output,allow_nan=False)


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
    lambda d:d.update(schema='sipi.periodic-norton-circuit/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('basis'),lambda d:d.update(basis='wrong'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d['source_currents'].pop('near:s'),lambda d:d['termination_admittances'].pop('near:s'),
    lambda d:d['source_currents'].update(other=0),lambda d:d['termination_admittances'].update(other=50),
    lambda d:d['source_currents'].update({'near:s':True}),
    lambda d:d['source_currents'].update({'near:s':[0]*4}),
    lambda d:d['source_currents'].update({'near:s':dict(real=0,imag=0)}),
    lambda d:d['source_currents'].update({'near:s':float('inf')}),
    lambda d:d['termination_admittances'].update({'near:s':True}),
    lambda d:d['termination_admittances'].update({'near:s':-1}),
    lambda d:d['termination_admittances'].update({'near:s':float('inf')}),
    lambda d:d['termination_admittances'].update({'near:s':'open'}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=50,imag=.1)}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=[50,50],imag=[0,0])}),
    lambda d:d['termination_admittances'].update({'near:s':dict(real=[50,50,50],imag=0)}),
    lambda d:d['network'].update(frequency_hz=[0,1,3]),
    lambda d:d['network'].update(kind='periodic-circuit')])
def test_strict_tables_and_schema(mutate):
    data=document().to_dict();mutate(data)
    with pytest.raises(ValueError):PeriodicNortonCircuitDocument.from_dict(data)


def test_constant_sources_canonical_loads_and_zero_drive():
    data=document().to_dict()
    data['source_currents']={name:0 for name in data['source_currents']}
    data['termination_admittances']={name:.02 for name in data['termination_admittances']}
    doc=PeriodicNortonCircuitDocument.from_dict(data)
    assert doc.to_dict()['termination_admittances']['near:s']==dict(real=.02,imag=0.)
    result=execute_saved(doc.dumps())['result']
    np.testing.assert_array_equal(result['response']['voltage_v'],0.)
    assert result['mean_power_w']==dict(network=0.,sources=0.,terminations=0.)


def test_duplicate_nonfinite_json_and_power_sum_guard(monkeypatch):
    doc=document();text=doc.dumps()
    with pytest.raises(ValueError):PeriodicNortonCircuitDocument.loads(text.replace('"basis":','"basis":"single-ended","basis":',1))
    for value in ('NaN','Infinity','1e999'):
        with pytest.raises(ValueError):PeriodicNortonCircuitDocument.loads(text.replace('0.0',value,1))
    huge=np.full(3,1e308)
    fake=SimpleNamespace(solution=SimpleNamespace(frequency_solution=SimpleNamespace(
        network_power=huge,termination_power=huge,source_power=huge)))
    monkeypatch.setattr(PeriodicNortonCircuitDocument,'analyze',lambda *args,**kwargs:fake)
    with pytest.raises(ValueError,match='nonfinite'):execute_saved(text)


def test_singular_circuit_is_not_partial_success():
    net=LineNetwork([0,1],np.ones((2,1,1)),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    doc=PeriodicNortonCircuitDocument(raw,source_currents={'p':1},termination_admittances={'p':0})
    with pytest.raises(ValueError,match='condition|singular'):execute_saved(doc.dumps())


@pytest.mark.parametrize('shunt',[0.,.02])
def test_saved_ideal_current_or_open_terminal_analytic_dc_and_ac(shunt):
    f=np.arange(3)*1e8
    # The one-port is a 100 ohm resistor, independent of the saved solver.
    net=LineNetwork(f,np.full((3,1,1),1/3),50.,('p',))
    raw=dict(kind='touchstone',text=net.touchstone(),ports=1,port_names=['p'])
    t=np.arange(5)/5;drive=.001+.002*np.cos(2*np.pi*t)
    doc=PeriodicNortonCircuitDocument(raw,source_currents={'p':drive.tolist()},
        termination_admittances={'p':shunt})
    out=execute_saved(doc.dumps(),max_evaluations=5)['result']
    voltage=np.array(out['response']['voltage_v'])[:,0]
    current=np.array(out['response']['current_a'])[:,0]
    np.testing.assert_allclose(voltage,drive/(.01+shunt),atol=1e-12,rtol=0)
    np.testing.assert_allclose(current,.01*voltage,atol=1e-12,rtol=0)
    np.testing.assert_allclose(out['termination_current_a'],(shunt*voltage)[:,None],atol=1e-12,rtol=0)


def test_saved_open_far_lossless_line_and_pre_fft_budget(monkeypatch):
    raw=dict(kind='rlgc',frequency_hz=[0,1e8,2e8],R=[[0]],G=[[0]],
        L=[[250e-9]],C=[[100e-12]],length_m=.1,reference_ohms=50,names=['s'])
    doc=PeriodicNortonCircuitDocument(raw,source_currents={'near:s':[.001,0,-.001,0,.001],'far:s':0},
        termination_admittances={'near:s':.02,'far:s':0})
    out=execute_saved(doc.dumps(),max_evaluations=5)['result']
    np.testing.assert_allclose(np.array(out['response']['current_a'])[:,1],0,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(np.array(out['termination_current_a'])[:,1],0)
    np.testing.assert_allclose(np.array(out['source_current_a']),
        np.array(out['response']['current_a'])+np.array(out['termination_current_a']),atol=1e-12,rtol=0)
    def forbidden(*args,**kwargs):pytest.fail('budget rejection reached FFT')
    monkeypatch.setattr(np.fft,'rfft',forbidden)
    with pytest.raises(ValueError,match='before field/FFT'):execute_saved(doc.dumps(),max_evaluations=4)


@pytest.mark.parametrize('bad',[True,1,10001,3.5])
def test_invalid_budget_and_diagnostics(bad):
    doc=document()
    with pytest.raises(ValueError):doc.analyze(max_evaluations=bad)
    with pytest.raises(ValueError):execute_saved(doc.dumps(),max_evaluations=bad)
    with pytest.raises(ValueError,match='top-level'):execute_saved(doc.dumps(),diagnostics=['characteristic'])
