# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit partitioned dielectric fields, grounded electrode networks and legacy parity."""
import importlib.metadata as metadata
import numpy as np
import pytest
from galerkin.mesh3d import Mesh3D,box_mesh
from sipi import extract_partitioned_capacitance_3d
from sipi.capacitance3d import extract_capacitance_3d,Capacitance3D
from sipi.constants import epsilon_0
import sipi.capacitance3d as module
from crosscheck import Stopwatch,emit,make_record,observable,require_tool

def geometry(n=2,network=False,layered=False):
    # Separate bounded dielectric boxes; names alias the same prescribed electrode.
    specs=[('ground','a',.4e-3,3.8)]
    if network:specs += [('a','b',.25e-3,2.2)]
    specs += [('b' if network else 'a',None,.3e-3,1.),(None,'ground',.2e-3,1.4)]
    nodes=[];tets=[];permittivity=[];electrodes={'ground':[],'a':[]}
    if network:electrodes['b']=[]
    boxes=[];offset=0
    for index,(bottom,top,height,eps) in enumerate(specs):
        mesh=box_mesh(1e-3,.8e-3,height,n,n,n)
        localz=mesh.nodes[:,2].copy();mesh.nodes[:,0]+=index*2e-3
        for name,face in [(bottom,'z0'),(top,'z1')]:
            if name is not None:electrodes[name].extend((offset+mesh.boundary[face]).tolist())
        is_layered=layered and index==0
        centres=localz[mesh.tets].mean(axis=1)
        relative=np.where(centres<height/2,2.1,4.7) if is_layered else np.full(mesh.num_tets,eps)
        permittivity.extend(relative);nodes.extend(mesh.nodes);tets.extend(mesh.tets+offset)
        boxes.append(dict(start=offset,end=offset+mesh.num_nodes,xmin=index*2e-3,
                          xmax=index*2e-3+1e-3,height=height,eps=eps,layered=is_layered,bottom=bottom,top=top))
        offset+=mesh.num_nodes
    mesh=Mesh3D(np.array(nodes),np.array(tets))
    bc=dict(eps_r=np.array(permittivity),conductors={k:np.array(v) for k,v in electrodes.items() if k!='ground'},ground=np.array(electrodes['ground']))
    c1=epsilon_0*1e-3*.8e-3/(.2e-3/2.1+.2e-3/4.7) if layered else epsilon_0*3.8*1e-3*.8e-3/.4e-3
    c2=epsilon_0*2.2*1e-3*.8e-3/.25e-3
    expected=np.array([[c1+c2,-c2],[-c2,c2]]) if network else np.array([[c1]])
    return mesh,bc,boxes,expected


@pytest.mark.parametrize('network,layered,n',[(False,False,n) for n in [2,3,4]]+
 [(True,False,n) for n in [2,3,4]]+[(True,True,n) for n in [2,4,6]])
def test_analytic_capacitor_network_and_constant_inactive_domains(network,layered,n):
    mesh,bc,boxes,expected=geometry(n,network,layered)
    out=extract_partitioned_capacitance_3d(mesh,**bc);norm=np.max(abs(expected))
    assert type(out) is Capacitance3D and out.names==tuple(bc['conductors'])
    assert np.max(abs(out.C-expected))/norm<1e-11
    assert np.max(abs(out.energy_C-expected))/norm<1e-11
    ground=np.array([-expected[0].sum(),0.]) if network else -expected[0]
    assert np.max(abs(out.ground_charge-ground))/norm<1e-11
    for box in boxes[-2:]:
        name=box['bottom'] or box['top'];target=np.zeros(len(out.names))
        if name!='ground':target[out.names.index(name)]=1.
        assert np.max(abs(out.potentials[box['start']:box['end']]-target))<1e-10


