# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit physical hybrid files, independent reader and legacy separation."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import hybrid_network,inverse_hybrid_network
from sipi.touchstone import loads_touchstone,loads_touchstone_parameters,loads_touchstone_hybrid
import sipi.touchstone as module

def fixture(parameter='h',form='ri',unit='hz',matrix='full',order='21_12'):
    base=np.array([[80.+.5j,.2+.1j],[-.1+.04j,.01+.002j]]) if parameter=='h' else np.array([[.02+.003j,.15-.05j],[-.12+.02j,60.+.7j]])
    if matrix!='full':base=(base+base.T)/2
    values=np.stack([base,base*(.8+.2j)]);frequency=np.array([1e6,2e6]);refs=np.array([40.,90.])
    lines=['[Version] 2.0',f'# {unit} {parameter} {form} R 123','[Number of Ports] 2',
       '[Number of Frequencies] 2','[Reference]','40 90',f'[Matrix Format] {matrix}',
       f'[Two-Port Data Order] {order}','[Network Data]']
    factor=dict(hz=1.,khz=1e3,mhz=1e6,ghz=1e9)[unit]
    for f,m in zip(frequency,values):
        if matrix=='lower':sequence=m[np.tril_indices(2)]
        elif matrix=='upper':sequence=m[np.triu_indices(2)]
        elif order=='21_12':sequence=m.T.flatten()
        else:sequence=m.flatten()
        numbers=[f/factor]
        for v in sequence:
            pair=(v.real,v.imag) if form=='ri' else (abs(v) if form=='ma' else 20*np.log10(abs(v)),np.angle(v,deg=True))
            numbers.extend(pair)
        tokens=[format(v,'.17g') for v in numbers]
        lines.extend(' '.join(tokens[i:i+7]) for i in range(0,len(tokens),7))
    lines.append('[End]');return '\n'.join(lines)+'\n',frequency,values,refs


