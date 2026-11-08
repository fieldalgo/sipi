# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Version2 physical units, independent file reads and strict API separation."""
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import impedance_network,admittance_network
from sipi.touchstone import loads_touchstone,loads_touchstone_parameters
import sipi.touchstone as module


def fixture(parameter='z',n=2,form='ri',unit='hz',matrix='full',order='21_12'):
    grid=np.arange(1,n*n+1,dtype=float).reshape(n,n)
    values=np.diag(40.+5*np.arange(n))+(2+.3j)*grid
    if matrix!='full':values=(values+values.T)/2
    if parameter=='y':values*=1e-4
    values=np.stack([values,values*(.8+.2j)])
    frequency=np.array([1e6,2e6]);refs=40.+10*np.arange(n)
    lines=['[Version] 2.0',f'# {unit} {parameter} {form} R 123',f'[Number of Ports] {n}',
        '[Number of Frequencies] 2','[Reference]',' '.join(map(str,refs)),f'[Matrix Format] {matrix}']
    if n==2:lines.append(f'[Two-Port Data Order] {order}')
    lines.append('[Network Data]');factor=dict(hz=1.,khz=1e3,mhz=1e6,ghz=1e9)[unit]
    for f,m in zip(frequency,values):
        if matrix=='lower':sequence=m[np.tril_indices(n)]
        elif matrix=='upper':sequence=m[np.triu_indices(n)]
        elif n==2 and order=='21_12':sequence=m.T.flatten()
        else:sequence=m.flatten()
        numbers=[f/factor]
        for v in sequence:
            pair=(v.real,v.imag) if form=='ri' else (abs(v) if form=='ma' else 20*np.log10(abs(v)),np.angle(v,deg=True))
            numbers.extend(pair)
        tokens=[format(v,'.17g') for v in numbers]
        lines.extend(' '.join(tokens[i:i+7]) for i in range(0,len(tokens),7))
    lines.append('[End]')
    return '\n'.join(lines)+'\n',frequency,values,refs


def convert(parameter,f,values,refs,names=None):
    return (impedance_network if parameter=='z' else admittance_network)(f,values,z_ref=refs,names=names)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('n',[1,2,3,4])
