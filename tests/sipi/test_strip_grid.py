# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Three-region bounded strip/grid geometry, independent fields and refinement."""
from dataclasses import replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import strip_grid_cell,extract_strip_grid_capacitance,extract_grid_plate_capacitance
from sipi.constants import epsilon_0
import sipi.strip_grid as module


def arguments(n=8,m=1,g=.5,w=.5,h=.5,a=1.,d=1.,p=1e-3,es=3.8,ea=1.,eb=1.,**changes):
    data=dict(pitch=p,grid_width=g*p,trace_width=w*p,height=h*p,top_clearance=a*p,backside_depth=d*p,
        eps_substrate=es,eps_above=ea,eps_below=eb,transverse_periods=m,cells_per_pitch=n,
        cells_substrate=round(n*h),cells_above=round(n*a),cells_below=round(n*d));data.update(changes);return data


@pytest.mark.parametrize('m,h,es,ea,eb',[(1,.25,3.8,1.,2.),(3,.5,4.2,1.3,2.1),(1,1.,2.2,5.,.7)])
def test_solid_full_width_plate_analytic_limit(m,h,es,ea,eb):
    a=arguments(m=m,g=1.,w=float(m),h=h,es=es,ea=ea,eb=eb);r=extract_strip_grid_capacitance(**a)
    exact=epsilon_0*es*a['pitch']**2*m/a['height']
    assert abs(r.capacitance_f/exact-1)<1e-11 and abs(r.field.ground_charge[0]/(-exact)-1)<1e-11


@pytest.mark.parametrize('parameter',['g','w'])
def test_nested_grid_and_trace_width_monotonicity(parameter):
    caps=[extract_strip_grid_capacitance(**arguments(**{parameter:v})).capacitance_f for v in [.25,.5,.75,1.]]
    assert np.all(np.diff(caps)>0)
    # Each sequence adds electrode nodes on an otherwise unchanged mesh.
    assert max(caps)==caps[-1]


@pytest.mark.parametrize('case',['mesh','side','top','back'])
def test_independent_mesh_and_three_exterior_refinement_sequences(case):
    if case=='mesh':items=[arguments(n=n) for n in [8,16,24]];gate=.03
    elif case=='side':items=[arguments(m=m) for m in [3,5,7]];gate=.01
    elif case=='top':items=[arguments(m=5,a=a) for a in [.5,1.,2.]];gate=.01
    else:items=[arguments(m=5,d=d) for d in [.5,1.,2.]];gate=.001
    values=[extract_strip_grid_capacitance(**a).capacitance_f for a in items]
    changes=[abs(b-a)/b for a,b in zip(values,values[1:])]
    assert changes[-1]<changes[0] and changes[-1]<gate
    # Successive changes are not bounds on true physical error.


@pytest.mark.parametrize('factor',[.5,2.])
def test_length_and_all_region_permittivity_scaling(factor):
    a=arguments();base=extract_strip_grid_capacitance(**a);geometry=dict(a);dielectric=dict(a)
    for key in ['pitch','grid_width','trace_width','height','top_clearance','backside_depth']:geometry[key]*=factor
    for key in ['eps_substrate','eps_above','eps_below']:dielectric[key]*=factor
    for scaled in [geometry,dielectric]:
        out=extract_strip_grid_capacitance(**scaled)
        assert abs(out.capacitance_f/(factor*base.capacitance_f)-1)<1e-10
        np.testing.assert_allclose(out.field.potentials,base.field.potentials,atol=1e-12,rtol=1e-10)


