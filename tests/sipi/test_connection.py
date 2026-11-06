# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Known networks: analytic composition and independent scikit-rf checks."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from sipi import LineNetwork, cascade_networks, deembed_network, rlgc_network


def series(resistance, names=('near','far')):
    r = resistance/(100+resistance)
    return LineNetwork([0,1e6,1e9], np.tile([[r,1-r],[1-r,r]], (3,1,1)), 50, names)


def line(length, conductors=1):
    eye = np.eye(conductors)
    return rlgc_network([0,1e6,1e9], R=2*eye, L=400e-9*eye,
                        G=.002*eye, C=100e-12*eye, length=length)


def test_through_and_series_resistance_are_analytic():
    a, b = series(100), series(35)
    np.testing.assert_allclose(cascade_networks(a,b).s, series(135).s, rtol=0,atol=1e-12)
    np.testing.assert_allclose(cascade_networks(series(0),b).s, b.s,rtol=0,atol=1e-12)
    # det(S)=0 for a, but the voltage/current relation is invertible.
    assert np.linalg.det(a.s[0]) == 0
    recovered = deembed_network(series(135),left=a,port_names=('near','far'))
    np.testing.assert_allclose(recovered.s,b.s,rtol=0,atol=1e-12)


@pytest.mark.parametrize('n',[1,2])
def test_uniform_line_lengths_add(n):
    result = cascade_networks(line(.03,n),line(.07,n))
    np.testing.assert_allclose(result.s,line(.1,n).s,rtol=0,atol=1e-10)


@pytest.mark.parametrize('side',['left','right','both'])
def test_known_fixture_removal_unequal_references_and_metadata(side):
    dut = line(.07).renormalized([30,90])
    left = series(100,('outerL','innerL')).renormalized([45,30])
    right = series(20,('innerR','outerR')).renormalized([90,75])
    measured = dut
    if side in ('left','both'):
        measured = cascade_networks(left,measured)
    if side in ('right','both'):
        measured = cascade_networks(measured,right)
    kwargs = dict(left=left if side in ('left','both') else None,
                  right=right if side in ('right','both') else None)
    recovered = deembed_network(measured,**kwargs)
    np.testing.assert_allclose(recovered.s,dut.s,rtol=0,atol=1e-10)
    np.testing.assert_array_equal(recovered.z_ref,dut.z_ref)
    assert recovered.port_names == (('innerL' if kwargs['left'] else dut.port_names[0]),
                                    ('innerR' if kwargs['right'] else dut.port_names[1]))
    assert not recovered.s.flags.writeable
    assert not np.shares_memory(recovered.s,measured.s)


def random_network(n,seed,refs):
    rng = np.random.default_rng(seed)
    s = .03*(rng.normal(size=(3,2*n,2*n))+1j*rng.normal(size=(3,2*n,2*n)))
    s[:,:n,n:] += .7*np.eye(n)
    s[:,n:,:n] += .8*np.eye(n)
    return LineNetwork([0,1e6,1e9],s,refs,tuple(f'p{k}' for k in range(2*n)))


@pytest.mark.parametrize('n',[1,2])
def test_independent_noncommuting_cascade_and_deembed(n):
    skrf = require_tool('scikit-rf')
    z1,z2,z3,z4 = [np.linspace(x,x+10,n) for x in (35,50,70,90)]
    a = random_network(n,23,np.r_[z1,z2])
    dut = random_network(n,27,np.r_[z2,z3])
    b = random_network(n,31,np.r_[z3,z4])
    convert = lambda x: skrf.Network(frequency=skrf.Frequency.from_f(x.frequency,unit='Hz'),
                                     s=x.s.copy(),z0=x.z_ref)
    clock = Stopwatch()
    with clock('openphysics'):
        measured = cascade_networks(cascade_networks(a,dut),b)
        recovered = deembed_network(measured,left=a,right=b,
                                   port_names=dut.port_names)
    with clock('reference'):
        reference = convert(a)**convert(dut)**convert(b)
        removed = convert(a).inv**convert(measured)**convert(b).inv
    errors = [float(np.max(abs(measured.s-reference.s))),
              float(np.max(abs(recovered.s-removed.s))),
              float(np.max(abs(recovered.s-dut.s)))]
    record = make_record(case=f'known-fixture-{2*n}-port',physics='multiport network connection',
        api='sipi.cascade_networks/deembed_network',
        discretization='scattering feedback and wave-chain linear solves',
        tool='scikit-rf',tool_discretization='Network cascade and inverse',
        matched=['same complex S samples, near/far port groups and positive real port references'],
        not_matched=[],observables=[observable(name,'1','max absolute difference',e,1e-10)
            for name,e in zip(('cascade S','deembedded S','known DUT recovery'),errors)],
        analytical_acceptance='series resistor and uniform-line length addition; not fixture estimation',
        stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert max(errors) <= 1e-10
    np.testing.assert_allclose(recovered.z_ref,dut.z_ref,rtol=0,atol=0)


def test_opaque_fixture_rejected_but_forward_cascade_allowed():
    opaque = LineNetwork([0,1e6,1e9],np.zeros((3,2,2)),50,('near','far'))
    np.testing.assert_array_equal(cascade_networks(opaque,series(0)).s,opaque.s)
    with pytest.raises(ValueError,match='singular'):
        deembed_network(opaque,left=opaque)


def test_ill_conditioned_attenuation_rejected_without_regularization():
    tiny = LineNetwork([0],[[[0,1e-8],[1e-8,0]]],50,('near','far'))
    with pytest.raises(ValueError,match='ill-conditioned'):
        deembed_network(tiny,left=tiny)


def test_singular_feedback_rejected():
    open_ports = LineNetwork([0], [np.eye(2)],50,('near','far'))
    with pytest.raises(ValueError,match='singular'):
        cascade_networks(open_ports,open_ports)


@pytest.mark.parametrize('operation',['cascade','left','right'])
@pytest.mark.parametrize('mismatch',['frequency','ports','references','basis','type'])
def test_incompatible_networks_rejected(operation,mismatch):
    good = series(25)
    if mismatch=='frequency':
        bad = LineNetwork([0,2e6,1e9],good.s,50,good.port_names)
    elif mismatch=='ports':
        bad = line(.03,2)
    elif mismatch=='references':
        bad = good.renormalized(75)
    elif mismatch=='basis':
        bad = LineNetwork(good.frequency,good.s,50,good.port_names,'mixed-mode')
    else:
        bad = object()
    with pytest.raises((ValueError,TypeError)):
        if operation=='cascade':
            cascade_networks(good,bad)
        else:
            deembed_network(good,**{operation:bad})


def test_missing_fixture_odd_ports_and_duplicate_output_names():
    with pytest.raises(ValueError,match='at least one'):
        deembed_network(series(0))
    odd = LineNetwork([0],[[[0]]],50,('a',))
    with pytest.raises(ValueError,match='2N'):
        cascade_networks(odd,odd)
    a,b = series(10,('outer','inner')),series(15,('inner','outer'))
    with pytest.raises(ValueError,match='unique'):
        cascade_networks(a,b)
    result = cascade_networks(a,b,port_names=('L','R'))
    assert result.port_names == ('L','R')