@pytest.mark.parametrize('form',['ri','ma','db'])
def test_physical_units_and_nonreciprocal_order(parameter,n,form):
    text,f,values,_=fixture(parameter,n,form);target=31.+13*np.arange(n)
    net=loads_touchstone_parameters(text,z_ref=target)
    expected=convert(parameter,f,values,target)
    np.testing.assert_allclose(net.s,expected.s,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(net.frequency,f);np.testing.assert_array_equal(net.z_ref,target)
    assert net.port_names==tuple(f'port{i+1}' for i in range(n)) and net.basis=='single-ended'
    with pytest.raises(ValueError):loads_touchstone(text)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('unit',['hz','khz','mhz','ghz'])
@pytest.mark.parametrize('order',['21_12','12_21'])
def test_frequency_units_and_both_two_port_orders(parameter,unit,order):
    text,f,values,_=fixture(parameter,unit=unit,order=order)
    net=loads_touchstone_parameters(text,z_ref=[31.,61.],port_names=['a','b'],ports=2)
    np.testing.assert_allclose(net.s,convert(parameter,f,values,[31.,61.]).s,atol=1e-12,rtol=0)
    np.testing.assert_array_equal(net.frequency,f);assert net.port_names==('a','b')


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('n',[2,3,4])
@pytest.mark.parametrize('matrix',['lower','upper'])
def test_triangular_values_are_transpose_symmetric(parameter,n,matrix):
    text,f,values,_=fixture(parameter,n,matrix=matrix)
    net=loads_touchstone_parameters(text,z_ref=73.)
    np.testing.assert_allclose(net.s,convert(parameter,f,values,73.).s,atol=1e-12,rtol=0)
    np.testing.assert_allclose(net.s,net.s.swapaxes(1,2),atol=1e-12,rtol=0)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('n,form,matrix',[(1,'ri','full'),(2,'ma','full'),(3,'db','full'),(4,'ri','full'),(3,'ma','lower'),(4,'db','upper')])
def test_independent_version2_file_reader_at_explicit_target(parameter,n,form,matrix,tmp_path):
    rf=require_tool('scikit-rf');text,f,values,refs=fixture(parameter,n,form,matrix=matrix)
    path=tmp_path/f'physical-{parameter}.s{n}p';path.write_text(text,encoding='ascii');target=31.+13*np.arange(n);clock=Stopwatch()
    with clock('openphysics'):net=loads_touchstone_parameters(text,z_ref=target)
    with clock('reference'):
        peer=rf.Network(str(path));peer.renormalize(target,s_def='power')
    error=float(np.max(abs(net.s-peer.s)));assert error<=1e-12
    np.testing.assert_array_equal(net.frequency,peer.f)
    emit(make_record(case=f'touchstone2-{parameter}-{n}-{form}-{matrix}',physics='explicit physical network parameter file input',
        api='loads_touchstone_parameters',discretization='strict v2 physical Y/Z parsing then explicit positive-real target conversion',
        tool='scikit-rf',tool_discretization='Network file reader then explicit power-wave renormalization',
        matched=['file bytes','physical units','frequency','port order','target references'],
        not_matched=['parser implementation and supported subset','numerical guards'],
        observables=[observable('S','1','max_absolute',error,1e-12)],
        analytical_acceptance='Scalar resistor and rank-one series resistor are separate checks; no measurement accuracy claim.',stopwatch=clock))


def one_port(parameter,value,option_reference=100,reference='23'):
    return f'[Version] 2.0\n# Hz {parameter} RI R {option_reference}\n[Number of Ports] 1\n[Number of Frequencies] 1\n[Reference] {reference}\n[Network Data]\n0 {value} 0\n[End]\n'


@pytest.mark.parametrize('parameter,value', [('z',200.),('y',.005)])
def test_file_references_do_not_scale_physical_values_or_select_target(parameter,value):
    expected=(200.-50)/(200.+50)
    for option in [1,50,10000]:
        for reference in ['23','701']:
            net=loads_touchstone_parameters(one_port(parameter,value,option,reference),z_ref=50.)
            assert net.s[0,0,0]==pytest.approx(expected,abs=1e-12)
            assert net.z_ref[0]==50.
    text=one_port(parameter,value).replace('[Reference] 23\n','')
    assert loads_touchstone_parameters(text,z_ref=50.).s[0,0,0]==pytest.approx(expected,abs=1e-12)
    # V2 is not the normalized v1 representation: these are 2ohm / 2siemens.
    value2=loads_touchstone_parameters(one_port(parameter,2.),z_ref=100.)
    expected2=(2.-100)/(2.+100) if parameter=='z' else (1-200)/(1+200)
    assert value2.s[0,0,0]==pytest.approx(expected2,abs=1e-12)


@pytest.mark.parametrize('parameter,sign',[('z',-1),('y',1)])
def test_exact_zero_open_short(parameter,sign):
    net=loads_touchstone_parameters(one_port(parameter,0),z_ref=50.)
    assert net.s[0,0,0]==sign


def test_rank_one_admittance_series_resistor():
    text='[Version] 2.0\n# Hz Y RI R 123\n[Number of Ports] 2\n[Two-Port Data Order] 12_21\n[Number of Frequencies] 1\n[Network Data]\n0 .025 0 -.025 0 -.025 0 .025 0\n[End]\n'
    net=loads_touchstone_parameters(text,z_ref=50.)
    np.testing.assert_allclose(net.s[0],np.array([[40.,100.],[100.,40.]])/140,atol=1e-12,rtol=0)


@pytest.mark.parametrize('parameter',['z','y'])
def test_exact_physical_matrices_reach_converter_without_reference_scaling(parameter,monkeypatch):
    text,f,values,_=fixture(parameter,n=3);seen=[];sentinel=object()
    def spy(frequency,parameters,**kw):seen.append((frequency,parameters,kw));return sentinel
    monkeypatch.setattr(module,'impedance_network' if parameter=='z' else 'admittance_network',spy)
    assert loads_touchstone_parameters(text,z_ref=[31.,42.,63.],port_names=['a','b','c']) is sentinel
    assert len(seen)==1;actual_f,actual_values,kw=seen[0]
    np.testing.assert_array_equal(actual_f,f);np.testing.assert_array_equal(actual_values,values)
    assert kw==dict(z_ref=[31.,42.,63.],names=('a','b','c'))


@pytest.mark.parametrize('parameter',['z','y'])
def test_version1_rejected_including_reference_reader_discrepancy(parameter):
    text=f'# Hz {parameter} RI R 100\n1000000 2 0\n'
    with pytest.raises(ValueError,match='version2.0'):loads_touchstone_parameters(text,z_ref=50.,ports=1)


@pytest.mark.parametrize('replacement',['S','H','G',''])
def test_other_parameter_kinds_and_default_s_rejected(replacement):
    text=one_port('Z',200).replace('Hz Z RI','Hz '+replacement+' RI')
    with pytest.raises(ValueError):loads_touchstone_parameters(text,z_ref=50.)


@pytest.mark.parametrize('old,new',[
 ('[Version] 2.0','[Version] 2.1'),(' R 123',' R -1'),(' R 123',' R 50 R 75'),
 ('Hz z ri','Hz z ri ma'),('Hz z ri','Hz z y ri'),('[Reference]','[Reference] -1'),
 ('[Number of Ports] 2','[Number of Ports] 3'),('[Number of Frequencies] 2','[Number of Frequencies] 3'),
 ('[Matrix Format] full','[Matrix Format] other'),('[Matrix Format] full','[Mixed-Mode Order] D1,2'),
 ('[Matrix Format] full','[Number of Noise Frequencies] 1'),('[Two-Port Data Order] 21_12',''),
 ('[Two-Port Data Order] 21_12','[Two-Port Data Order] invalid'),('[End]',''),('[End]','[End]\n1 2 3'),
 ('[Network Data]','[Noise Data]'),('1000000','NaN'),('1000000','1e999'),('1000000','1_000_000'),
 ('2000000','1000000'),('1000000','-1'),('[Network Data]','[Number of Ports] 2\n[Network Data]'),
 ('[Number of Ports]',' [Number of Ports]'),('[End]','[End]\n# Hz z ri'),
])
def test_malformed_or_out_of_scope_files_rejected(old,new):
    text,*_=fixture();text=text.replace('# hz','# Hz');assert old in text
    with pytest.raises(ValueError):loads_touchstone_parameters(text.replace(old,new),z_ref=50.)


@pytest.mark.parametrize('kw',[{'ports':True},{'ports':3},{'port_names':['a']},{'port_names':['a','a']},
 {'z_ref':0},{'z_ref':[50]},{'z_ref':True},{'z_ref':complex(50)}, {'z_ref':[50,float('nan')]}])
def test_explicit_port_and_target_validation(kw):
    text,*_=fixture();args=dict(z_ref=50.);args.update(kw)
    with pytest.raises((ValueError,TypeError)):loads_touchstone_parameters(text,**args)


def test_target_is_required_and_comments_information_copies_are_preserved():
    text,f,_,_=fixture()
    with pytest.raises(TypeError):loads_touchstone_parameters(text)
    text='! comment\n'+text.replace('[Network Data]','[Begin Information]\nopaque metadata\n[End Information]\n[Network Data]')
    names=['a','b'];refs=[31.,61.];net=loads_touchstone_parameters(text,z_ref=refs,port_names=names)
    refs[0]=2;names[0]='other';assert net.z_ref[0]==31 and net.port_names==('a','b')
    for a in [net.s,net.frequency,net.z_ref]:assert not a.flags.writeable
    with pytest.raises(ValueError):loads_touchstone_parameters(text+'! \N{GREEK SMALL LETTER MU}',z_ref=50.)


@pytest.mark.parametrize('parameter,value',[('z',-50.),('y',-.02)])
def test_original_conditioning_gate_and_converter_failure_propagate(parameter,value,monkeypatch):
    text=one_port(parameter,value)
    with pytest.raises(ValueError,match='singular'):loads_touchstone_parameters(text,z_ref=50.)
    def fail(*a,**kw):raise RuntimeError('deliberate physical parameter conversion failure')
    monkeypatch.setattr(module,'impedance_network' if parameter=='z' else 'admittance_network',fail)
    with pytest.raises(RuntimeError,match='deliberate'):loads_touchstone_parameters(text,z_ref=50.)
