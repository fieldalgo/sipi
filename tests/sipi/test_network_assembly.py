# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved circuit assembly: independent references, exact replay and early checks."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import (NetworkAssemblyDocument, NetworkTransformDocument, LineNetwork,
                  CrossSection, CrossSectionDocument, microstrip, connect_networks)
from sipi.circuit_document import CircuitDocument
from sipi.line_model import TransmissionLineDocument
from sipi.volume_line import VolumeLineDocument

F = [0,1e9,5e9,10e9]


def node(names=('input','output','branch')):
    return dict(kind='ideal-junction',frequency_hz=F,port_names=list(names),reference_ohms=50)


def line(name='stub',length=.01):
    return dict(kind='rlgc',frequency_hz=F,R=[[0]],L=[[250e-9]],G=[[0]],C=[[100e-12]],
                length_m=length,reference_ohms=50,names=[name])


def assembly():
    return NetworkAssemblyDocument(node(),connections=[
        dict(network=line(),ports=[['branch','near:stub']])])


@pytest.mark.parametrize('ending',['open','short'])
def test_saved_shunt_stub_transforms_and_driven_circuit_against_closed_form(ending):
    original = assembly(); doc = NetworkAssemblyDocument.loads(original.dumps())
    assert doc.dumps()==original.dumps()
    assert doc.port_names==('input','output','far:stub')
    assert doc.to_dict()['connections'][0]['port_names']==list(doc.port_names)
    transformed = NetworkTransformDocument(dict(kind='network-assembly',document=doc.to_dict()),
        operations=[dict(kind='terminate-ports',loads={'far:stub':ending}),
                    dict(kind='renormalize',reference_ohms=[75,100])])
    circuit = CircuitDocument(dict(kind='network-transform',document=transformed.to_dict()),
        excitation=dict(kind='sources',voltages={'input':1}),terminations={'input':50,'output':50})
    solved = CircuitDocument.loads(circuit.dumps()).analyze()
    angle = 2*np.pi*np.array(F)*.01/2e8
    if ending=='open':
        transmission = 2*np.cos(angle)/(2*np.cos(angle)+1j*np.sin(angle))
    else:
        transmission = 2j*np.sin(angle)/(2j*np.sin(angle)+np.cos(angle))
    np.testing.assert_allclose(solved.response.voltage[:,1],.5*transmission,rtol=0,atol=1e-12)
    np.testing.assert_allclose(solved.response.current[:,1],-.5*transmission/50,rtol=0,atol=1e-12)
    joined = solved.extraction.extraction
    assert joined.input_json==doc.dumps() and len(joined.source_networks)==2
    assert joined.extractions==(None,None)
    assert joined.network.port_names==doc.port_names
    assert solved.extraction.input_json==transformed.dumps()


