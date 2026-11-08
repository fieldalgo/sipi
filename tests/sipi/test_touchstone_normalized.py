# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Version1 normalized physical inputs with explicit target and reference limits."""
import importlib.metadata as metadata
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import impedance_network,admittance_network,hybrid_network,inverse_hybrid_network
from sipi.touchstone import loads_touchstone,loads_touchstone_parameters,loads_touchstone_hybrid,loads_touchstone_normalized
import sipi.touchstone as module
APIS=dict(z=impedance_network,y=admittance_network,h=hybrid_network,g=inverse_hybrid_network)

def fixture(parameter='z',n=2,form='ri',unit='hz',reference=100.,version=1):
    grid=np.arange(1,n*n+1,dtype=float).reshape(n,n)
    base=np.diag(40.+5*np.arange(n))+(2+.3j)*grid
    if parameter=='y':base*=1e-4
    elif parameter=='h':base=np.array([[80.+.5j,.2+.1j],[-.1+.04j,.01+.002j]])
    elif parameter=='g':base=np.array([[.02+.003j,.15-.05j],[-.12+.02j,60.+.7j]])
    physical=np.stack([base,base*(.8+.2j)]);raw=physical.copy()
    if version==1:
        if parameter=='z':raw/=reference
        elif parameter=='y':raw*=reference
        elif parameter=='h':raw[:,0,0]/=reference;raw[:,1,1]*=reference
        else:raw[:,0,0]*=reference;raw[:,1,1]/=reference
    frequency=np.array([1e6,2e6]);lines=[]
    if version==2:lines.append('[Version] 2.0')
    lines.append(f'# {unit} {parameter} {form} R {reference}')
    if version==2:
        lines.extend([f'[Number of Ports] {n}','[Number of Frequencies] 2'])
        if n==2:lines.append('[Two-Port Data Order] 21_12')
        lines.append('[Network Data]')
    factor=dict(hz=1.,khz=1e3,mhz=1e6,ghz=1e9)[unit]
    for f,m in zip(frequency,raw):
        sequence=m.T.flatten() if n==2 else m.flatten();numbers=[f/factor]
        for v in sequence:
            numbers.extend((v.real,v.imag) if form=='ri' else (abs(v) if form=='ma' else 20*np.log10(abs(v)),np.angle(v,deg=True)))
        tokens=[format(x,'.17g') for x in numbers]
        if n<=2:lines.append(' '.join(tokens))
        else:
            lines.append(' '.join(tokens[:9]))
            lines.extend(' '.join(tokens[i:i+8]) for i in range(9,len(tokens),8))
    if version==2:lines.append('[End]')
    return '\n'.join(lines)+'\n',frequency,physical,raw


@pytest.mark.parametrize('parameter',['z','y','h','g'])
@pytest.mark.parametrize('form',['ri','ma','db'])
@pytest.mark.parametrize('reference',[1.,50.,100.])
def test_normalization_and_mixed_units(parameter,form,reference):
    text,f,physical,_=fixture(parameter,form=form,reference=reference)
    net=loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.])
    np.testing.assert_allclose(net.s,APIS[parameter](f,physical,z_ref=[31.,73.]).s,atol=1e-12,rtol=0.)
    np.testing.assert_array_equal(net.frequency,f);np.testing.assert_array_equal(net.z_ref,[31.,73.])
    assert net.port_names==('port1','port2') and net.basis=='single-ended'
    for reader in [lambda s:loads_touchstone(s,ports=2),lambda s:loads_touchstone_parameters(s,z_ref=50.,ports=2),lambda s:loads_touchstone_hybrid(s,z_ref=50.,ports=2)]:
        with pytest.raises(ValueError):reader(text)