@pytest.mark.parametrize('case',[0,1,2,3])
def test_independent_three_region_weak_form_charge_energy(case):
    skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
    cases=[arguments(),arguments(m=3,h=.375,a=.75,d=1.25,es=4.2,ea=1.4,eb=2.1),
        arguments(p=.8e-3,g=.25,w=.75,h=.75,a=.5,d=.75,es=2.8,ea=1.1,eb=1.5),
        arguments(m=3,h=.7,a=.6,d=1.3,es=3.7,ea=1.2,eb=2.3,cells_substrate=3,cells_above=5,cells_below=7)]
    a=cases[case];clock=Stopwatch()
    with clock('openphysics'):result=extract_strip_grid_capacitance(**a)
    cell=result.cell
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTet(cell.nodes.T,cell.tets.T),skfem.ElementTetP1())
        @skfem.BilinearForm
        def form(u,v,w):
            eps=np.where(w.x[2]<0,a['eps_below'],np.where(w.x[2]>a['height'],a['eps_above'],a['eps_substrate']))
            return epsilon_0*eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis);initial=np.zeros(basis.N);initial[cell.trace_nodes]=1.
        potential=skfem.solve(*skfem.condense(k,np.zeros(basis.N),x=initial,D=np.r_[cell.ground_nodes,cell.trace_nodes]))
        charge=k@potential;capacitance=float(charge[cell.trace_nodes].sum());energy=float(potential@k@potential);ground=float(charge[cell.ground_nodes].sum())
    error=max(abs(result.capacitance_f/capacitance-1),abs(result.field.energy_C[0,0]/energy-1),abs(result.field.ground_charge[0]/ground-1))
    record=make_record(case=f'sipi-strip-grid-independent-{case}',physics='bounded static thin trace and grid with three dielectric regions',
        api='extract_strip_grid_capacitance',discretization='shared tetrahedra/P1 with integer-layer dielectric assignment',
        tool='scikit-fem',tool_discretization='independent coordinate-defined piecewise weak form and Dirichlet solution',
        matched=['explicit mesh','three dielectric regions','electrode nodes and voltages','insulating exterior'],
        not_matched=['assembly and linear solution','common mesh is not independent meshing'],
        observables=[observable('C,energy capacitance,ground charge','1','max_relative',error,1e-10)],
        analytical_acceptance='Solid/full-width plate1e-11, length/eps scaling1e-10 and separate mesh/side/top/back refinement; not a line or wave model.',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert error<1e-10


def test_full_width_homogeneous_bridge_to_existing_broad_plate():
    a=arguments(w=1.,es=3.8,ea=3.8,eb=3.8);r=extract_strip_grid_capacitance(**a)
    old=extract_grid_plate_capacitance(pitch=a['pitch'],width=a['grid_width'],height=a['height'],backside_depth=a['backside_depth'],eps_r=3.8,cells_xy=a['cells_per_pitch'],cells_above=a['cells_substrate'],cells_below=a['cells_below'])
    assert abs(r.capacitance_f/old.capacitance_f-1)<1e-10  # Replay, not independent FE evidence.


@pytest.mark.parametrize('n,m,g,w',[(4,1,.5,.5),(8,3,.25,.5),(8,5,.5,1.25),(8,3,1.,3.)])
def test_conforming_planes_counts_regions_volume_and_export(n,m,g,w):
    a=arguments(n=n,m=m,g=g,w=w,es=4.2,ea=1.3,eb=2.1,cells_substrate=3,cells_above=5,cells_below=7)
    cell=strip_grid_cell(**a);mesh=cell.to_mesh();mesh.check();x,y,z=cell.nodes.T;p=a['pitch'];ge=cell.grid_edge_cells;te=cell.trace_edge_cells
    assert len(cell.nodes)==(n+1)*(m*n+1)*16 and len(cell.tets)==6*n*(m*n)*15
    assert len(cell.trace_nodes)==(n+1)*(2*te+1)
    assert len(cell.ground_nodes)==(n+1)*(m*n+1)-m*max(n-2*ge-1,0)**2
    tolerance=1e-12*p
    nearest_grid_y=np.min(abs(y[:,None]-p*np.arange(m+1)),axis=1)
    grid=(np.minimum(x,p-x)<=cell.resolved_grid_width/2+tolerance)|(nearest_grid_y<=cell.resolved_grid_width/2+tolerance)
    expected_ground=np.flatnonzero((z==0)&grid)
    expected_trace=np.flatnonzero((z==a['height'])&(abs(y-m*p/2)<=cell.resolved_trace_width/2+tolerance))
    np.testing.assert_array_equal(cell.ground_nodes,expected_ground);np.testing.assert_array_equal(cell.trace_nodes,expected_trace)
    assert not np.intersect1d(cell.trace_nodes,cell.ground_nodes).size
    assert z.min()==-a['backside_depth'] and z.max()==a['height']+a['top_clearance']
    volumes=mesh.volumes();centres=cell.nodes[cell.tets].mean(axis=1)[:,2]
    below=centres<0;above=centres>a['height'];substrate=~(below|above)
    for mask,eps,depth in [(below,a['eps_below'],a['backside_depth']),(substrate,a['eps_substrate'],a['height']),(above,a['eps_above'],a['top_clearance'])]:
        assert np.all(cell.relative_permittivity[mask]==eps)
        assert abs(volumes[mask].sum()/(p*p*m*depth)-1)<1e-12
    assert np.all(volumes>0) and cell.mesh_volume_relative_error<1e-12 and not mesh.tagged_faces


def test_roundoff_only_alignment_keeps_both_requested_and_resolved_widths():
    a=arguments();a['grid_width']*=1+2e-13;a['trace_width']*=1-2e-13;c=strip_grid_cell(**a)
    assert c.inputs['grid_width_m']==a['grid_width'] and c.inputs['trace_width_m']==a['trace_width']
    assert c.resolved_grid_width!=a['grid_width'] and c.resolved_trace_width!=a['trace_width']
    assert c.resolved_grid_width==.5e-3 and c.resolved_trace_width==.5e-3


def test_readonly_detached_geometry_material_field_and_compact_units():
    r=extract_strip_grid_capacitance(**arguments(n=4));c=r.cell;original=c.to_dict(include_mesh=True)
    assert len(c.inputs)==14
    for name in ['nodes','tets','trace_nodes','ground_nodes','relative_permittivity']:
        value=getattr(c,name);assert not value.flags.writeable
        changed=value.copy();other=replace(c,**{name:changed});changed[:]=0;np.testing.assert_array_equal(getattr(other,name),value)
    mesh=c.to_mesh();mesh.nodes[:]=0;mesh.tets[:]=0;assert c.to_dict(include_mesh=True)==original
    snapshot=c.inputs;snapshot['eps_substrate']=9;assert c.inputs['eps_substrate']==3.8
    out=r.to_dict();assert not out['fields_included'] and not out['cell']['mesh_included']
    assert out['capacitance_f']==r.field.C[0,0] and out['stored_energy_j_at_one_volt']==.5*r.field.energy_C[0,0]
    assert out['ground_charge_c_at_one_volt']==r.field.ground_charge[0]<0
    expanded=r.to_dict(include_fields=True);json.dumps(expanded,allow_nan=False)
    assert len(expanded['potential_v_at_one_volt'])==len(c.nodes) and len(expanded['cell']['relative_permittivity'])==len(c.tets)
    for value in [r.field.C,r.field.energy_C,r.field.ground_charge,r.field.potentials]:assert not value.flags.writeable
    with pytest.raises(ValueError):r.to_dict(include_fields=1)
    with pytest.raises(ValueError):c.to_dict(include_mesh=1)


@pytest.mark.parametrize('name',['pitch','grid_width','trace_width','height','top_clearance','backside_depth','eps_substrate','eps_above','eps_below'])
@pytest.mark.parametrize('bad',[0.,-1.,float('inf'),float('nan'),True,1+0j,[1.]])
def test_strict_positive_scalar_inputs_before_mesh(name,bad,monkeypatch):
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid scalar allocated mesh'));a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):strip_grid_cell(**a)


@pytest.mark.parametrize('name,bad',[
 ('transverse_periods',0),('transverse_periods',2),('transverse_periods',11),('transverse_periods',1.),('transverse_periods',True),
 ('cells_per_pitch',3),('cells_per_pitch',5),('cells_per_pitch',34),('cells_per_pitch',8.),('cells_per_pitch',True),
 ('cells_substrate',0),('cells_substrate',129),('cells_substrate',4.),('cells_substrate',False),
 ('cells_above',0),('cells_above',129),('cells_above',4.),('cells_below',0),('cells_below',129),('cells_below',True)])
def test_explicit_counts_before_mesh(name,bad,monkeypatch):
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid counts allocated mesh'));a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):strip_grid_cell(**a)


@pytest.mark.parametrize('case',['grid-over','trace-over','grid-off','trace-off','grid-small','trace-small','node-budget','tet-budget','small-volume','large-volume','lost-top'])
def test_geometry_alignment_scale_and_budget_before_mesh(case,monkeypatch):
    a=arguments()
    if case=='grid-over':a['grid_width']=2*a['pitch']
    elif case=='trace-over':a['trace_width']=2*a['pitch']
    elif case=='grid-off':a['grid_width']=.3*a['pitch']
    elif case=='trace-off':a['trace_width']=.3*a['pitch']
    elif case=='grid-small':a['grid_width']=1e-20*a['pitch']
    elif case=='trace-small':a['trace_width']=1e-20*a['pitch']
    elif case=='node-budget':a.update(transverse_periods=9,cells_per_pitch=32,cells_substrate=64,cells_above=64,cells_below=64)
    elif case=='tet-budget':a.update(transverse_periods=3,cells_per_pitch=32,cells_substrate=4,cells_above=12,cells_below=12)
    elif case=='lost-top':a['top_clearance']=1e-300
    else:
        factor=1e-150 if case=='small-volume' else 1e150
        for key in ['pitch','grid_width','trace_width','height','top_clearance','backside_depth']:a[key]*=factor
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid geometry allocated mesh'))
    with pytest.raises(ValueError):strip_grid_cell(**a)


def test_geometry_does_not_solve_a_field(monkeypatch):
    monkeypatch.setattr(module,'extract_capacitance_3d',lambda *a,**k:pytest.fail('geometry solved field'))
    assert strip_grid_cell(**arguments()).relative_permittivity.ndim==1


@pytest.mark.parametrize('bad',['type','names','tets','C','energy_C','ground_charge','potentials','nonfinite','negative-energy','positive-ground','boundary','diagnostics'])
def test_field_identity_finiteness_and_boundaries(bad,monkeypatch):
    a=arguments(n=4);r=extract_strip_grid_capacitance(**a);f=r.field
    if bad=='type':changed=None
    elif bad=='names':changed=replace(f,names=('other',))
    elif bad=='tets':changed=replace(f,num_tets=f.num_tets+1)
    elif bad in ['C','energy_C','ground_charge','potentials']:changed=replace(f,**{bad:np.zeros((2,2))})
    elif bad=='nonfinite':changed=replace(f,C=np.array([[np.nan]]))
    elif bad=='negative-energy':changed=replace(f,energy_C=-f.energy_C)
    elif bad=='positive-ground':changed=replace(f,ground_charge=-f.ground_charge)
    elif bad=='diagnostics':changed=replace(f,energy_charge_relative=float('nan'))
    else:
        potential=f.potentials.copy();potential[r.cell.trace_nodes,0]=0;changed=replace(f,potentials=potential)
    monkeypatch.setattr(module,'extract_capacitance_3d',lambda *a,**kw:changed)
    with pytest.raises(ValueError,match='field solve changed'):extract_strip_grid_capacitance(**a)


def test_original_field_failure_is_retained(monkeypatch):
    def fail(*a,**kw):raise RuntimeError('deliberate strip-grid field failure')
    monkeypatch.setattr(module,'extract_capacitance_3d',fail)
    with pytest.raises(RuntimeError,match='deliberate'):extract_strip_grid_capacitance(**arguments())
