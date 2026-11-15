# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import dataclasses
from types import SimpleNamespace
import numpy as np
import pytest
from sipi import CrossSection, Layer, Trace, PolygonTrace
from sipi.constants import mu_0
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.layered_metal import MetalLayer
from sipi.roughness import CausalHuray
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.two_ground_conductor import two_ground_conductor_loss, two_ground_current_factors
import sipi.two_ground_face_conductor as module

F = np.array([1e9,3e9,10e9])
CONTROLS = dict(panels_per_edge=32,interpolation_degree=16)


def section(guard=True, scale=1., operation=None):
    traces=[Trace('left',x=-.0004,y=.0007,width=.0003,thickness=.00005,top_width=.00028),
            Trace('right',x=.0004,y=.0009,width=.0003,thickness=.00006,top_width=.00032)]
    if guard:traces.insert(1,Trace('guard',x=0.,y=.001,width=.0002,thickness=.00005,ground=True))
    if operation=='reverse':traces=traces[::-1]
    updated=[]
    for t in traces:
        x,y,w,tw=t.x,t.y,t.width,t.top_width
        if operation=='mirror-x':x=-x
        if operation=='mirror-y':
            y=.002-y-t.thickness
            if tw is not None:w,tw=tw,w
        updated.append(Trace(t.name,x=x*scale,y=y*scale,width=w*scale,thickness=t.thickness*scale,
            ground=t.ground,top_width=None if tw is None else tw*scale))
    return CrossSection([Layer('uniform',.002*scale,9. if operation=='dielectric' else 4.)],updated,.008*scale,top='ground')


def reference(guard=True):
    return ReferenceSurfaceMetals(SurfaceMetal(45e6),SurfaceMetal(21e6),None,
                                 {'guard':SurfaceMetal(17e6)} if guard else {})


def conductors():
    return {'left':TraceFaceMetals.uniform(SurfaceMetal(58e6)),
            'right':TraceFaceMetals.uniform(SurfaceMetal(35e6,1.4))}


@pytest.fixture(scope='module')
def factors():
    return module.two_ground_face_current_factors(section(),**CONTROLS)


def test_factor_order_ground_voltage_and_immutable_partitions(factors):
    assert factors.names==('left','right')
    assert factors.labels==tuple('signal:'+n+':'+f for n in ('left','right') for f in ('bottom','top','left','right'))+('reference:bottom','reference:top')+tuple('reference:ground:guard:'+f for f in ('bottom','top','left','right'))
    assert factors.base.diagnostics['ground_voltage_error']<=1e-10
    np.testing.assert_allclose(factors.current_integrals[:4].sum(axis=0),[1,0],rtol=0,atol=1e-10)
    np.testing.assert_allclose(factors.current_integrals[4:8].sum(axis=0),[0,1],rtol=0,atol=1e-10)
    np.testing.assert_allclose(factors.current_integrals.sum(axis=0),[0,0],rtol=0,atol=1e-10)
    assert np.max(abs(factors.current_integrals[10:].sum(axis=0)))>.01
    for value in (factors.parts,factors.current_integrals,factors.C0):
        with pytest.raises(ValueError):value.setflags(write=True)
    with pytest.raises(dataclasses.FrozenInstanceError):factors.parts=None


@pytest.mark.parametrize('guard',[False,True])
def test_uniform_faces_preserve_whole_law_at_three_frequencies(guard,record_property):
    sec=section(guard);ref=reference(guard);metals=conductors()
    old=two_ground_conductor_loss(sec,F,conductors={k:v.bottom for k,v in metals.items()},reference=ref,ground_thickness=35e-6,**CONTROLS)
    new=module.two_ground_conductor_loss_by_face(sec,F,conductors=metals,reference=ref,ground_thickness=35e-6,**CONTROLS)
    for name in ('R','L_internal'):np.testing.assert_allclose(getattr(new,name),getattr(old,name),rtol=1e-10,atol=0)
    np.testing.assert_array_equal(new.factors.C0,old.factors.C0)
    np.testing.assert_array_equal(new.factors.base.boundary_parts,old.factors.boundary_parts)
    record_property('face_uniform',str(dict(guard=guard,R=new.R.tolist(),L_internal=new.L_internal.tolist())))