def test_multiple_saved_components_and_port_order_against_independent_skrf():
    tool=require_tool('scikit-rf');clock=Stopwatch()
    # Two unequal-length stubs meet the same four-terminal ideal node.
    doc=NetworkAssemblyDocument(node(('input','output','first','second')),connections=[
        dict(network=line('one',.007),ports=[['first','near:one']]),
        dict(network=line('two',.013),ports=[['second','near:two']])])
    transform=NetworkTransformDocument(dict(kind='network-assembly',document=doc.to_dict()),
        operations=[dict(kind='terminate-ports',loads={'far:one':75,'far:two':dict(real=100,imag=20)})])
    with clock('openphysics'):actual=NetworkTransformDocument.loads(transform.dumps()).analyze()
    with clock('reference'):
        frequency=tool.Frequency.from_f(F,unit='Hz')
        medium=tool.media.DefinedGammaZ0(frequency=frequency,gamma=2j*np.pi*np.array(F)/2e8,z0=50)
        junction=medium.splitter(4)
        first=tool.network.connect(junction,2,medium.line(.007,unit='m'),0)
        second=tool.network.connect(first,3,medium.line(.013,unit='m'),0)
        def load(value):return tool.Network(frequency=frequency,
            s=np.full((len(F),1,1),(value-50)/(value+50)),z0=50)
        expected=tool.network.connect(tool.network.connect(second,3,load(100+20j),0),2,load(75),0)
    error=float(abs(actual.network.s-expected.s).max())
    record=make_record(case='saved-two-stub-assembly',physics='saved line circuit assembly',
        api='sipi.NetworkAssemblyDocument',discretization='ordered explicit connections then passive reduction',
        tool='scikit-rf',tool_discretization='independent ideal media, splitter and port connections',
        matched=['same line lengths, wave speed, real references, explicit topology and finite loads'],
        not_matched=['no physical junction or three-dimensional via/stub model'],
        observables=[observable('assembled S','1','max absolute difference',error,1e-10)],
        analytical_acceptance='single shunt stub and driven terminal voltage at DC/quarter/half wavelength',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10
    assert doc.port_names==('input','output','far:one','far:two')
    assert len(actual.extraction.source_networks)==3


def test_touchstone_crossed_wiring_and_explicit_names_round_trip():
    rng=np.random.default_rng(204)
    a=LineNetwork(F,.05*(rng.normal(size=(4,4,4))+1j*rng.normal(size=(4,4,4))),
                   [25,55,90,70],('a0','a1','a2','a3'))
    b=LineNetwork(F,.05*(rng.normal(size=(4,4,4))+1j*rng.normal(size=(4,4,4))),
                   [70,40,55,110],('b0','b1','b2','b3'))
    def source(net):return dict(kind='touchstone',text=net.touchstone(),ports=4,port_names=list(net.port_names))
    pairs=[['a1','b2'],['a3','b0']];names=['x','y','z','w']
    doc=NetworkAssemblyDocument(source(a),connections=[dict(network=source(b),ports=pairs,port_names=names)])
    actual=NetworkAssemblyDocument.loads(doc.dumps()).analyze()
    expected=connect_networks(a,b,pairs,port_names=names)
    np.testing.assert_allclose(actual.network.s,expected.s,rtol=0,atol=1e-12)
    np.testing.assert_array_equal(actual.network.z_ref,[25,90,40,110])
    assert doc.port_names==tuple(names)


@pytest.mark.parametrize('kind',['transmission-line','volume-line'])
def test_each_geometry_component_is_extracted_once_and_parsing_never_meshes(kind,monkeypatch):
    section=microstrip(width=.4e-3,substrate_height=.5e-3,thickness=.1e-3,
        eps_r=4,tan_delta=.02,air_height=.5e-3,box_width=2e-3)
    cross=CrossSectionDocument(section)
    if kind=='transmission-line':
        inner=TransmissionLineDocument(cross,[0,1e3],materials={},conductor={'kind':'perfect'},length=.01)
        owner,method=CrossSection,'mesh'
    else:
        inner=VolumeLineDocument(cross,[0,1e3],materials={},conductivity=58e6,length=.01,
            mesh=dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,
                      far_size=.5e-3,grade=.2,min_angle=28))
        import sipi.volume_line as owner
        method='mesh_conductor_section'
    calls=[];original=getattr(owner,method)
    def counted(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(owner,method,counted)
    start=node();start['frequency_hz']=[0,1e3]
    source=dict(kind=kind,document=inner.to_dict())
    doc=NetworkAssemblyDocument(start,connections=[
        dict(network=source,ports=[['branch','near:signal']],port_names=['input','output','first_end']),
        dict(network=source,ports=[['output','near:signal']])])
    saved=NetworkAssemblyDocument.loads(doc.dumps())
    assert not calls
    # Even invalid final circuit ports must fail before any extraction.
    with pytest.raises(ValueError,match='unknown network port'):
        CircuitDocument(dict(kind='network-assembly',document=saved.to_dict()),
            excitation=dict(kind='sources',voltages={'output':1}),terminations={})
    assert not calls
    circuit=CircuitDocument(dict(kind='network-assembly',document=saved.to_dict()),
        excitation=dict(kind='sources',voltages={'input':1}),
        terminations={'input':50,'first_end':50,'far:signal':50})
    solved=CircuitDocument.loads(circuit.dumps()).analyze()
    assert len(calls)==2
    result=solved.extraction
    assert len(result.source_networks)==len(result.extractions)==3 and result.extractions[0] is None
    assert all(x.input_json==inner.dumps() for x in result.extractions[1:])
    np.testing.assert_allclose(result.source_networks[1].s,result.source_networks[2].s,rtol=0,atol=1e-12)
    assert result.input_json==doc.dumps()


def test_input_and_metadata_snapshots():
    start=node();steps=[dict(network=line(),ports=[['branch','near:stub']])]
    doc=NetworkAssemblyDocument(start,connections=steps);saved=doc.dumps()
    start['port_names'][0]='changed';steps[0]['ports'].clear();doc.to_dict()['connections'].clear()
    assert doc.dumps()==saved
    for array in (doc.frequency,doc.z_ref):
        assert not array.flags.writeable
        array.setflags(write=True);array[:]=999
    np.testing.assert_array_equal(doc.frequency,F)
    np.testing.assert_array_equal(doc.z_ref,[50,50,50])


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.network-assembly/2'),lambda d:d.update(extra=1),
    lambda d:d.pop('network'),lambda d:d.pop('connections'),
    lambda d:d.update(connections=[]),lambda d:d.update(connections=None),
    lambda d:d.update(connections=[None]),lambda d:d['connections'][0].update(extra=1),
    lambda d:d['connections'][0].pop('network'),lambda d:d['connections'][0].pop('ports'),
    lambda d:d['connections'][0].update(ports=[]),
    lambda d:d['connections'][0].update(ports=[['absent','near:stub']]),
    lambda d:d['connections'][0].update(ports=[['branch','near:stub'],['output','near:stub']]),
    lambda d:d['connections'][0].update(port_names=None),
    lambda d:d['connections'][0].update(port_names='abc'),
    lambda d:d['connections'][0].update(port_names=['a','a','c']),
    lambda d:d['connections'][0].update(port_names=['a']),
    lambda d:d['connections'][0]['network'].update(frequency_hz=[0,1e9,5e9,11e9]),
    lambda d:d['connections'][0]['network'].update(reference_ohms=75),
    lambda d:d['network'].update(port_names='abc'),
    lambda d:d['network'].update(port_names=['a']),
    lambda d:d['network'].update(reference_ohms=True),
    lambda d:d['network'].update(reference_ohms=[50,0,50]),
    lambda d:d['network'].update(extra=1),
    lambda d:d.update(network=dict(kind='network-assembly',document={})),
    lambda d:d['connections'][0].update(network=dict(kind='network-transform',document={})),
])
def test_invalid_document_rejected(mutate):
    data=assembly().to_dict();mutate(data)
    with pytest.raises(ValueError):NetworkAssemblyDocument.from_dict(data)