@pytest.mark.parametrize('parameter',['z','y'])
@pytest.mark.parametrize('n',[1,2,3,4])
@pytest.mark.parametrize('form',['ri','ma','db'])
def test_explicit_port_counts_and_row_major_three_plus_ports(parameter,n,form):
    text,f,physical,_=fixture(parameter,n=n,form=form);target=31.+13*np.arange(n)
    net=loads_touchstone_normalized(text,ports=n,z_ref=target)
    np.testing.assert_allclose(net.s,APIS[parameter](f,physical,z_ref=target).s,atol=1e-12,rtol=0.)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
@pytest.mark.parametrize('unit',['hz','khz','mhz','ghz'])
def test_frequency_units_and_fixed_v1_two_port_order(parameter,unit):
    text,f,physical,_=fixture(parameter,unit=unit)
    net=loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.],port_names=['a','b'])
    np.testing.assert_array_equal(net.frequency,f);assert net.port_names==('a','b')
    np.testing.assert_allclose(net.s,APIS[parameter](f,physical,z_ref=[31.,73.]).s,atol=1e-12,rtol=0.)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
def test_equivalent_input_reference_changes_preserve_physical_network(parameter):
    values=[]
    for reference in [1.,50.,100.,10000.]:
        text,*_=fixture(parameter,reference=reference)
        values.append(loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.]).s)
    for s in values[1:]:np.testing.assert_allclose(s,values[0],atol=1e-12,rtol=0.)
    text,*_=fixture(parameter,reference=50.)
    np.testing.assert_array_equal(loads_touchstone_normalized(text.replace(' R 50.0',''),ports=2,z_ref=[31.,73.]).s,values[1])