def convert(parameter,f,values,refs,names=None):
    return (hybrid_network if parameter=='h' else inverse_hybrid_network)(f,values,z_ref=refs,names=names)


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('form',['ri','ma','db'])
def test_physical_mixed_units_and_nonreciprocal_order(parameter,form):
    text,f,values,_=fixture(parameter,form);target=[31.,73.]
    net=loads_touchstone_hybrid(text,z_ref=target)
    np.testing.assert_allclose(net.s,convert(parameter,f,values,target).s,atol=1e-12,rtol=0.)
    np.testing.assert_array_equal(net.frequency,f);np.testing.assert_array_equal(net.z_ref,target)
    assert net.port_names==('port1','port2') and net.basis=='single-ended'
    for reader in [loads_touchstone,lambda text:loads_touchstone_parameters(text,z_ref=target)]:
        with pytest.raises(ValueError):reader(text)


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('unit',['hz','khz','mhz','ghz'])
@pytest.mark.parametrize('order',['21_12','12_21'])
def test_frequency_units_and_two_port_orders(parameter,unit,order):
    text,f,values,_=fixture(parameter,unit=unit,order=order)
    net=loads_touchstone_hybrid(text,z_ref=[31.,73.],ports=2,port_names=['a','b'])
    np.testing.assert_allclose(net.s,convert(parameter,f,values,[31.,73.]).s,atol=1e-12,rtol=0.)
    np.testing.assert_array_equal(net.frequency,f);assert net.port_names==('a','b')


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('matrix',['lower','upper'])
@pytest.mark.parametrize('order',['21_12','12_21'])
def test_numeric_triangles_are_order_independent_not_reciprocity(parameter,matrix,order):
    text,f,values,_=fixture(parameter,matrix=matrix,order=order)
    net=loads_touchstone_hybrid(text,z_ref=[31.,73.])
    np.testing.assert_allclose(net.s,convert(parameter,f,values,[31.,73.]).s,atol=1e-12,rtol=0.)
    full,*_=fixture(parameter,matrix=matrix,order='12_21')
    np.testing.assert_array_equal(net.s,loads_touchstone_hybrid(full,z_ref=[31.,73.]).s)
    assert np.max(abs(net.s-net.s.swapaxes(1,2)))>1e-3
    # Numeric H/G symmetry is not hybrid reciprocity (off-diagonals opposite).


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('form,matrix,order',[(f,'full',o) for f in ['ri','ma','db'] for o in ['21_12','12_21']]+[(f,m,'12_21') for f in ['ri','ma'] for m in ['lower','upper']])
def test_independent_file_reader_with_qualified_triangular_order(parameter,form,matrix,order,tmp_path):
    rf=require_tool('scikit-rf');text,f,values,refs=fixture(parameter,form,matrix=matrix,order=order)
    path=tmp_path/f'physical-{parameter}.s2p';path.write_text(text,encoding='ascii');target=[31.,73.];clock=Stopwatch()
    with clock('openphysics'):net=loads_touchstone_hybrid(text,z_ref=target)
    with clock('reference'):
        peer=rf.Network(str(path));peer.renormalize(target,s_def='power')
    error=float(np.max(abs(net.s-peer.s)));assert error<1e-12
    np.testing.assert_array_equal(net.frequency,peer.f)
    record=make_record(case=f'touchstone2-{parameter}-{form}-{matrix}-{order}',physics='physical two-port hybrid network files',
        api='loads_touchstone_hybrid',discretization='strict v2 physical H/G parsing and direct wave conversion',
        tool='scikit-rf',tool_discretization='Network file reader and target power-wave renormalization',
        matched=['file bytes','physical mixed units','frequency','port order','target references'],
        not_matched=['parser implementation','triangular21_12 reference path has a preserved transpose/mirror failure and is not counted here'],
        observables=[observable('S','1','max_absolute',error,1e-12)],
        analytical_acceptance='Exact zero H/G, ideal transformers and rank-one inverse-hybrid closed form; no physical extraction or spatial convergence.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def literal(parameter,values,option=123,reference='40 90'):
    numbers=' '.join(f'{v.real:.17g} {v.imag:.17g}' for v in np.asarray(values,dtype=complex).flatten())
    return f'[Version] 2.0\n# Hz {parameter} RI R {option}\n[Number of Ports] 2\n[Two-Port Data Order] 12_21\n[Number of Frequencies] 1\n[Reference] {reference}\n[Network Data]\n0 {numbers}\n[End]\n'


@pytest.mark.parametrize('parameter',['h','g'])
def test_file_references_do_not_scale_data_or_select_target(parameter):
    values=np.array([[80.,.2],[-.1,.01]]) if parameter=='h' else np.array([[.02,.15],[-.12,60.]])
    expected=convert(parameter,[0.],values[None],[31.,73.])
    for option in [1,50,10000]:
        for reference in ['23 71','701 3']:
            net=loads_touchstone_hybrid(literal(parameter,values,option,reference),z_ref=[31.,73.])
            np.testing.assert_array_equal(net.s,expected.s);np.testing.assert_array_equal(net.z_ref,[31.,73.])
    text=literal(parameter,values).replace('[Reference] 40 90\n','')
    np.testing.assert_array_equal(loads_touchstone_hybrid(text,z_ref=[31.,73.]).s,expected.s)


@pytest.mark.parametrize('parameter',['h','g'])
def test_exact_zero_open_short_and_ideal_transformer(parameter):
    zero=loads_touchstone_hybrid(literal(parameter,np.zeros((2,2))),z_ref=[31.,73.])
    np.testing.assert_array_equal(zero.s[0],np.diag([1.,-1.]) if parameter=='g' else np.diag([-1.,1.]))
    for t in [1.,2.]:
        value=[[0.,-1/t],[1/t,0.]] if parameter=='g' else [[0.,t],[-t,0.]]
        net=loads_touchstone_hybrid(literal(parameter,value),z_ref=[31.,73.])
        den=31.+t*t*73.;q=(t*t*73.-31.)/den;c=2*t*np.sqrt(31.*73.)/den
        np.testing.assert_allclose(net.s[0],[[q,c],[c,-q]],atol=1e-12,rtol=0.)


def test_rank_one_admittance_encoded_as_inverse_hybrid_uses_direct_wave_equations():
    a=.02+.01j;g=np.array([[0.,.5],[-.5,1/(4*a)]])
    result=loads_touchstone_hybrid(literal('g',g),z_ref=1.)
    expected=np.eye(2)-2*a/(1+5*a)*np.array([[1.,2.],[2.,4.]])
    np.testing.assert_allclose(result.s[0],expected,atol=1e-12,rtol=0.)
    # No g2s reference claim: that path constructs nonexistent finite Z.


@pytest.mark.parametrize('parameter',['h','g'])
def test_exact_raw_matrix_reaches_one_converter_without_reference_scaling(parameter,monkeypatch):
    text,f,values,_=fixture(parameter);seen=[];sentinel=object()
    def spy(frequency,parameters,**kw):seen.append((frequency,parameters,kw));return sentinel
    monkeypatch.setattr(module,'hybrid_network' if parameter=='h' else 'inverse_hybrid_network',spy)
    assert loads_touchstone_hybrid(text,z_ref=[31.,73.],port_names=['a','b']) is sentinel
    assert len(seen)==1;actual_f,actual_values,kw=seen[0]
    np.testing.assert_array_equal(actual_f,f);np.testing.assert_array_equal(actual_values,values)
    assert kw==dict(z_ref=[31.,73.],names=('a','b'))


@pytest.mark.parametrize('parameter',['h','g'])
def test_version1_rejected(parameter):
    text=f'# Hz {parameter} RI R 100\n1000000 1 0 0 0 0 0 1 0\n'
    with pytest.raises(ValueError,match='version2.0'):loads_touchstone_hybrid(text,z_ref=50.,ports=2)


@pytest.mark.parametrize('replacement',['S','Y','Z',''])
def test_other_parameter_kinds_and_default_s_rejected(replacement):
    text=literal('H',np.eye(2)).replace('Hz H RI','Hz '+replacement+' RI')
    with pytest.raises(ValueError):loads_touchstone_hybrid(text,z_ref=50.)


@pytest.mark.parametrize('n',[1,3])
def test_exactly_two_ports_required_before_conversion(n,monkeypatch):
    text=f'[Version] 2.0\n# Hz H RI R 50\n[Number of Ports] {n}\n[Number of Frequencies] 1\n[Network Data]\n0 '+' '.join(['1 0']*(n*n))+'\n[End]\n'
    def fail(*a,**kw):pytest.fail('invalid port count reached conversion')
    monkeypatch.setattr(module,'hybrid_network',fail)
    with pytest.raises(ValueError,match='exactly two ports'):loads_touchstone_hybrid(text,z_ref=50.)


@pytest.mark.parametrize('old,new',[
 ('[Version] 2.0','[Version] 2.1'),(' R 123',' R -1'),(' R 123',' R 50 R 75'),
 ('Hz h ri','Hz h ri ma'),('Hz h ri','Hz h g ri'),('[Reference]','[Reference] -1'),
 ('[Number of Ports] 2','[Number of Ports] 3'),('[Number of Frequencies] 2','[Number of Frequencies] 3'),
 ('[Matrix Format] full','[Matrix Format] other'),('[Matrix Format] full','[Mixed-Mode Order] D1,2'),
 ('[Matrix Format] full','[Number of Noise Frequencies] 1'),('[Two-Port Data Order] 21_12',''),
 ('[Two-Port Data Order] 21_12','[Two-Port Data Order] invalid'),('[End]',''),('[End]','[End]\n1 2 3'),
 ('[Network Data]','[Noise Data]'),('1000000','NaN'),('1000000','1e999'),('1000000','1_000_000'),
 ('2000000','1000000'),('1000000','-1'),('[Network Data]','[Number of Ports] 2\n[Network Data]'),
 ('[Number of Ports]',' [Number of Ports]'),('[End]','[End]\n# Hz h ri'),
])
def test_malformed_or_out_of_scope_files_rejected(old,new):
    text,*_=fixture();text=text.replace('# hz','# Hz');assert old in text
    with pytest.raises(ValueError):loads_touchstone_hybrid(text.replace(old,new),z_ref=50.)


@pytest.mark.parametrize('kw',[{'ports':True},{'ports':3},{'port_names':['a']},{'port_names':['a','a']},{'port_names':'ab'},
 {'z_ref':0},{'z_ref':[50]},{'z_ref':True},{'z_ref':complex(50)}, {'z_ref':[50,float('nan')]}])
def test_explicit_port_target_and_names(kw):
    text,*_=fixture();args=dict(z_ref=50.);args.update(kw)
    with pytest.raises((ValueError,TypeError)):loads_touchstone_hybrid(text,**args)


def test_target_required_ascii_comments_information_and_copies():
    text,*_=fixture()
    with pytest.raises(TypeError):loads_touchstone_hybrid(text)
    text='! comment\n'+text.replace('[Network Data]','[Begin Information]\nopaque metadata\n[End Information]\n[Network Data]')
    names=['a','b'];refs=[31.,73.];net=loads_touchstone_hybrid(text,z_ref=refs,port_names=names)
    refs[0]=2;names[0]='other';assert net.z_ref[0]==31 and net.port_names==('a','b')
    for x in [net.s,net.frequency,net.z_ref]:assert not x.flags.writeable
    with pytest.raises(ValueError):loads_touchstone_hybrid(text+'! μ',z_ref=50.)


@pytest.mark.parametrize('parameter',['h','g'])
def test_original_conditioning_gate_and_failure_propagate(parameter,monkeypatch):
    text=literal(parameter,np.diag([-1.,1.]))
    with pytest.raises(ValueError,match='singular'):loads_touchstone_hybrid(text,z_ref=1.)
    def fail(*a,**kw):raise RuntimeError('deliberate hybrid conversion failure')
    monkeypatch.setattr(module,'hybrid_network' if parameter=='h' else 'inverse_hybrid_network',fail)
    with pytest.raises(RuntimeError,match='deliberate'):loads_touchstone_hybrid(text,z_ref=1.)
