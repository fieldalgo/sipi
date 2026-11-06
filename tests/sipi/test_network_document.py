# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved network operations: analytic phases, independent composition and parsing."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (CrossSection, CrossSectionDocument, LineNetwork,
                  NetworkTransformDocument, microstrip, terminate_ports)
from sipi.circuit_document import CircuitDocument
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument


def source():
    return dict(kind='rlgc',frequency_hz=[0,1e9,5e9,10e9],R=[[0]],L=[[250e-9]],
                G=[[0]],C=[[100e-12]],length_m=.01,reference_ohms=50,names=['trace'])


def steps(first=True):
    load=dict(kind='terminate-ports',loads={'far:trace':'open'})
    return [dict(kind='renormalize',reference_ohms=[75,120]),load] if first else [
        load,dict(kind='renormalize',reference_ohms=75)]


@pytest.mark.parametrize('first',[True,False])
@pytest.mark.parametrize('ending',['open','short'])
def test_saved_analytic_line_reflection_and_following_driven_circuit(first,ending):
    operations=steps(first)
    operations[1 if first else 0]['loads']['far:trace']=ending
    doc=NetworkTransformDocument(source(),operations=operations)
    restored=NetworkTransformDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()
    result=restored.analyze()
    original=(1 if ending=='open' else -1)*np.exp(-2j*2*np.pi*np.array(source()['frequency_hz'])/2e8*.01)
    expected=((-25)+125*original)/(125-25*original)
    np.testing.assert_allclose(result.network.s[:,0,0],expected,rtol=0,atol=1e-12)
    assert result.network.port_names==doc.port_names==('near:trace',)
    assert result.input_json==doc.dumps() and result.extraction is None
    np.testing.assert_array_equal(result.network.z_ref,[75])
    circuit=CircuitDocument(dict(kind='network-transform',document=doc.to_dict()),
        excitation=dict(kind='sources',voltages={'near:trace':1}),terminations={'near:trace':50})
    solved=CircuitDocument.loads(circuit.dumps()).analyze()
    np.testing.assert_allclose(solved.response.voltage[:,0],.5*(1+original),rtol=0,atol=1e-12)
    np.testing.assert_allclose(solved.response.current[:,0],(1-original)/100,rtol=0,atol=1e-12)
    assert solved.extraction.input_json==doc.dumps()


