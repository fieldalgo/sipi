# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import numpy as np
import pytest
from sipi import CrossSection,Layer
from sipi._two_ground_current_reuse import _current_reuse_scope,_SCOPE
import sipi.two_ground_linear_corner_conductor as module
from test_two_ground_linear_corner_conductor import section,conductors,reference,F


def fake(monkeypatch):
    calls=[]
    def solver(*args,**kwargs):calls.append((args,kwargs));return object()
    monkeypatch.setattr(module,'_solver',lambda:solver)
    monkeypatch.setattr(module,'_extract_result',lambda sec,polygons,result,label:result)
    return solver,calls


def factors(sec=None,**kwargs):
    return module.two_ground_linear_corner_face_current_factors(section() if sec is None else sec,**kwargs)


def test_direct_uncached_scoped_identity_cleanup(monkeypatch):
    _,calls=fake(monkeypatch);a=factors();assert factors() is not a and len(calls)==2
    with _current_reuse_scope() as cache:
        a=factors();assert factors() is a and len(calls)==3 and len(cache)==1
    assert not cache and _SCOPE.get() is None and factors() is not a


@pytest.mark.parametrize('kind',['width','height','polygon','name','order','panels','modes','solver'])
def test_physical_key_change_misses(monkeypatch,kind):
    solver,calls=fake(monkeypatch);sec=section();traces=list(sec.traces);width=sec.width;layers=sec.layers;kwargs={}
    if kind=='width':width+=.0001
    if kind=='height':layers=[Layer('uniform',.0021,4.)]
    if kind=='polygon':traces[0]=replace(traces[0],width=traces[0].width*1.01)
    if kind=='name':traces[0]=replace(traces[0],name='renamed')
    if kind=='order':traces.reverse()
    if kind=='panels':kwargs['panels_per_edge']=34
    if kind=='modes':kwargs['ground_modes']=512
    changed=CrossSection(layers,traces,width,top='ground')
    with _current_reuse_scope():
        a=factors()
        if kind=='solver':monkeypatch.setattr(module,'_solver',lambda:(lambda *args,**kwargs:solver(*args,**kwargs)))
        b=factors(changed,**kwargs);assert b is not a and len(calls)==2


def test_dielectric_only_change_reuses_vacuum_field(monkeypatch):
    _,calls=fake(monkeypatch);sec=section();changed=CrossSection([Layer('a',.001,2.),Layer('b',.001,8.)],sec.traces,sec.width,top='ground')
    with _current_reuse_scope():assert factors() is factors(changed)
    assert len(calls)==1


@pytest.mark.parametrize('kind',['skin','budget','capability','geometry','degree'])
def test_hit_does_not_bypass_admission(monkeypatch,kind):
    _,calls=fake(monkeypatch)
    with _current_reuse_scope() as cache:
        factors()
        with pytest.raises((ValueError,RuntimeError)):
            if kind=='skin':module.two_ground_linear_corner_conductor_loss_by_face(section(),[1.],conductors=conductors(),reference=reference(),ground_thickness=35e-6)
            elif kind=='budget':factors(panels_per_edge=72)
            elif kind=='degree':factors(interpolation_degree=25)
            elif kind=='geometry':
                sec=section();factors(CrossSection(sec.layers,sec.traces,sec.width,top='open'))
            else:
                def missing():raise RuntimeError('missing capability')
                monkeypatch.setattr(module,'_solver',missing);factors()
        assert len(calls)==1 and len(cache)==1


@pytest.mark.parametrize('failure',[ArithmeticError,KeyboardInterrupt])
def test_failure_not_cached_and_exit_clears(monkeypatch,failure):
    _,calls=fake(monkeypatch)
    def convert(*args):
        if len(calls)==1:raise failure('unchanged failure')
        return args[2]
    monkeypatch.setattr(module,'_extract_result',convert)
    with _current_reuse_scope() as cache:
        with pytest.raises(failure):factors()
        assert not cache
        a=factors();assert factors() is a and len(calls)==2
    assert not cache and _SCOPE.get() is None


def test_scope_lru_nested_and_concurrent_isolation(monkeypatch):
    _,calls=fake(monkeypatch);sec=section()
    with _current_reuse_scope() as outer:
        a=factors()
        with _current_reuse_scope() as inner:assert factors() is not a
        assert not inner and factors() is a
        for i in range(9):
            changed=CrossSection(sec.layers,[replace(t,x=t.x+(i+1)*1e-6) for t in sec.traces],sec.width,top='ground');factors(changed)
        assert len(outer)==8 and factors() is not a
    assert not outer
    barrier=Barrier(2)
    def run():
        with _current_reuse_scope():
            a=factors();barrier.wait(timeout=10);assert factors() is a;return a
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(run) for _ in range(2)];assert jobs[0].result(timeout=20) is not jobs[1].result(timeout=20)
    assert _SCOPE.get() is None


def test_real_scoped_currents_and_changed_surface_law_keep_exact_fields(monkeypatch,record_property):
    import json
    from sipi.boundary_conductor import SurfaceMetal
    from sipi.constants import mu_0
    solver=module._solver();calls=[]
    def solve(*args,**kwargs):calls.append(kwargs);return solver(*args,**kwargs)
    monkeypatch.setattr(module,'_solver',lambda:solve)
    sec=section(0);metals=conductors(0);kwargs=dict(reference=reference(),ground_thickness=35e-6,panels_per_edge=16)
    direct=module.two_ground_linear_corner_conductor_loss_by_face(sec,F,conductors=metals,**kwargs)
    with _current_reuse_scope() as cache:
        cached=module.two_ground_linear_corner_conductor_loss_by_face(sec,F,conductors=metals,**kwargs)
        changed=dict(metals);name=sec.traces[0].name;changed[name]=replace(metals[name],top=SurfaceMetal(17e6))
        altered=module.two_ground_linear_corner_conductor_loss_by_face(sec,F,conductors=changed,**kwargs)
        whole=module.two_ground_linear_corner_current_factors(sec,panels_per_edge=16)
        assert altered.factors is cached.factors and whole is cached.factors.base and len(calls)==2
        for key in ['parts','current_integrals','C0']:
            np.testing.assert_array_equal(getattr(direct.factors,key),getattr(cached.factors,key))
        np.testing.assert_array_equal(direct.R,cached.R);np.testing.assert_array_equal(direct.L_internal,cached.L_internal)
        change=np.sqrt(np.pi*F*mu_0)*(1/np.sqrt(17e6)-1/np.sqrt(metals[name].top.conductivity))
        expected=change[:,None,None]*cached.factors.parts[1]
        np.testing.assert_allclose(altered.R-cached.R,expected,rtol=1e-10,atol=0)
        for array in [cached.factors.parts,cached.factors.C0,cached.factors.base.boundary_parts]:
            with pytest.raises(ValueError):array.flags.writeable=True
        record_property('linear_corner_current_reuse',json.dumps(dict(calls=calls,R=cached.R.tolist(),changed_R=altered.R.tolist(),C0=cached.factors.C0.tolist()),sort_keys=True))
    assert not cache and _SCOPE.get() is None