def test_distinct_faces_match_independent_surface_power_formula():
    values=[SurfaceMetal(sigma,mu) for sigma,mu in ((58e6,1),(35e6,1.4),(21e6,1),(45e6,1))]
    metals={'left':TraceFaceMetals(*values),'right':TraceFaceMetals(*values[::-1])}
    ref=ReferenceSurfaceMetals(values[1],values[2],None,{'guard':TraceFaceMetals(*values)})
    result=module.two_ground_conductor_loss_by_face(section(),F,conductors=metals,reference=ref,ground_thickness=35e-6,**CONTROLS)
    r=np.zeros_like(result.R)
    for k,f in enumerate(F):
        for i,m in enumerate(result.metals):
            r[k]+=np.sqrt(np.pi*f*mu_0*m.relative_permeability/m.conductivity)*result.factors.parts[i]
    np.testing.assert_allclose(result.R,r,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.L_internal*(2*np.pi*F[:,None,None]),r,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1),result.R,rtol=1e-12,atol=0)
    for currents in (np.array([1.,0.]),np.array([1.,-1.]),np.array([1.,1.]),np.array([1.+2.j,-.3j])):
        assert np.all(np.real(np.einsum('i,fij,j->f',currents.conj(),result.R,currents))>0)
    network=result.network(C=4*result.factors.C0,G=np.zeros((2,2)),length=.02)
    np.testing.assert_allclose(network.s,network.s.swapaxes(1,2),rtol=1e-10,atol=1e-12)
    assert np.max(np.linalg.svd(network.s,compute_uv=False))<=1+1e-10


@pytest.mark.parametrize('law',['coating','roughness'])
def test_one_face_law_changes_only_its_weighted_surface_term(law):
    sec=section();metals=conductors();ref=reference()
    old=module.two_ground_conductor_loss_by_face(sec,F,conductors=metals,reference=ref,ground_thickness=35e-6,**CONTROLS)
    coating=LayeredSurfaceMetal(58e6,coatings=(MetalLayer(2e-7,14e6,3.),MetalLayer(1e-6,40e6)))
    if law=='roughness':coating=SurfaceMetal(58e6,roughness=CausalHuray((.2e-6,),(2.,)))
    changed=dict(metals);changed['left']=dataclasses.replace(metals['left'],top=coating)
    new=module.two_ground_conductor_loss_by_face(sec,F,conductors=changed,reference=ref,ground_thickness=35e-6,**CONTROLS)
    dz=coating._samples(F)[3]-metals['left'].top._samples(F)[3]
    expected=dz[:,None,None]*old.factors.parts[1]
    np.testing.assert_allclose(new.R-old.R,expected.real,rtol=1e-10,atol=0)
    np.testing.assert_allclose((new.L_internal-old.L_internal)*2*np.pi*F[:,None,None],expected.imag,rtol=1e-10,atol=0)
    assert np.max(abs(expected))>0


@pytest.mark.parametrize('operation',['scale','mirror-x','mirror-y','reverse','dielectric'])
def test_factors_obey_physical_transformations(factors,operation):
    scale=2. if operation=='scale' else 1.
    other=module.two_ground_face_current_factors(section(scale=scale,operation=operation),**CONTROLS)
    labels=list(other.labels);order=[]
    for label in factors.labels:
        target=label
        if operation in ('mirror-x','mirror-y'):
            mapping={'left':'right','right':'left'} if operation=='mirror-x' else {'bottom':'top','top':'bottom'}
            prefix,face=label.rsplit(':',1)
            if face in mapping:target=prefix+':'+mapping[face]
        order.append(labels.index(target))
    q=other.parts[order]*scale;j=other.current_integrals[order];c=other.C0
    if operation=='reverse':q=q[:,::-1,::-1];j=j[:,::-1];c=c[::-1,::-1]
    np.testing.assert_allclose(q,factors.parts,rtol=1e-10,atol=0)
    np.testing.assert_allclose(j,factors.current_integrals,rtol=0,atol=1e-10)
    np.testing.assert_allclose(c,factors.C0,rtol=1e-10,atol=0)