@pytest.mark.parametrize('parameter,reference',[('z',1.),('z',50.),('z',100.),('z',10000.),('y',1.),('h',1.),('g',1.)])
@pytest.mark.parametrize('form',['ri','ma','db'])
def test_qualified_same_file_independent_reader(parameter,reference,form,tmp_path):
    rf=require_tool('scikit-rf');text,*_=fixture(parameter,form=form,reference=reference)
    path=tmp_path/f'normalized-{parameter}.s2p';path.write_text(text,encoding='ascii');clock=Stopwatch()
    with clock('openphysics'):net=loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.])
    with clock('reference'):
        peer=rf.Network(str(path));peer.renormalize([31.,73.],s_def='power')
    error=float(np.max(abs(net.s-peer.s)));assert error<1e-12
    record=make_record(case=f'normalized-v1-{parameter}-{reference}-{form}',physics='normalized physical network file input',api='loads_touchstone_normalized',
        discretization='strict v1 parsing, dimensionally recovered physical values, direct wave conversion',tool='scikit-rf',
        tool_discretization='same-file Network read and explicit target renormalization; Z or R1 qualification',
        matched=['file bytes','frequency','physical units in qualified reference subset','target'],
        not_matched=['implementation and conditioning','v1 Y/H/G at R!=1 reference normalization is not accepted'],
        observables=[observable('S','1','max_absolute',error,1e-12)],
        analytical_acceptance='Scalar Z/Y, mixed H/G diagonal, through/transformer and reference-invariant physical networks; no spatial extraction.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
@pytest.mark.parametrize('reference',[50.,100.,10000.])
def test_independent_equivalent_physical_v2_file_is_not_same_file_claim(parameter,reference,tmp_path):
    rf=require_tool('scikit-rf');text,*_=fixture(parameter,reference=reference)
    physical_text,*_=fixture(parameter,reference=reference,version=2)
    path=tmp_path/f'physical-{parameter}.s2p';path.write_text(physical_text,encoding='ascii');clock=Stopwatch()
    with clock('openphysics'):net=loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.])
    with clock('reference'):
        peer=rf.Network(str(path));peer.renormalize([31.,73.],s_def='power')
    error=float(np.max(abs(net.s-peer.s)));assert error<1e-12
    record=make_record(case=f'normalized-v1-equivalent-v2-{parameter}-{reference}',physics='equivalent normalized/physical network data',api='loads_touchstone_normalized',
        discretization='version1 normalized input recovered using declared mixed units',tool='scikit-rf',
        tool_discretization='independently generated physical version2 file read and target renormalization',
        matched=['original physical matrices','frequency','port order','target'],
        not_matched=['file bytes and version','v1 Y/H/G reference parser is not used'],
        observables=[observable('S','1','max_absolute',error,1e-12)],
        analytical_acceptance='Separate scalar/mixed-unit analytical cases and explicit input-reference invariance; equivalent representation, not identical bytes.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)


def literal(parameter,raw,reference=100.):
    a=np.asarray(raw,dtype=complex);n=len(a);sequence=a.T.flatten() if n==2 else a.flatten()
    return f'# Hz {parameter} RI R {reference}\n0 '+' '.join(f'{v.real:.17g} {v.imag:.17g}' for v in sequence)+'\n'


@pytest.mark.parametrize('reference',[1.,50.,100.,10000.])
def test_scalar_and_mixed_diagonal_analytic_normalization(reference):
    z=loads_touchstone_normalized(literal('z',[[2.]],reference),ports=1,z_ref=reference)
    y=loads_touchstone_normalized(literal('y',[[2.]],reference),ports=1,z_ref=reference)
    np.testing.assert_allclose(z.s,[[[1/3]]],atol=1e-12,rtol=0.)
    np.testing.assert_allclose(y.s,[[[-1/3]]],atol=1e-12,rtol=0.)
    for parameter,expected in [('h',[1/3,1/3]),('g',[-1/3,-1/3])]:
        net=loads_touchstone_normalized(literal(parameter,np.diag([2.,.5]),reference),ports=2,z_ref=reference)
        np.testing.assert_allclose(net.s[0],np.diag(expected),atol=1e-12,rtol=0.)


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('reference',[1.,50.,10000.])
def test_dimensionless_off_diagonals_and_zero_boundaries(parameter,reference):
    for turns in [1.,2.]:
        t=turns;value=[[0.,-1/t],[1/t,0.]] if parameter=='g' else [[0.,t],[-t,0.]]
        net=loads_touchstone_normalized(literal(parameter,value,reference),ports=2,z_ref=[31.,73.])
        den=31.+t*t*73.;q=(t*t*73.-31.)/den;c=2*t*np.sqrt(31.*73.)/den
        np.testing.assert_allclose(net.s[0],[[q,c],[c,-q]],atol=1e-12,rtol=0.)
    zero=loads_touchstone_normalized(literal(parameter,np.zeros((2,2)),reference),ports=2,z_ref=[31.,73.])
    np.testing.assert_array_equal(zero.s[0],np.diag([1.,-1.]) if parameter=='g' else np.diag([-1.,1.]))


@pytest.mark.parametrize('parameter',['z','y','h','g'])
def test_one_recovered_physical_matrix_call_and_original_input_preservation(parameter,monkeypatch):
    text,f,physical,_=fixture(parameter,reference=100.);before=text;seen=[];sentinel=object()
    def spy(frequency,parameters,**kw):seen.append((frequency,parameters.copy(),kw));parameters[:]=99;return sentinel
    monkeypatch.setattr(module,APIS[parameter].__name__,spy)
    assert loads_touchstone_normalized(text,ports=2,z_ref=[31.,73.],port_names=['a','b']) is sentinel
    assert len(seen)==1 and text==before
    np.testing.assert_array_equal(seen[0][0],f);np.testing.assert_allclose(seen[0][1],physical,atol=0.,rtol=3e-16)
    assert seen[0][2]==dict(z_ref=[31.,73.],names=('a','b'))


@pytest.mark.parametrize('parameter',['h','g'])
@pytest.mark.parametrize('n',[1,3])
def test_hybrid_port_count_rejects_before_conversion(parameter,n,monkeypatch):
    text=literal(parameter,np.eye(n));monkeypatch.setattr(module,APIS[parameter].__name__,lambda *a,**kw:pytest.fail('bad port count converted'))
    with pytest.raises(ValueError,match='exactly two ports'):loads_touchstone_normalized(text,ports=n,z_ref=50.)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
def test_version2_and_default_s_are_rejected(parameter):
    text,*_=fixture(parameter,version=2)
    with pytest.raises(ValueError,match='version1.0'):loads_touchstone_normalized(text,ports=2,z_ref=50.)
    text,*_=fixture(parameter)
    for kind in ['s','']:
        with pytest.raises(ValueError):loads_touchstone_normalized(text.replace(f'hz {parameter} ri',f'hz {kind} ri'),ports=2,z_ref=50.)


@pytest.mark.parametrize('old,new',[
 ('R 100.0','R -1'),('R 100.0','R 0'),('R 100.0','R 100 200'),('R 100.0','R 100 R 50'),
 ('hz z ri','hz z ri ma'),('hz z ri','hz z y ri'),('1000000','NaN'),('1000000','1e999'),
 ('1000000','1_000_000'),('1000000','-1'),('2000000','1000000'),
 ('# hz','[Version] 1.0\n# hz'),('# hz','[Number of Ports] 2\n# hz'),
 ('2000000','[Noise Data]\n2000000'),('2000000','# Hz Z RI\n2000000'),
])
def test_malformed_v1_records_and_multiple_references_reject(old,new):
    text,*_=fixture();assert old in text
    with pytest.raises(ValueError):loads_touchstone_normalized(text.replace(old,new),ports=2,z_ref=50.)


@pytest.mark.parametrize('kw',[{'ports':None},{'ports':True},{'ports':0},{'ports':3},
 {'port_names':'ab'},{'port_names':['a']},{'port_names':['a','a']},
 {'z_ref':0},{'z_ref':[50]},{'z_ref':True},{'z_ref':complex(50)},{'z_ref':[50,np.nan]}])
def test_explicit_ports_target_and_names(kw):
    text,*_=fixture();args=dict(ports=2,z_ref=50.);args.update(kw)
    with pytest.raises((ValueError,TypeError)):loads_touchstone_normalized(text,**args)


def test_required_arguments_ascii_copies_and_no_implicit_pairing():
    text,*_=fixture()
    with pytest.raises(TypeError):loads_touchstone_normalized(text,z_ref=50.)
    with pytest.raises(TypeError):loads_touchstone_normalized(text,ports=2)
    names=['a','b'];refs=[31.,73.];net=loads_touchstone_normalized('! comment\n'+text,ports=2,z_ref=refs,port_names=names)
    names[0]='other';refs[0]=1;assert net.port_names==('a','b') and net.z_ref[0]==31.
    for a in [net.s,net.frequency,net.z_ref]:assert not a.flags.writeable
    with pytest.raises(ValueError):loads_touchstone_normalized(text+'! μ',ports=2,z_ref=50.)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
def test_physical_overflow_rejected_before_converter(parameter,monkeypatch):
    reference=1e308 if parameter in ['z','h'] else 1e-308
    values=np.full((2,2),1e308);text=literal(parameter,values,reference)
    monkeypatch.setattr(module,APIS[parameter].__name__,lambda *a,**kw:pytest.fail('nonfinite physical data converted'))
    with pytest.raises(ValueError,match='finite physical'):loads_touchstone_normalized(text,ports=2,z_ref=50.)


@pytest.mark.parametrize('parameter',['z','y','h','g'])
def test_original_conditioning_gate_and_failure_propagate(parameter,monkeypatch):
    values=np.diag([-1.,1.]);text=literal(parameter,values,1.)
    with pytest.raises(ValueError,match='singular'):loads_touchstone_normalized(text,ports=2,z_ref=1.)
    def fail(*a,**kw):raise RuntimeError('deliberate normalized conversion failure')
    monkeypatch.setattr(module,APIS[parameter].__name__,fail)
    with pytest.raises(RuntimeError,match='deliberate'):loads_touchstone_normalized(text,ports=2,z_ref=1.)
