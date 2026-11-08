# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite signal and ground volumes, explicit surfaces and qualified refinement."""
from dataclasses import replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import asymmetric_volume_grid_pair_cell,extract_asymmetric_volume_grid_pair_capacitance,extract_partitioned_capacitance_3d
from sipi.constants import epsilon_0
import sipi.asymmetric_volume_grid_pair as module


def arguments(n=8,m=3,g=.5,w=.5,wr=.75,gap=.5,h=.5,a=1.,d=1.,t=.125,u=.125,p=1e-3,es=3.8,ea=1.,eb=1.,**changes):
    data=dict(pitch=p,grid_width=g*p,left_trace_width=w*p,right_trace_width=wr*p,trace_gap=gap*p,height=h*p,top_clearance=a*p,backside_depth=d*p,ground_thickness=t*p,trace_thickness=u*p,
        eps_substrate=es,eps_above=ea,eps_below=eb,transverse_periods=m,cells_per_pitch=n,
        cells_substrate=round(n*h),cells_above=round(n*a),cells_below=round(n*(d-t)),cells_grid=max(1,round(n*t)),cells_trace=max(1,round(n*u)));data.update(changes);return data










@pytest.mark.parametrize('case',['mesh','side','top','back'])
def test_independent_mesh_and_three_exterior_refinement_sequences(case):
    if case=='mesh':items=[arguments(n=n,a=.5,d=.5) for n in [8,16,24]];gate=.05
    elif case=='side':items=[arguments(m=m) for m in [3,5,7]];gate=.01
    elif case=='top':items=[arguments(m=5,a=a) for a in [.5,1.,2.]];gate=.01
    else:items=[arguments(m=5,d=d) for d in [.5,1.,2.]];gate=.001
    values=[extract_asymmetric_volume_grid_pair_capacitance(**a).field.C for a in items]
    changes=[np.linalg.norm(b-a)/np.linalg.norm(b) for a,b in zip(values,values[1:])]
    assert changes[-1]<changes[0] and changes[-1]<gate
    # Successive changes are not bounds on true physical error.


@pytest.mark.parametrize('factor',[.5,2.])
def test_length_and_all_region_permittivity_scaling(factor):
    a=arguments();base=extract_asymmetric_volume_grid_pair_capacitance(**a);geometry=dict(a);dielectric=dict(a)
    for key in ['pitch','grid_width','left_trace_width','right_trace_width','trace_gap','height','top_clearance','backside_depth','ground_thickness','trace_thickness']:geometry[key]*=factor
    for key in ['eps_substrate','eps_above','eps_below']:dielectric[key]*=factor
    for scaled in [geometry,dielectric]:
        out=extract_asymmetric_volume_grid_pair_capacitance(**scaled)
        assert np.linalg.norm(out.field.C-factor*base.field.C)/np.linalg.norm(factor*base.field.C)<1e-10
        np.testing.assert_allclose(out.field.potentials,base.field.potentials,atol=1e-12,rtol=1e-10)