@pytest.mark.parametrize('case',['signal-map','signal-whole','reference-type','bottom','top','sides','ground-map','low-frequency','ground-thin','coating-core','polygon','count','degree'])
def test_invalid_inputs_are_refused_before_shared_solve(monkeypatch,case):
    monkeypatch.setattr(module,'_solver',lambda:pytest.fail('shared dependency reached'))
    sec=section();m=conductors();ref=reference();frequency=F;thickness=35e-6;controls=dict(CONTROLS)
    if case=='signal-map':m.pop('left')
    elif case=='signal-whole':m['left']=m['left'].bottom
    elif case=='reference-type':ref=SurfaceMetal(58e6)
    elif case in ('bottom','top'):ref=dataclasses.replace(ref,**{case:None})
    elif case=='sides':ref=dataclasses.replace(ref,sides=SurfaceMetal(58e6))
    elif case=='ground-map':ref=dataclasses.replace(ref,conductors={})
    elif case=='low-frequency':frequency=[1.]
    elif case=='ground-thin':thickness=1e-8
    elif case=='coating-core':m['left']=TraceFaceMetals.uniform(LayeredSurfaceMetal(58e6,coatings=(MetalLayer(60e-6,14e6),)))
    elif case=='polygon':
        traces=list(sec.traces);t=traces[1];traces[1]=PolygonTrace(t.name,t.corners(),ground=True)
        sec=CrossSection(sec.layers,traces,sec.width,top='ground')
    elif case=='count':controls['panels_per_edge']=257
    elif case=='degree':controls['interpolation_degree']=11
    with pytest.raises((ValueError,TypeError)):
        module.two_ground_conductor_loss_by_face(sec,frequency,conductors=m,reference=ref,ground_thickness=thickness,**controls)


def test_missing_shared_capability_has_no_fallback(monkeypatch):
    monkeypatch.setattr(module,'import_module',lambda _:SimpleNamespace())
    with pytest.raises(RuntimeError,match='pinned galerkin'):
        module.two_ground_face_current_factors(section(),**CONTROLS)


def test_one_shared_field_solve(monkeypatch):
    original=module._solver();calls=[]
    def counted(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
    monkeypatch.setattr(module,'_solver',lambda:counted)
    module.two_ground_face_current_factors(section(),**CONTROLS)
    assert calls==[1]


def test_guard_face_reduction_against_prescribed_zero_potential(factors):
    sec=section();shared=module._solver()([t.corners()+[sec.width/2,0.] for t in sec.traces],
        width=sec.width,height=sec.height,**CONTROLS)
    cap=shared.whole.capacitance_per_permittivity
    v=np.zeros((3,2));v[[0,2]]=np.linalg.inv(cap[np.ix_([0,2],[0,2])])
    current=cap@v
    assert np.max(abs(v[1]))==0
    edges=np.array([current.T@q@current for q in shared.edge_current_gram])
    # Input traces are left, guard, right; each starts with its bottom edge.
    order=[0,2,3,1,8,10,11,9,4,6,7,5]
    np.testing.assert_allclose(factors.parts[list(range(8))+list(range(10,14))],edges[order],rtol=1e-10,atol=0)
    floating=cap[np.ix_([0,2],[0,2])]-cap[[0,2],1,None]*cap[None,1,[0,2]]/cap[1,1]
    assert not np.allclose(floating,cap[np.ix_([0,2],[0,2])],rtol=1e-3,atol=0)


@pytest.mark.parametrize('kind',['endpoint','owner'])
def test_shared_edge_assignment_must_match_physical_geometry(monkeypatch,kind):
    solver=module._solver()
    def changed(*args,**kwargs):
        value=solver(*args,**kwargs)
        if kind=='endpoint':
            a=value.edge_starts.copy();a[0,0]+=.00001
            return dataclasses.replace(value,edge_starts=a)
        owner=value.edge_owners.copy();owner[0]=1
        return dataclasses.replace(value,edge_owners=owner)
    monkeypatch.setattr(module,'_solver',lambda:changed)
    with pytest.raises(ValueError,match='shared edges'):
        module.two_ground_face_current_factors(section(),**CONTROLS)