@pytest.mark.parametrize('case',[(False,False),(True,False),(True,True)])
def test_independent_piecewise_weak_form(case):
    skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
    network,layered=case;mesh,bc,boxes,_=geometry(4 if layered else 3,network,layered)
    clock=Stopwatch()
    with clock('openphysics'):out=extract_partitioned_capacitance_3d(mesh,**bc)
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTet(mesh.nodes.T,mesh.tets.T),skfem.ElementTetP1())
        @skfem.BilinearForm
        def form(u,v,w):
            eps=np.zeros_like(w.x[0])
            for box in boxes:
                mask=(w.x[0]>=box['xmin'])&(w.x[0]<=box['xmax'])
                value=np.where(w.x[2]<box['height']/2,2.1,4.7) if box['layered'] else box['eps']
                eps=np.where(mask,value,eps)
            return epsilon_0*eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis);fixed=np.concatenate([bc['ground'],*bc['conductors'].values()])
        potential=np.zeros_like(out.potentials)
        for col,nodes in enumerate(bc['conductors'].values()):
            v=np.zeros(basis.N);v[nodes]=1.
            potential[:,col]=skfem.solve(*skfem.condense(k,np.zeros(basis.N),x=v,D=fixed))
        charge=k@potential;c=np.array([charge[v].sum(axis=0) for v in bc['conductors'].values()])
        energy=potential.T@charge;ground=charge[bc['ground']].sum(axis=0);norm=np.max(abs(c))
    error=max(float(np.max(abs(c-out.C))/norm),float(np.max(abs(energy-out.energy_C))/norm),
              float(np.max(abs(ground-out.ground_charge))/norm),float(np.max(abs(potential-out.potentials))))
    record=make_record(case=f'sipi-partitioned-capacitance-{network}-{layered}',physics='bounded static partitioned dielectric domains with prescribed electrodes',
        api='extract_partitioned_capacitance_3d',discretization='shared tetrahedra/P1 with explicit per-tet material and global electrode aliases',
        tool='scikit-fem',tool_discretization='independent coordinate-defined piecewise weak form and Dirichlet solution',
        matched=['explicit mesh','dielectric regions','all prescribed electrode nodes and voltages','insulating exterior'],
        not_matched=['assembly and linear solution','common mesh is not independent meshing'],
        observables=[observable('C,energy,ground,potential','1','max_normalized_error',error,1e-10)],
        analytical_acceptance='Nine plate/network mesh limits1e-11, constant inactive potentials1e-10, scale/permutation1e-10; not an open-space or wave model.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10


@pytest.mark.parametrize('factor',[.5,2.])
def test_length_and_permittivity_scaling(factor):
    mesh,bc,_,_=geometry(3,True);base=extract_partitioned_capacitance_3d(mesh,**bc)
    for other,args in [(Mesh3D(mesh.nodes*factor,mesh.tets),bc),(mesh,dict(bc,eps_r=bc['eps_r']*factor))]:
        out=extract_partitioned_capacitance_3d(other,**args)
        assert np.max(abs(out.C/factor-base.C))/np.max(abs(base.C))<1e-10
        np.testing.assert_allclose(out.potentials,base.potentials,rtol=0,atol=1e-10)


def test_electrode_order_and_mesh_component_numbering_do_not_change_fields():
    mesh,bc,_,_=geometry(3,True);base=extract_partitioned_capacitance_3d(mesh,**bc)
    reverse=extract_partitioned_capacitance_3d(mesh,**dict(bc,conductors=dict(reversed(list(bc['conductors'].items())))))
    np.testing.assert_allclose(reverse.C,base.C[::-1,::-1],rtol=1e-10,atol=0)
    order=np.random.default_rng(2026).permutation(len(mesh.nodes));inverse=np.empty_like(order);inverse[order]=np.arange(len(order))
    shuffled=Mesh3D(mesh.nodes[order],inverse[mesh.tets[::-1]])
    args=dict(eps_r=bc['eps_r'][::-1],conductors={k:inverse[v] for k,v in bc['conductors'].items()},ground=inverse[bc['ground']])
    result=extract_partitioned_capacitance_3d(shuffled,**args)
    assert np.max(abs(result.C-base.C))/np.max(abs(base.C))<1e-10
    np.testing.assert_allclose(result.potentials[inverse],base.potentials,rtol=0,atol=1e-10)


@pytest.mark.parametrize('n',[2,3,4])
@pytest.mark.parametrize('eps',[1.,3.8])
@pytest.mark.parametrize('signals',[1,2])
@pytest.mark.parametrize('material',['scalar','array'])
def test_legacy_grounded_contract_has_exact_output_parity(n,eps,signals,material):
    mesh=box_mesh(.001,.0008,.0004,n,n,n);electrodes={'top':mesh.boundary['z1']}
    if signals==2:
        iz=np.rint(mesh.nodes[:,2]/.0004*n).astype(int);electrodes['middle']=np.flatnonzero(iz==n//2)
    args=dict(eps_r=eps if material=='scalar' else np.full(mesh.num_tets,eps),conductors=electrodes,ground=mesh.boundary['z0'])
    old=extract_capacitance_3d(mesh,**args);new=extract_partitioned_capacitance_3d(mesh,**args)
    for name in old.__dataclass_fields__:
        left=getattr(old,name);right=getattr(new,name)
        if isinstance(left,np.ndarray):np.testing.assert_array_equal(left,right)
        else:assert left==right


def forbidden(*args,**kwargs):pytest.fail('invalid inputs reached assembly')


@pytest.mark.parametrize('failure',['unanchored','floating-electrode','floating-pair'])
def test_component_and_global_reference_checks_precede_assembly(failure,monkeypatch):
    mesh,bc,boxes,_=geometry(2,network=failure=='floating-pair')
    if failure=='unanchored':bc['ground']=bc['ground'][bc['ground']<boxes[-1]['start']]
    elif failure=='floating-electrode':
        start=boxes[-2]['start'];end=boxes[-2]['end'];a=bc['conductors']['a']
        bc['conductors']={'a':a[(a<start)|(a>=end)],'floating':a[(a>=start)&(a<end)]}
    else:
        start=boxes[1]['start'];a=bc['conductors']['a']
        bc['conductors']={'a':a[a<start],'floating-c':a[a>=start],'floating-d':bc['conductors']['b']}
    monkeypatch.setattr(module,'assemble_stiffness_3d',forbidden)
    with pytest.raises(ValueError,match='prescribed electrode|connect every signal to ground'):
        extract_partitioned_capacitance_3d(mesh,**bc)


def test_original_api_and_saved_input_keep_component_ground_requirement(monkeypatch):
    from sipi.capacitance3d_document import Capacitance3DDocument
    mesh,bc,_,_=geometry(2)
    monkeypatch.setattr(module,'assemble_stiffness_3d',forbidden)
    with pytest.raises(ValueError,match='component'):extract_capacitance_3d(mesh,**bc)
    with pytest.raises(ValueError,match='component'):
        Capacitance3DDocument(mesh=mesh,**bc)


@pytest.mark.parametrize('bad',[0.,-1.,np.nan,np.inf,True,1+0j,[1.],[[1.]],'1'])
def test_original_material_contract_is_preserved(bad,monkeypatch):
    mesh,bc,_,_=geometry(2);bc['eps_r']=bad;monkeypatch.setattr(module,'assemble_stiffness_3d',forbidden)
    with pytest.raises(ValueError):extract_partitioned_capacitance_3d(mesh,**bc)


@pytest.mark.parametrize('bad',['empty-ground','empty-signals','empty-name','overlap','duplicate','outside','noninteger','unused-node'])
def test_original_node_and_electrode_contracts_are_preserved(bad,monkeypatch):
    mesh,bc,_,_=geometry(2)
    if bad=='empty-ground':bc['ground']=[]
    elif bad=='empty-signals':bc['conductors']={}
    elif bad=='empty-name':bc['conductors']={' ':bc['conductors']['a']}
    elif bad=='overlap':bc['conductors']['a']=bc['ground']
    elif bad=='duplicate':bc['conductors']['a']=np.array([1,1])
    elif bad=='outside':bc['conductors']['a']=np.array([len(mesh.nodes)])
    elif bad=='noninteger':bc['conductors']['a']=np.array([1.])
    else:mesh=Mesh3D(np.vstack([mesh.nodes,[1.,1.,1.]]),mesh.tets)
    monkeypatch.setattr(module,'assemble_stiffness_3d',forbidden)
    with pytest.raises(ValueError):extract_partitioned_capacitance_3d(mesh,**bc)


def test_results_are_detached_readonly_and_input_arrays_unchanged():
    mesh,bc,_,_=geometry(2,True);oldnodes=mesh.nodes.copy();oldeps=bc['eps_r'].copy()
    out=extract_partitioned_capacitance_3d(mesh,**bc)
    np.testing.assert_array_equal(mesh.nodes,oldnodes);np.testing.assert_array_equal(bc['eps_r'],oldeps)
    original=out.C.copy();mesh.nodes[:]=0;bc['eps_r'][:]=9;np.testing.assert_array_equal(out.C,original)
    for name in ['C','energy_C','ground_charge','potentials']:assert not getattr(out,name).flags.writeable


@pytest.mark.parametrize('failure',['nonfinite','solve','raw-gate'])
def test_original_operator_solver_and_raw_gates_remain_effective(failure,monkeypatch):
    mesh,bc,_,_=geometry(2)
    if failure=='nonfinite':
        original=module.assemble_stiffness_3d
        def corrupt(*a,**kw):
            k=original(*a,**kw);k.data[0]=np.nan;return k
        monkeypatch.setattr(module,'assemble_stiffness_3d',corrupt)
    elif failure=='solve':
        def fail(*a,**kw):raise RuntimeError('deliberate partitioned solve failure')
        monkeypatch.setattr(module,'splu',fail)
    else:
        class Zero:
            def solve(self,value):return np.zeros_like(value)
        monkeypatch.setattr(module,'splu',lambda *a,**kw:Zero())
    with pytest.raises(ValueError):extract_partitioned_capacitance_3d(mesh,**bc)
