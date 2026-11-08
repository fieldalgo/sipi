# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded grid/plate capacitance: geometry, independent P1 and refinement."""
from dataclasses import replace
import importlib.metadata as metadata
import json
import numpy as np
import pytest
from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from sipi import grid_plate_cell,extract_grid_plate_capacitance
from sipi.constants import epsilon_0
import sipi.grid_plate as module


def arguments(n=8,width=.25,height=.5,depth=1.,pitch=1e-3,eps=3.8,**changes):
    data=dict(pitch=pitch,width=width*pitch,height=height*pitch,backside_depth=depth*pitch,
        eps_r=eps,cells_xy=n,cells_above=round(n*height),cells_below=round(n*depth))
    data.update(changes);return data


def record(clock,case,error):
    out=make_record(case=case,physics='bounded static thin-grid and broad-plate capacitance',
        api='sipi.extract_grid_plate_capacitance',discretization='shared conforming tetrahedra andP1electrostatics',
        tool='scikit-fem',tool_discretization='independent scalar weak-form assembly/Dirichlet solve on the same explicit mesh',
        matched=['same homogeneouseps,mesh,electrodenodes,1Vdrive andinsulatingotherfaces'],
        not_matched=['commonmesh is not independentmeshing;no lineRLGC,frequency,measurement or fullwave claim'],
        observables=[observable('cell C,energy capacitance,ground charge','relative','maximum relative difference',error,1e-10)],
        analytical_acceptance='solidplate eps0*eps*pitch²/height;geometry/permittivity scaling;mesh/backside refinement',stopwatch=clock)
    out['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(out)


@pytest.mark.parametrize('n',[8,16])
@pytest.mark.parametrize('height',[.25,.5,1.])
def test_solid_plate_analytic_limit(n,height):
    a=arguments(n,width=1.,height=height);r=extract_grid_plate_capacitance(**a)
    exact=epsilon_0*a['eps_r']*a['pitch']**2/a['height']
    assert abs(r.capacitance_f/exact-1)<=1e-11
    assert abs(r.field.ground_charge[0]/(-exact)-1)<=1e-11


def test_nested_ground_width_monotonicity_and_solid_upper_bound():
    caps=[extract_grid_plate_capacitance(**arguments(16,width=w)).capacitance_f for w in [.25,.5,.75,1.]]
    exact=epsilon_0*3.8*1e-6/.5e-3
    assert np.all(np.diff(caps)>0) and max(caps)<=exact*(1+1e-10)


def test_fixed_geometry_mesh_refinement_changes_decrease():
    values=[extract_grid_plate_capacitance(**arguments(n)).capacitance_f for n in [8,16,32]]
    changes=[abs(b-a)/b for a,b in zip(values,values[1:])]
    assert changes[1]<changes[0] and changes[1]<.015
    # This is successive-mesh change, not a bound on true physical error.


def test_backside_truncation_refinement_at_fixed_spacing():
    values=[extract_grid_plate_capacitance(**arguments(16,depth=d)).capacitance_f for d in [1.,2.]]
    assert abs(values[1]-values[0])/values[1]<1e-3


@pytest.mark.parametrize('case',[0,1,2,3])
def test_independent_scalar_weak_form_energy_and_charge(case):
    skfem=require_tool('scikit-fem');from skfem.helpers import dot,grad
    cases=[arguments(16),arguments(16,pitch=.8e-3,width=.5,height=.375,depth=1.25),
           arguments(8,pitch=1.2e-3,width=.75,height=1.,depth=.75),
           arguments(8,width=.5,height=.7,depth=1.3,cells_above=3,cells_below=5)]
    a=cases[case];clock=Stopwatch()
    with clock('openphysics'):result=extract_grid_plate_capacitance(**a)
    cell=result.cell
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTet(cell.nodes.T,cell.tets.T),skfem.ElementTetP1())
        @skfem.BilinearForm
        def form(u,v,w):return epsilon_0*a['eps_r']*dot(grad(u),grad(v))
        k=skfem.asm(form,basis);initial=np.zeros(basis.N);initial[cell.plate_nodes]=1.
        u=skfem.solve(*skfem.condense(k,np.zeros(basis.N),x=initial,D=np.r_[cell.ground_nodes,cell.plate_nodes]))
        charge=k@u;energy=float(u@k@u);plate=float(charge[cell.plate_nodes].sum());ground=float(charge[cell.ground_nodes].sum())
    error=max(abs(result.capacitance_f/plate-1),abs(result.field.energy_C[0,0]/energy-1),abs(result.field.ground_charge[0]/ground-1))
    record(clock,f'sipi-grid-plate-independent-{case}',error);assert error<=1e-10


