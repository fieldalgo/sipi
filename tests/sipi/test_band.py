# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Sampled network limits: exact direction, finite zeros and independent line reference."""
import json
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi.band import NetworkBandDocument, assess_band, db_to_magnitude
from sipi.network import LineNetwork, rlgc_network
from sipi.lumped import LumpedNetworkDocument
from sipi.execution import execute_saved, normalize_saved

F=[0.,1e8,2e8]


def limit(**kwargs):
    out=dict(name='transmission',input_port='near',output_port='far',frequency_hz=[0.,2e8],minimum=.75,maximum=None)
    out.update(kwargs);return out


def source():
    return dict(kind='lumped-network',document=LumpedNetworkDocument(F,resistance=25).to_dict())


def document(**kwargs):
    args=dict(network=source(),limits=[limit()]);args.update(kwargs);return NetworkBandDocument(**args)


def test_series_resistance_limits_replay_failures_and_finite_execution():
    doc=document(limits=[limit(),limit(name='reflection',output_port='near',minimum=None,maximum=.1)])
    restored=NetworkBandDocument.loads(doc.dumps())
    assert restored.dumps()==doc.dumps()==normalize_saved(doc.dumps())
    result=restored.analyze();assert not result.passed
    np.testing.assert_allclose(result.checks[0].magnitude,.8,atol=1e-15)
    np.testing.assert_allclose(result.checks[1].magnitude,.2,atol=1e-15)
    assert result.checks[0].passed and not result.checks[1].passed
    assert result.checks[1].to_dict()['failed_indices']==[0,1,2]
    out=execute_saved(doc.dumps())
    assert out['status']=='complete' and out['result']['passed'] is False
    assert out['result']==result.to_dict()
    assert out['result']['coverage']=='frequency-samples-only'
    json.dumps(out,allow_nan=False)


def test_direction_band_subset_ties_and_zero_are_explicit():
    s=np.zeros((4,2,2),complex);s[:,1,0]=[1,.8,.8,.2];s[:,0,1]=.1
    net=LineNetwork([0,1,2,3],s,[50,75],('near','far'))
    check=assess_band(net,[limit(frequency_hz=[1,2],minimum=.8,maximum=.8),
                          limit(name='reverse',frequency_hz=[0,3],input_port='far',output_port='near',minimum=.2),
                          limit(name='zero',frequency_hz=[0,3],output_port='near',minimum=0,maximum=0)])
    assert check.checks[0].passed and check.checks[0].worst_index==0
    assert check.checks[0].frequency_hz==(1.,2.)
    assert not check.checks[1].passed and check.checks[2].passed
    assert all(np.isfinite(check.checks[2].margin))
    assert check.to_dict()['reference_ohms']==[50.,75.]
    s[:]=99;assert check.checks[0].magnitude==(.8,.8)