def test_later_steps_use_current_port_names():
    data=assembly().to_dict()
    data['connections'].append(dict(network=line('next'),ports=[['branch','near:next']]))
    with pytest.raises(ValueError,match='known'):
        NetworkAssemblyDocument.from_dict(data)


def test_thirty_two_joins_allowed_thirty_three_rejected():
    start=node(('left','right'))
    step=dict(network=node(('join','right')),ports=[['right','join']])
    doc=NetworkAssemblyDocument(start,connections=[step]*32)
    np.testing.assert_allclose(doc.analyze().network.s,
                              np.broadcast_to([[0,1],[1,0]],(4,2,2)),rtol=0,atol=1e-12)
    with pytest.raises(ValueError,match='1..32'):
        NetworkAssemblyDocument(start,connections=[step]*33)


@pytest.mark.parametrize('text',['{"schema":1,"schema":2}','{"x":NaN}',
                                  '{"x":Infinity}','{"x":{"a":1,"a":2}}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError):NetworkAssemblyDocument.loads(text)


def test_singular_analysis_raises_without_returning_partial_assembly():
    def source(names):
        net=LineNetwork([0],[np.eye(len(names))],50,names)
        return dict(kind='touchstone',text=net.touchstone(),ports=len(names),port_names=list(names))
    doc=NetworkAssemblyDocument(source(('keep','loop')),connections=[
        dict(network=source(('loop',)),ports=[['loop','loop']])])
    saved=doc.dumps()
    with pytest.raises(ValueError,match='singular'):doc.analyze()
    assert doc.dumps()==saved