@pytest.mark.parametrize('factor',[.5,2.])
def test_length_and_permittivity_scale_total_capacitance(factor):
    a=arguments();base=extract_grid_plate_capacitance(**a);scaled=dict(a)
    for name in ['pitch','width','height','backside_depth']:scaled[name]*=factor
    length=extract_grid_plate_capacitance(**scaled)
    assert abs(length.capacitance_f/(factor*base.capacitance_f)-1)<=1e-10
    a['eps_r']*=factor;dielectric=extract_grid_plate_capacitance(**a)
    assert abs(dielectric.capacitance_f/(factor*base.capacitance_f)-1)<=1e-10
    np.testing.assert_allclose(length.field.potentials,base.field.potentials,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(dielectric.field.potentials,base.field.potentials,rtol=1e-10,atol=1e-12)


@pytest.mark.parametrize('n,width',[(4,.5),(8,.25),(16,.375),(16,1.)])
def test_conforming_geometry_planes_volume_and_shared_mesh_export(n,width):
    a=arguments(n,width=width,cells_above=3,cells_below=5);c=grid_plate_cell(**a);mesh=c.to_mesh();mesh.check()
    assert len(c.nodes)==(n+1)**2*9 and len(c.tets)==6*n*n*8
    assert len(c.plate_nodes)==(n+1)**2 and not np.intersect1d(c.plate_nodes,c.ground_nodes).size
    x,y,z=c.nodes.T;w=c.resolved_width;p=a['pitch']
    expected=np.flatnonzero((z==0)&((x<=w/2)|(x>=p-w/2)|(y<=w/2)|(y>=p-w/2)))
    np.testing.assert_array_equal(expected,c.ground_nodes)
    assert np.all(z[c.plate_nodes]==a['height']) and np.all(z[c.ground_nodes]==0)
    assert z.min()==-a['backside_depth'] and z.max()==a['height']
    assert np.all(mesh.volumes()>0) and c.mesh_volume_relative_error<=1e-12
    assert abs(mesh.volumes().sum()/(p*p*(a['height']+a['backside_depth']))-1)<=1e-12
    if width<1:assert np.any((z==0)&~np.isin(np.arange(len(z)),c.ground_nodes))
    assert not mesh.tagged_faces


def test_roundoff_only_alignment_preserves_requested_and_resolved_width():
    a=arguments();a['width']*=1+2e-13;c=grid_plate_cell(**a)
    assert c.inputs['width_m']==a['width'] and c.resolved_width==.25e-3
    assert c.inputs['width_m']!=c.resolved_width
    a['width']=.3e-3
    with pytest.raises(ValueError,match='align'):grid_plate_cell(**a)


def test_detached_readonly_geometry_field_and_unit_serialization():
    r=extract_grid_plate_capacitance(**arguments());c=r.cell;original=c.to_dict(include_mesh=True)
    for name in ['nodes','tets','plate_nodes','ground_nodes']:
        value=getattr(c,name);assert not value.flags.writeable
        changed=value.copy();copy=replace(c,**{name:changed});changed[:]=0;np.testing.assert_array_equal(getattr(copy,name),value)
    mesh=c.to_mesh();mesh.nodes[:]=0;mesh.tets[:]=0;assert c.to_dict(include_mesh=True)==original
    inputs=c.inputs;inputs['pitch_m']=999;assert c.inputs['pitch_m']==1e-3
    out=r.to_dict();assert not out['fields_included'] and not out['cell']['mesh_included']
    assert out['capacitance_f']==r.field.C[0,0] and out['stored_energy_j_at_one_volt']==.5*r.field.energy_C[0,0]
    assert out['ground_charge_c_at_one_volt']==r.field.ground_charge[0]<0
    expanded=r.to_dict(include_fields=True);json.dumps(expanded,allow_nan=False)
    assert len(expanded['potential_v_at_one_volt'])==len(c.nodes)
    for array in [r.field.C,r.field.energy_C,r.field.potentials,r.field.ground_charge]:assert not array.flags.writeable
    with pytest.raises(ValueError):r.to_dict(include_fields=1)
    with pytest.raises(ValueError):c.to_dict(include_mesh=1)


@pytest.mark.parametrize('name',['pitch','width','height','backside_depth','eps_r'])
@pytest.mark.parametrize('bad',[0.,-1.,float('inf'),float('nan'),True,1+0j,[1.]])
def test_strict_positive_scalar_inputs_before_mesh_allocation(name,bad,monkeypatch):
    def fail(*args,**kwargs):pytest.fail('invalid input allocated a mesh')
    monkeypatch.setattr(module,'box_mesh',fail);a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):grid_plate_cell(**a)