def test_distortionless_line_against_skrf_and_closed_expression():
    skrf=require_tool('scikit-rf');clock=Stopwatch();length=.7
    alpha=np.array([.1,.2,.3]);z=50.;velocity=2e8
    with clock('openphysics'):
        net=rlgc_network(F,R=(alpha*z)[:,None,None],G=(alpha/z)[:,None,None],
                         L=[[z/velocity]],C=[[1/(z*velocity)]],length=length,names=['s'])
        result=assess_band(net,[limit(input_port='near:s',output_port='far:s',minimum=.85)])
    expected=np.exp(-alpha*length)
    np.testing.assert_allclose(result.checks[0].magnitude,expected,rtol=1e-10)
    with clock('reference'):
        frequency=skrf.Frequency.from_f(F,unit='hz')
        medium=skrf.media.DefinedGammaZ0(frequency=frequency,gamma=alpha+2j*np.pi*np.array(F)/velocity,z0=z)
        peer=medium.line(length,unit='m')
    error=float(np.max(abs(net.s-peer.s)))
    assert error<1e-10
    assert result.checks[0].to_dict()['failed_indices']==[2]
    assert result.checks[0].worst_index==2
    record=make_record(case='sampled-distortionless-line-band',physics='power-wave S magnitude limits',
        api='sipi.band.assess_band',discretization='given RLGC samples and exact port references',
        tool='scikit-rf',tool_discretization='independent DefinedGammaZ0 line',
        matched=['frequency, attenuation, phase velocity, length and reference impedance'],
        not_matched=['no unobserved frequency extrema, field extraction or measured validity'],
        observables=[observable('S','dimensionless','maximum absolute difference',error,1e-10)],
        analytical_acceptance='abs(S21)=exp(-alpha*length), relative 1e-10',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def test_saved_mixed_mode_uses_named_power_wave_ports():
    data=dict(kind='rlgc',frequency_hz=F,R=[[1,0],[0,1]],L=[[2.5e-7,0],[0,2.5e-7]],
              G=[[.0004,0],[0,.0004]],C=[[1e-10,0],[0,1e-10]],length_m=.1,reference_ohms=50,names=['p','n'])
    doc=document(network=data,basis='mixed-mode',limits=[
        limit(input_port='d_near',output_port='d_far'),
        limit(name='conversion',input_port='d_near',output_port='c_far',minimum=None,maximum=1e-12)])
    result=doc.analyze();assert result.passed
    assert result.network.port_names==('d_near','d_far','c_near','c_far')
    np.testing.assert_array_equal(result.network.z_ref,[100,100,25,25])
    assert result.to_dict()['basis']=='mixed-mode'


def test_saved_assembly_transform_and_touchstone_sources():
    from sipi.assembly_document import NetworkAssemblyDocument
    from sipi.network_document import NetworkTransformDocument
    assembly=NetworkAssemblyDocument(source(),connections=[dict(network=source(),ports=[['far','near']],port_names=['near','far'])])
    transform=NetworkTransformDocument(dict(kind='network-assembly',document=assembly.to_dict()),
                                      operations=[dict(kind='renormalize',reference_ohms=75)])
    for value in [dict(kind='network-assembly',document=assembly.to_dict()),
                  dict(kind='network-transform',document=transform.to_dict()),
                  dict(kind='touchstone',text=assembly.analyze().network.touchstone(),ports=2,port_names=['near','far'])]:
        result=document(network=value,limits=[limit(minimum=.5)]).analyze()
        assert result.passed


def test_geometry_source_preserves_field_normalization_and_actual_extraction(monkeypatch):
    from sipi import CrossSection, CrossSectionDocument, microstrip
    from sipi.line_model import TransmissionLineDocument
    line=TransmissionLineDocument(CrossSectionDocument(microstrip(width=.5e-3,substrate_height=.5e-3,
        eps_r=4,air_height=1e-3,box_width=3e-3),mesh=dict(edge_size=20e-6,far_size=.2e-3,grade=.3)),
        [1e8,2e8],materials={},conductor={'kind':'perfect'},length=.1)
    with monkeypatch.context() as m:
        m.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('normalization meshed'))
        doc=document(network=dict(kind='transmission-line',document=line.to_dict()),limits=[
            limit(input_port='near:signal',output_port='far:signal',frequency_hz=[1e8,2e8],minimum=0)])
        assert NetworkBandDocument.loads(doc.dumps()).dumps()==doc.dumps()
    actual=doc.analyze();assert actual.passed and actual.extraction is not None
    np.testing.assert_array_equal(actual.network.s,line.analyze().network.s)


@pytest.mark.parametrize('edit',[
    lambda d:d.update(schema='sipi.network-band/2'),lambda d:d.update(extra=0),
    lambda d:d.update(basis='automatic'),lambda d:d.update(basis='mixed-mode'),
    lambda d:d.update(limits=[]),lambda d:d.update(limits={}),
    lambda d:d['limits'].append(d['limits'][0]),lambda d:d['limits'][0].update(name=''),
    lambda d:d['limits'][0].update(input_port='missing'),lambda d:d['limits'][0].update(output_port=[]),
    lambda d:d['limits'][0].update(frequency_hz=[0,1e7]),lambda d:d['limits'][0].update(frequency_hz=[1e8,0]),
    lambda d:d['limits'][0].update(frequency_hz=[0,0]),lambda d:d['limits'][0].update(frequency_hz=[0]),
    lambda d:d['limits'][0].update(frequency_hz=[False,2e8]),lambda d:d['limits'][0].update(frequency_hz=[-1,2e8]),
    lambda d:d['limits'][0].update(minimum=-1),lambda d:d['limits'][0].update(minimum=True),
    lambda d:d['limits'][0].update(minimum=None),lambda d:d['limits'][0].update(maximum=.5),
    lambda d:d['limits'][0].update(maximum=float('inf')),lambda d:d['limits'][0].pop('maximum'),
])
def test_strict_saved_band_rejections(edit):
    data=document().to_dict();edit(data)
    with pytest.raises(ValueError):NetworkBandDocument.from_dict(data)


@pytest.mark.parametrize('value',[True,float('inf'),float('nan'),[0],10000,-10000])
def test_db_limit_rejects_nonfinite_nonrepresentable_values(value):
    with pytest.raises(ValueError):db_to_magnitude(value)


def test_db_conversion_and_input_snapshot():
    assert db_to_magnitude(-20)==pytest.approx(.1,rel=1e-15)
    assert db_to_magnitude(0)==1
    limits=[limit()];doc=document(limits=limits);limits[0]['minimum']=99
    out=doc.to_dict();out['limits'][0]['minimum']=88
    assert doc.to_dict()['limits'][0]['minimum']==.75
    with pytest.raises(ValueError):NetworkBandDocument.loads(doc.dumps().replace('"basis":','"basis":"single-ended", "basis":',1))