def test_touchstone_operations_against_independent_skrf():
    skrf=require_tool('scikit-rf')
    rng=np.random.default_rng(104)
    s=.12*(rng.normal(size=(2,3,3))+1j*rng.normal(size=(2,3,3)))
    net=LineNetwork([1e6,1e9],s,[25,50,75],('a','b','c'))
    ops=[dict(kind='renormalize',reference_ohms=[35,55,80]),
         dict(kind='terminate-ports',loads={'b':dict(real=[25,100],imag=[10,-20])}),
         dict(kind='renormalize',reference_ohms=[60,90])]
    doc=NetworkTransformDocument(dict(kind='touchstone',text=net.touchstone(),ports=3,
                                     port_names=list(net.port_names)),operations=ops)
    clock=Stopwatch()
    with clock('openphysics'):actual=NetworkTransformDocument.loads(doc.dumps()).analyze()
    with clock('reference'):
        ref=skrf.Network(frequency=skrf.Frequency.from_f(net.frequency,unit='Hz'),s=s,z0=net.z_ref)
        ref.renormalize([35,55,80])
        z=np.array([25+10j,100-20j]);gamma=(z-55)/(z+55)
        load=skrf.Network(frequency=ref.frequency,s=gamma[:,None,None],z0=55)
        ref=skrf.network.connect(ref,1,load,0)
        ref.renormalize([60,90])
    error=float(np.max(abs(actual.network.s-ref.s)))
    record=make_record(case='saved-network-transforms',physics='loaded multiport network',
        api='sipi.NetworkTransformDocument',discretization='strict saved steps through existing network APIs',
        tool='scikit-rf',tool_discretization='independent renormalize and connect',
        matched=['same nonreciprocal input S, references, complex passive load and operation order'],
        not_matched=['no geometry, electromagnetic accuracy or time-domain comparison'],
        observables=[observable('transformed S','1','max absolute difference',error,1e-10)],
        analytical_acceptance='lossless open-end input reflection and independent driven-terminal voltages',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10
    np.testing.assert_allclose(actual.source_network.s,net.s,rtol=0,atol=1e-12)
    assert actual.network.port_names==('a','c')


@pytest.mark.parametrize('kind',['transmission-line','volume-line'])
def test_geometry_source_extracts_and_meshes_once(kind,monkeypatch):
    section=microstrip(width=.4e-3,substrate_height=.5e-3,thickness=.1e-3,
        eps_r=4,tan_delta=.02,air_height=.5e-3,box_width=2e-3)
    cross=CrossSectionDocument(section)
    if kind=='transmission-line':
        inner=TransmissionLineDocument(cross,[0,1e3],materials={},conductor={'kind':'perfect'},length=.1)
        owner,method=CrossSection,'mesh'
    else:
        inner=VolumeLineDocument(cross,[0,1e3],materials={},conductivity=58e6,length=.1,
            mesh=dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,
                      far_size=.5e-3,grade=.2,min_angle=28))
        import sipi.volume_line as owner
        method='mesh_conductor_section'
    calls=[];original=getattr(owner,method)
    def counted(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(owner,method,counted)
    operations=[dict(kind='renormalize',reference_ohms=[30,70]),
                dict(kind='terminate-ports',loads={'far:signal':100})]
    doc=NetworkTransformDocument(dict(kind=kind,document=inner.to_dict()),operations=operations)
    restored=NetworkTransformDocument.loads(doc.dumps())
    assert not calls
    circuit=CircuitDocument(dict(kind='network-transform',document=restored.to_dict()),
        excitation=dict(kind='sources',voltages={'near:signal':1}),terminations={})
    out=circuit.analyze()
    assert len(calls)==1
    transform=out.extraction
    assert transform.extraction.input_json==inner.dumps()
    direct=terminate_ports(transform.source_network.renormalized([30,70]),{'far:signal':100})
    np.testing.assert_allclose(out.network.s,direct.s,rtol=0,atol=1e-12)


def test_snapshots_and_operation_order_are_preserved():
    raw=source();ops=steps()
    doc=NetworkTransformDocument(raw,operations=ops);before=doc.dumps()
    raw['C'][0][0]=1;ops[0]['reference_ohms'][0]=999
    doc.to_dict()['operations'].clear()
    assert doc.dumps()==before
    assert not doc.frequency.flags.writeable
    # Renormalization alone is not a load; changing its order keeps all steps.
    assert [x['kind'] for x in doc.to_dict()['operations']]==['renormalize','terminate-ports']


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.network-transforms/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('network'),lambda d:d.pop('operations'),
    lambda d:d.update(operations=[]),lambda d:d.update(operations=None),
    lambda d:d.update(operations=[dict(kind='renormalize',reference_ohms=50)]*33),
    lambda d:d.update(operations=[None]),lambda d:d['operations'][0].update(kind='eval'),
    lambda d:d['operations'][0].update(extra=1),
    lambda d:d['operations'][0].update(reference_ohms=True),
    lambda d:d['operations'][0].update(reference_ohms=[50]),
    lambda d:d['operations'][0].update(reference_ohms=-1),
    lambda d:d['operations'][1].update(loads={}),
    lambda d:d['operations'][1].update(loads={'missing':'open'}),
    lambda d:d['operations'][1].update(loads={'far:trace':'unknown'}),
    lambda d:d['operations'][1].update(loads={'far:trace':True}),
    lambda d:d['operations'][1].update(loads={'far:trace':-1}),
    lambda d:d['operations'][1].update(loads={'far:trace':dict(real=[1],imag=[0])}),
    lambda d:d['operations'][1].update(loads={'far:trace':dict(real=1,imag=0,extra=1)}),
    lambda d:d['operations'][1].update(loads={'far:trace':'open','near:trace':'short'}),
    lambda d:d['operations'].append(dict(kind='terminate-ports',loads={'far:trace':50})),
    lambda d:d['operations'].append(dict(kind='renormalize',reference_ohms=[50,50])),
    lambda d:d.update(network=dict(kind='network-transform',document={})),
])
def test_invalid_document_rejected(mutate):
    data=NetworkTransformDocument(source(),operations=steps()).to_dict();mutate(data)
    with pytest.raises(ValueError):NetworkTransformDocument.from_dict(data)


@pytest.mark.parametrize('text',['{"schema":1,"schema":2}','{"x":NaN}',
                                  '{"x":Infinity}','{"x":{"a":1,"a":2}}'])
def test_nonfinite_and_duplicate_json_rejected(text):
    with pytest.raises(ValueError):NetworkTransformDocument.loads(text)


def test_analysis_failure_is_not_converted_to_a_partial_result():
    net=LineNetwork([0],[np.eye(2)],50,('keep','isolated'))
    doc=NetworkTransformDocument(dict(kind='touchstone',text=net.touchstone(),ports=2,
        port_names=list(net.port_names)),operations=[
            dict(kind='terminate-ports',loads={'isolated':'open'})])
    before=doc.dumps()
    with pytest.raises(ValueError,match='singular'):
        doc.analyze()
    assert doc.dumps()==before


def test_bad_transformed_circuit_ports_rejected_before_geometry(monkeypatch):
    inner=TransmissionLineDocument(CrossSectionDocument(microstrip(
        width=.4e-3,substrate_height=.5e-3,eps_r=4)),[1e3],
        materials={},conductor={'kind':'perfect'},length=.1)
    def forbidden(*args,**kwargs):pytest.fail('parsing reached extraction')
    monkeypatch.setattr(TransmissionLineDocument,'analyze',forbidden)
    doc=NetworkTransformDocument(dict(kind='transmission-line',document=inner.to_dict()),
        operations=[dict(kind='terminate-ports',loads={'far:signal':'open'})])
    with pytest.raises(ValueError,match='unknown network port'):
        CircuitDocument(dict(kind='network-transform',document=doc.to_dict()),
            excitation=dict(kind='sources',voltages={'far:signal':1}),terminations={})