@pytest.mark.parametrize('name,bad',[
    ('cells_xy',3),('cells_xy',5),('cells_xy',66),('cells_xy',8.),('cells_xy',True),
    ('cells_above',0),('cells_above',65),('cells_above',4.),('cells_above',False),
    ('cells_below',0),('cells_below',129),('cells_below',8.),('cells_below',True)])
def test_explicit_cell_counts_before_mesh_allocation(name,bad,monkeypatch):
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid counts allocated mesh'));a=arguments();a[name]=bad
    with pytest.raises((ValueError,TypeError)):grid_plate_cell(**a)


@pytest.mark.parametrize('case',['width-over-pitch','off-grid','unresolved','budget','small-volume','large-volume'])
def test_alignment_scale_and_budget_reject_before_allocation(case,monkeypatch):
    a=arguments()
    if case=='width-over-pitch':a['width']=2*a['pitch']
    elif case=='off-grid':a['width']=.3*a['pitch']
    elif case=='unresolved':a['width']=1e-20*a['pitch']
    elif case=='budget':a.update(cells_xy=64,cells_above=32,cells_below=64)
    else:
        scale=1e-150 if case=='small-volume' else 1e150
        for key in ['pitch','width','height','backside_depth']:a[key]*=scale
    monkeypatch.setattr(module,'box_mesh',lambda *a,**k:pytest.fail('invalid geometry allocated mesh'))
    with pytest.raises(ValueError):grid_plate_cell(**a)


def test_cell_preparation_does_not_assemble_or_solve(monkeypatch):
    monkeypatch.setattr(module,'extract_capacitance_3d',lambda *a,**k:pytest.fail('geometry preparation solved field'))
    assert grid_plate_cell(**arguments()).nodes.shape[1]==3


@pytest.mark.parametrize('bad',['type','names','tets','C','energy_C','ground_charge','potentials','nonfinite','negative','boundary','diagnostics'])
def test_extraction_result_identity_and_finiteness(bad,monkeypatch):
    a=arguments(4,width=.5);r=extract_grid_plate_capacitance(**a);f=r.field
    if bad=='type':changed=None
    elif bad=='names':changed=replace(f,names=('other',))
    elif bad=='tets':changed=replace(f,num_tets=f.num_tets+1)
    elif bad in ['C','energy_C','ground_charge','potentials']:changed=replace(f,**{bad:np.zeros((2,2))})
    elif bad=='nonfinite':changed=replace(f,C=np.array([[np.nan]]))
    elif bad=='negative':changed=replace(f,energy_C=-f.energy_C)
    elif bad=='diagnostics':changed=replace(f,energy_charge_relative=float('nan'))
    else:
        potential=f.potentials.copy();potential[r.cell.plate_nodes,0]=0;changed=replace(f,potentials=potential)
    monkeypatch.setattr(module,'extract_capacitance_3d',lambda *a,**kw:changed)
    with pytest.raises(ValueError,match='field solve changed'):extract_grid_plate_capacitance(**a)


def test_original_field_failure_is_retained(monkeypatch):
    def fail(*a,**kw):raise RuntimeError('deliberate field failure')
    monkeypatch.setattr(module,'extract_capacitance_3d',fail)
    with pytest.raises(RuntimeError,match='deliberate'):extract_grid_plate_capacitance(**arguments())