@pytest.mark.parametrize('case',[0,1,2,3])
def test_independent_three_region_weak_form_charge_energy(case):
    skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
    cases=[arguments(),arguments(g=1.,h=.375,a=.75,d=1.25,t=.125,u=.125,es=4.2,ea=1.4,eb=2.1),
        arguments(p=.8e-3,g=.25,w=.25,wr=.5,gap=.75,h=.75,a=.5,d=.75,t=.25,u=.125,es=2.8,ea=1.1,eb=1.5),
        arguments(w=.75,wr=.5,h=.7,a=.6,d=1.3,es=3.7,ea=1.2,eb=2.3,cells_substrate=3,cells_above=5,cells_below=7,cells_grid=3,cells_trace=3)]
    a=cases[case];clock=Stopwatch()
    with clock('openphysics'):result=extract_asymmetric_volume_grid_pair_capacitance(**a)
    cell=result.cell;signals=[cell.left_nodes,cell.right_nodes]
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTet(cell.nodes.T,cell.tets.T),skfem.ElementTetP1())
        @skfem.BilinearForm
        def form(u,v,w):
            eps=np.where(w.x[2]<0,a['eps_below'],np.where(w.x[2]>a['height'],a['eps_above'],a['eps_substrate']))
            return epsilon_0*eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis);potential=np.zeros((basis.N,2));boundary=np.r_[cell.ground_nodes,*signals]
        for col,signal in enumerate(signals):
            initial=np.zeros(basis.N);initial[signal]=1.
            potential[:,col]=skfem.solve(*skfem.condense(k,np.zeros(basis.N),x=initial,D=boundary))
        charge=k@potential;capacitance=np.array([charge[x].sum(axis=0) for x in signals]);energy=potential.T@k@potential;ground=charge[cell.ground_nodes].sum(axis=0)
    error=max(np.linalg.norm(x-y)/np.linalg.norm(y) for x,y in [(result.field.C,capacitance),(result.field.energy_C,energy),(result.field.ground_charge,ground),(result.field.potentials,potential)])
    record=make_record(case=f'sipi-volume-grid-pair-independent-{case}',physics='bounded static paired finite trace and ground-grid volumes with three dielectric regions',
        api='extract_asymmetric_volume_grid_pair_capacitance',discretization='shared tetrahedra/P1 after PEC-volume removal and integer-layer dielectric assignment',
        tool='scikit-fem',tool_discretization='independent coordinate-defined weak form and two Dirichlet solutions',
        matched=['explicit mesh','three dielectric regions','electrode nodes and basis voltages','insulating exterior'],
        not_matched=['assembly and linear solution','common mesh is not independent meshing'],
        observables=[observable('Maxwell C,energy C,ground charge,potential','1','max_relative',error,1e-10)],
        analytical_acceptance='Length/epsilon scaling, port permutation, SPD/Maxwell signs and quadratic energy; separate mesh/side/top/back refinement. No imposed mirror symmetry or line model.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10
    for v in [np.ones(2),np.array([1.,-1.]),np.array([.3,-.7])]:
        phi=potential@v
        assert abs(float(phi@k@phi)/(v@result.field.C@v)-1)<1e-10






    # Preserve absolute top h+p and the common p/128 grid; do not mix remeshing effects.








def test_readonly_detached_geometry_material_field_and_compact_units():
    r=extract_asymmetric_volume_grid_pair_capacitance(**arguments(n=4,wr=1.));c=r.cell;original=c.to_dict(include_mesh=True)
    assert len(c.inputs)==20
    for name in ['nodes','tets','left_nodes','right_nodes','ground_nodes','relative_permittivity']:
        value=getattr(c,name);assert not value.flags.writeable
        changed=value.copy();other=replace(c,**{name:changed});changed[:]=0;np.testing.assert_array_equal(getattr(other,name),value)
    mesh=c.to_mesh();mesh.nodes[:]=0;mesh.tets[:]=0;assert c.to_dict(include_mesh=True)==original
    snapshot=c.inputs;snapshot['eps_substrate']=9;assert c.inputs['eps_substrate']==3.8
    out=r.to_dict();assert not out['fields_included'] and not out['cell']['mesh_included']
    np.testing.assert_array_equal(out['capacitance_matrix_f'],r.field.C)
    np.testing.assert_array_equal(out['energy_capacitance_matrix_f'],r.field.energy_C)
    np.testing.assert_array_equal(out['ground_charge_c_per_basis'],r.field.ground_charge)
    snapshot=r.capacitance_matrix_f;snapshot[:]=0;assert np.all(np.diag(r.field.C)>0)
    expanded=r.to_dict(include_fields=True);json.dumps(expanded,allow_nan=False)
    assert len(expanded['potential_v_per_basis'])==len(c.nodes) and len(expanded['cell']['relative_permittivity'])==len(c.tets)
    for value in [r.field.C,r.field.energy_C,r.field.ground_charge,r.field.potentials]:assert not value.flags.writeable
    with pytest.raises(ValueError):r.to_dict(include_fields=1)
    with pytest.raises(ValueError):c.to_dict(include_mesh=1)


@pytest.mark.parametrize('name',['pitch','grid_width','left_trace_width','right_trace_width','trace_gap','height','top_clearance','backside_depth','ground_thickness','trace_thickness','eps_substrate','eps_above','eps_below'])
@pytest.mark.parametrize('bad',[0.,-1.,float('inf'),float('nan'),True,1+0j,[1.]])
def test_strict_positive_scalar_inputs_before_mesh(name,bad,monkeypatch):
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid scalar allocated mesh'));a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):asymmetric_volume_grid_pair_cell(**a)


@pytest.mark.parametrize('name,bad',[
 ('transverse_periods',0),('transverse_periods',2),('transverse_periods',11),('transverse_periods',1.),('transverse_periods',True),
 ('cells_per_pitch',3),('cells_per_pitch',5),('cells_per_pitch',34),('cells_per_pitch',8.),('cells_per_pitch',True),
 ('cells_substrate',0),('cells_substrate',129),('cells_substrate',4.),('cells_substrate',False),
 ('cells_above',0),('cells_above',129),('cells_above',4.),('cells_below',0),('cells_below',129),('cells_below',True),('cells_grid',0),('cells_grid',129),('cells_grid',2.),('cells_grid',True),('cells_trace',0),('cells_trace',129),('cells_trace',2.),('cells_trace',False)])
def test_explicit_counts_before_mesh(name,bad,monkeypatch):
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid counts allocated mesh'));a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):asymmetric_volume_grid_pair_cell(**a)


@pytest.mark.parametrize('case',['grid-over','trace-over','right-over','grid-off','trace-off','right-off','right-small','gap-off','gap-over','gap-small','grid-small','trace-small','node-budget','tet-budget','small-volume','large-volume','lost-top','thickness-equal','thickness-over','lost-trace-top'])
def test_geometry_alignment_scale_and_budget_before_mesh(case,monkeypatch):
    a=arguments()
    if case=='grid-over':a['grid_width']=2*a['pitch']
    elif case=='trace-over':a['left_trace_width']=2*a['pitch']
    elif case=='right-over':a['right_trace_width']=2*a['pitch']
    elif case=='right-off':a['right_trace_width']=.3*a['pitch']
    elif case=='right-small':a['right_trace_width']=1e-20*a['pitch']
    elif case=='grid-off':a['grid_width']=.3*a['pitch']
    elif case=='trace-off':a['left_trace_width']=.3*a['pitch']
    elif case=='gap-off':a['trace_gap']=.3*a['pitch']
    elif case=='gap-over':a['trace_gap']=3*a['pitch']
    elif case=='gap-small':a['trace_gap']=1e-20*a['pitch']
    elif case=='grid-small':a['grid_width']=1e-20*a['pitch']
    elif case=='trace-small':a['left_trace_width']=1e-20*a['pitch']
    elif case=='node-budget':a.update(transverse_periods=9,cells_per_pitch=32,cells_substrate=64,cells_above=64,cells_below=64)
    elif case=='tet-budget':a.update(transverse_periods=3,cells_per_pitch=32,cells_substrate=4,cells_above=12,cells_below=12)
    elif case=='thickness-equal':a['ground_thickness']=a['backside_depth']
    elif case=='thickness-over':a['ground_thickness']=2*a['backside_depth']
    elif case=='lost-trace-top':a['trace_thickness']=1e-300
    elif case=='lost-top':a['top_clearance']=1e-300
    else:
        factor=1e-150 if case=='small-volume' else 1e150
        for key in ['pitch','grid_width','left_trace_width','right_trace_width','trace_gap','height','top_clearance','backside_depth','ground_thickness','trace_thickness']:a[key]*=factor
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid geometry allocated mesh'))
    with pytest.raises(ValueError):asymmetric_volume_grid_pair_cell(**a)


def test_geometry_does_not_solve_a_field(monkeypatch):
    monkeypatch.setattr(module,'extract_partitioned_capacitance_3d',lambda *a,**k:pytest.fail('geometry solved field'))
    assert asymmetric_volume_grid_pair_cell(**arguments()).relative_permittivity.ndim==1


@pytest.mark.parametrize('bad',['type','names','tets','C','energy_C','ground_charge','potentials','nonfinite','negative-energy','positive-ground','boundary','diagnostics'])
def test_field_identity_finiteness_and_boundaries(bad,monkeypatch):
    a=arguments(n=4,wr=1.);r=extract_asymmetric_volume_grid_pair_capacitance(**a);f=r.field
    if bad=='type':changed=None
    elif bad=='names':changed=replace(f,names=('other',))
    elif bad=='tets':changed=replace(f,num_tets=f.num_tets+1)
    elif bad in ['C','energy_C','ground_charge','potentials']:changed=replace(f,**{bad:np.zeros((1,1))})
    elif bad=='nonfinite':changed=replace(f,C=np.full((2,2),np.nan))
    elif bad=='negative-energy':changed=replace(f,energy_C=-f.energy_C)
    elif bad=='positive-ground':changed=replace(f,ground_charge=-f.ground_charge)
    elif bad=='diagnostics':changed=replace(f,energy_charge_relative=float('nan'))
    else:
        potential=f.potentials.copy();potential[r.cell.left_nodes,0]=0;changed=replace(f,potentials=potential)
    monkeypatch.setattr(module,'extract_partitioned_capacitance_3d',lambda *a,**kw:changed)
    with pytest.raises(ValueError,match='field solve changed'):extract_asymmetric_volume_grid_pair_capacitance(**a)


def test_original_field_failure_is_retained(monkeypatch):
    def fail(*a,**kw):raise RuntimeError('deliberate strip-grid field failure')
    monkeypatch.setattr(module,'extract_partitioned_capacitance_3d',fail)
    with pytest.raises(RuntimeError,match='deliberate'):extract_asymmetric_volume_grid_pair_capacitance(**arguments())





def test_electrode_order_permutation_and_unmodified_raw_matrix():
    r=extract_asymmetric_volume_grid_pair_capacitance(**arguments());c=r.cell
    other=extract_partitioned_capacitance_3d(c.to_mesh(),eps_r=c.relative_permittivity,
        conductors={'right':c.right_nodes,'left':c.left_nodes},ground=c.ground_nodes)
    np.testing.assert_array_equal(other.C,r.field.C[::-1,::-1])
    np.testing.assert_array_equal(other.potentials,r.field.potentials[:,::-1])
    assert np.min(np.linalg.eigvalsh(r.field.C))>0 and r.field.C[0,1]<0 and np.all(r.field.ground_charge<0)
    assert r.field.names==('left','right')
    # Unequal traces retain the raw, asymmetric self-capacitances.
    assert r.field.C[0,0]!=r.field.C[1,1]


def test_solid_ground_screens_backside_material_and_depth():
    base=extract_asymmetric_volume_grid_pair_capacitance(**arguments(g=1.))
    changed=extract_asymmetric_volume_grid_pair_capacitance(**arguments(g=1.,d=2.,eb=4.2))
    np.testing.assert_allclose(base.field.C,changed.field.C,rtol=1e-10,atol=0.)
    below=changed.cell.nodes[:,2]<-changed.inputs['ground_thickness_m']
    assert np.all(changed.field.potentials[below]==0.)


@pytest.mark.parametrize('n,m,g,w,wr,gap',[(4,3,.5,.5,1.,.5),(8,3,.5,.5,.75,.5),(8,1,1.,.25,.25,.5),(8,3,.25,1.25,.25,.5),(8,3,.25,.25,1.25,.5)])
def test_independent_width_surfaces_counts_material_volumes_and_wall_contact(n,m,g,w,wr,gap):
    a=arguments(n=n,m=m,g=g,w=w,wr=wr,gap=gap,es=4.2,ea=1.3,eb=2.1,cells_substrate=3,cells_above=5,cells_below=7,cells_grid=3,cells_trace=3)
    c=asymmetric_volume_grid_pair_cell(**a);mesh=c.to_mesh();mesh.check();x,y,z=c.nodes.T;p=a['pitch'];ge=c.grid_edge_cells;tl=c.left_trace_edge_cells;tr=c.right_trace_edge_cells;ce=c.gap_edge_cells;ny=m*n
    nz=15+a['cells_grid']+a['cells_trace'];xy=(n+1)*(ny+1)
    open_nodes=m*(n-2*ge+1)**2 if ge<n//2 else 0
    touches=[ce+2*t==ny//2 for t in [tl,tr]]
    interior=sum((n+1)*(2*t-1+int(wall)) for t,wall in zip([tl,tr],touches))
    removed_nodes=(a['cells_grid']-1)*(xy-open_nodes)+(a['cells_trace']-1)*interior
    removed_tets=6*(n*ny-m*(n-2*ge)**2)*a['cells_grid']+6*n*(2*tl+2*tr)*a['cells_trace']
    assert c.uncut_num_nodes==xy*(nz+1) and c.uncut_num_tets==6*n*ny*nz
    assert len(c.nodes)==c.uncut_num_nodes-removed_nodes and len(c.tets)==c.uncut_num_tets-removed_tets
    tol=1e-12*p;mid=m*p/2;half=c.resolved_trace_gap/2
    slab=(z>=a['height'])&(z<=a['height']+a['trace_thickness'])
    for signal,lo,hi,te,wall in [(c.left_nodes,mid-half-w*p,mid-half,tl,touches[0]),(c.right_nodes,mid+half,mid+half+wr*p,tr,touches[1])]:
        np.testing.assert_array_equal(signal,np.flatnonzero(slab&(y>=lo-tol)&(y<=hi+tol)))
        assert len(signal)==2*(n+1)*(2*te+1)+(a['cells_trace']-1)*(1 if wall else 2)*(n+1)
        assert not np.intersect1d(signal,c.ground_nodes).size
    grid=(np.minimum(x,p-x)<=c.resolved_grid_width/2+tol)|(np.min(abs(y[:,None]-p*np.arange(m+1)),axis=1)<=c.resolved_grid_width/2+tol)
    np.testing.assert_array_equal(c.ground_nodes,np.flatnonzero((z>=-a['ground_thickness'])&(z<=0)&grid))
    assert not np.intersect1d(c.left_nodes,c.right_nodes).size
    np.testing.assert_array_equal(np.unique(c.tets),np.arange(len(c.nodes)))
    volumes=mesh.volumes();centres=c.nodes[c.tets].mean(axis=1)[:,2]
    below=centres<0;above=centres>a['height'];substrate=~(below|above)
    for mask,eps,depth in [(below,a['eps_below'],a['backside_depth']),(substrate,a['eps_substrate'],a['height']),(above,a['eps_above'],a['trace_thickness']+a['top_clearance'])]:
        assert np.all(c.relative_permittivity[mask]==eps)
        expected=p*p*m*depth-(c.ground_metal_volume if mask is below else c.trace_metal_volume if mask is above else 0.)
        assert abs(volumes[mask].sum()/expected-1)<1e-12
    assert abs(c.trace_metal_volume/(p*p*(w+wr)*a['trace_thickness'])-1)<1e-12
    assert abs(volumes.sum()/c.dielectric_volume-1)<1e-12
    assert np.all(volumes>0) and c.mesh_volume_relative_error<1e-12 and not mesh.tagged_faces
    faces=np.sort(np.concatenate([c.tets[:,ix] for ix in [[0,1,2],[0,1,3],[0,2,3],[1,2,3]]]),axis=1)
    faces,count=np.unique(faces,axis=0,return_counts=True);surface=np.unique(faces[count==1])
    assert np.all(np.isin(np.r_[c.left_nodes,c.right_nodes,c.ground_nodes],surface))


def test_roundoff_only_alignment_preserves_independent_requested_and_resolved_widths():
    a=arguments();a['left_trace_width']*=1-2e-13;a['right_trace_width']*=1+2e-13;a['trace_gap']*=1+2e-13
    c=asymmetric_volume_grid_pair_cell(**a)
    assert c.inputs['left_trace_width_m']==a['left_trace_width'] and c.inputs['right_trace_width_m']==a['right_trace_width']
    assert c.resolved_left_trace_width==.5e-3 and c.resolved_right_trace_width==.75e-3 and c.resolved_trace_gap==.5e-3
    assert c.resolved_left_trace_width!=a['left_trace_width'] and c.resolved_right_trace_width!=a['right_trace_width']


@pytest.mark.parametrize('case',[0,1,2])
def test_equal_width_limit_preserves_original_mesh_and_full_field_exactly(case):
    from sipi import extract_volume_grid_pair_capacitance
    cases=[arguments(n=4,w=.5,wr=.5),arguments(w=.25,wr=.25,g=.25),arguments(w=.75,wr=.75,es=4.2,ea=1.3,eb=2.1)]
    a=cases[case];new=extract_asymmetric_volume_grid_pair_capacitance(**a)
    old=dict(a);old['trace_width']=old.pop('left_trace_width');old.pop('right_trace_width');previous=extract_volume_grid_pair_capacitance(**old)
    for name in ['nodes','tets','left_nodes','right_nodes','ground_nodes','relative_permittivity']:
        np.testing.assert_array_equal(getattr(new.cell,name),getattr(previous.cell,name))
    for name in ['C','energy_C','ground_charge','potentials']:
        np.testing.assert_array_equal(getattr(new.field,name),getattr(previous.field,name))
