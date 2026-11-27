# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact request-local reuse, admission, isolation and actual frozen goals."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from threading import Barrier
from types import SimpleNamespace
import hashlib
import json
import numpy as np
import pytest
from sipi import CrossSection, Layer
import sipi.two_ground_conductor as current
from sipi._two_ground_current_reuse import _current_reuse_scope, _SCOPE
from sipi.two_ground_conductor import two_ground_current_factors as factors
from test_two_ground_conductor import guarded, metals


def fake_solver(monkeypatch, *, failure=None):
    calls=[]
    def solve(polygons, *, box_size, panels_per_edge, ground_modes, interpolation_degree):
        width,height=box_size
        calls.append((width,height,panels_per_edge,ground_modes,interpolation_degree))
        if failure is not None and len(calls)==1:raise failure('original current refusal')
        n=len(polygons);eye=np.eye(n)
        return SimpleNamespace(capacitance_per_permittivity=eye,
            current_gram=np.repeat(eye[None,:,:],n+2,axis=0),
            current_integrals=np.vstack((eye,-np.ones((2,n))/2)),
            panel_count=sum(len(p) for p in polygons)*panels_per_edge,
            condition_bound=1.,reciprocity_error=0.,residual_error=0.,current_error=0.,
            matrix_refinement_error=0.,ground_refinement_error=0.,minimum_scaled_eigenvalue=1.)
    monkeypatch.setattr(current,'_solver',lambda:solve)
    return solve,calls


def changed(kind):
    sec=guarded();traces=list(sec.traces);layers=sec.layers;width=sec.width
    if kind=='width':width+=.0001
    elif kind=='height':layers=[Layer('uniform',.0021,1.)]
    elif kind=='polygon':traces[0]=replace(traces[0],width=traces[0].width*1.01)
    elif kind=='name':traces[0]=replace(traces[0],name='renamed')
    elif kind=='ground':traces[0]=replace(traces[0],ground=True);traces[1]=replace(traces[1],ground=False)
    elif kind=='order':traces.reverse()
    elif kind=='dielectric':layers=[Layer('other',.001,2.,tan_delta=.01),Layer('second',.001,7.)]
    return CrossSection(layers,traces,width,top='ground')


def test_no_scope_keeps_direct_api_uncached_and_scoped_values_are_immutable(monkeypatch):
    _,calls=fake_solver(monkeypatch);sec=guarded()
    assert factors(sec) is not factors(sec) and len(calls)==2
    with _current_reuse_scope() as cache:
        a=factors(sec);assert factors(sec) is a and len(calls)==3 and len(cache)==1
        for array in (a.parts,a.current_integrals,a.C0,a.boundary_parts,a.boundary_integrals):
            with pytest.raises(ValueError):array.setflags(write=True)
        with pytest.raises(TypeError):a.diagnostics['current_error']=1.
    assert not cache and _SCOPE.get() is None
    assert factors(sec) is not a and len(calls)==4


@pytest.mark.parametrize('kind',['width','height','polygon','name','ground','order','panels','modes','degree'])
def test_each_physical_key_component_invalidates_reuse(monkeypatch,kind):
    _,calls=fake_solver(monkeypatch)
    kw={'panels_per_edge':64} if kind=='panels' else {'ground_modes':256} if kind=='modes' else {'interpolation_degree':14} if kind=='degree' else {}
    with _current_reuse_scope():
        a=factors(guarded());b=factors(changed(kind),**kw)
        assert b is not a and len(calls)==2
        assert factors(changed(kind),**kw) is b and len(calls)==2


def test_dielectric_metadata_is_not_a_vacuum_current_key(monkeypatch):
    _,calls=fake_solver(monkeypatch)
    with _current_reuse_scope():assert factors(guarded()) is factors(changed('dielectric'))
    assert len(calls)==1


def test_callable_identity_and_lifetime_are_retained(monkeypatch):
    first,calls=fake_solver(monkeypatch)
    with _current_reuse_scope() as cache:
        a=factors(guarded())
        second,other=fake_solver(monkeypatch);b=factors(guarded())
        assert b is not a and len(calls)==len(other)==1
        assert {id(value[0]) for value in cache.values()}=={id(first),id(second)}
        monkeypatch.setattr(current,'_solver',lambda:first)
        assert factors(guarded()) is a and len(calls)==1


@pytest.mark.parametrize('kind',['invalid-section','invalid-control','capability','skin-depth'])
def test_admission_is_not_skipped_after_a_hit(monkeypatch,kind):
    _,calls=fake_solver(monkeypatch)
    with _current_reuse_scope() as cache:
        factors(guarded())
        if kind=='invalid-section':
            sec=guarded();bad=CrossSection(sec.layers,sec.traces,sec.width,bottom='open',top='ground')
            with pytest.raises(ValueError):factors(bad)
        elif kind=='invalid-control':
            with pytest.raises(ValueError):factors(guarded(),panels_per_edge=True)
        elif kind=='capability':
            def unavailable():raise RuntimeError('original unavailable capability')
            monkeypatch.setattr(current,'_solver',unavailable)
            with pytest.raises(RuntimeError,match='original unavailable'):factors(guarded())
        else:
            conductors,reference=metals(['left','right'])
            from sipi.boundary_conductor import SurfaceMetal
            from sipi.face_conductor import ReferenceSurfaceMetals
            reference=ReferenceSurfaceMetals(reference.bottom,reference.top,None,{'guard':SurfaceMetal(58e6)})
            with pytest.raises(ValueError,match='skin depth'):
                current.two_ground_conductor_loss(guarded(),[1.],conductors=conductors,reference=reference,ground_thickness=35e-6)
        assert len(calls)==1 and len(cache)==1


@pytest.mark.parametrize('failure',[ArithmeticError,KeyboardInterrupt])
def test_failed_computation_is_never_cached(monkeypatch,failure):
    _,calls=fake_solver(monkeypatch,failure=failure)
    with _current_reuse_scope() as cache:
        with pytest.raises(failure,match='original current refusal'):factors(guarded())
        assert not cache
        a=factors(guarded());assert factors(guarded()) is a and len(calls)==2


def test_eight_entry_lru_bound_and_cleanup(monkeypatch):
    _,calls=fake_solver(monkeypatch);sections=[]
    for i in range(9):
        sec=guarded();traces=list(sec.traces);traces[0]=replace(traces[0],x=traces[0].x+i*1e-6)
        sections.append(CrossSection(sec.layers,traces,sec.width,top='ground'))
    with _current_reuse_scope() as cache:
        original=[factors(sec) for sec in sections[:8]];assert len(cache)==8
        assert factors(sections[0]) is original[0]
        factors(sections[8]);assert len(cache)==8 and len(calls)==9
        assert factors(sections[0]) is original[0]
        assert factors(sections[1]) is not original[1] and len(calls)==10 and len(cache)==8
    assert not cache


def test_nested_requests_restore_parent_scope(monkeypatch):
    _,calls=fake_solver(monkeypatch)
    with _current_reuse_scope() as outer:
        a=factors(guarded())
        with _current_reuse_scope() as inner:
            b=factors(guarded());assert b is not a and factors(guarded()) is b
        assert not inner and len(outer)==1 and factors(guarded()) is a
    assert not outer and len(calls)==2


@pytest.mark.parametrize('failure',[ValueError,KeyboardInterrupt])
def test_exception_and_interrupt_clear_scope(monkeypatch,failure):
    _,calls=fake_solver(monkeypatch)
    with pytest.raises(failure):
        with _current_reuse_scope() as cache:
            factors(guarded());raise failure('leave request')
    assert not cache and _SCOPE.get() is None
    factors(guarded());assert len(calls)==2


def test_concurrent_requests_have_separate_caches(monkeypatch):
    _,calls=fake_solver(monkeypatch);barrier=Barrier(2)
    def run():
        with _current_reuse_scope():
            a=factors(guarded());barrier.wait(timeout=10)
            assert factors(guarded()) is a
            return a
    with ThreadPoolExecutor(max_workers=2) as executor:
        tasks=[executor.submit(run) for _ in range(2)];a,b=[task.result(timeout=20) for task in tasks]
    assert a is not b and len(calls)==2 and _SCOPE.get() is None


@pytest.mark.parametrize('sampled',[False,True],ids=['single','finite-grid'])
def test_real_selected_goal_keeps_every_value_and_attempt_with_two_solves(monkeypatch,sampled,record_property):
    import galerkin.panel_electrostatics as shared
    import sipi.two_ground_pair_goal as single_module
    import sipi.two_ground_sampled_pair_goal as sampled_module
    from sipi.execution_request import SavedExecutionRequest
    from test_two_ground_pair_goal_document import document as single_document
    from test_two_ground_sampled_pair_goal_document import document as sampled_document,SELECTED
    doc=sampled_document(True,initial=SELECTED,max_evaluations=4) if sampled else single_document(True)
    if not sampled:
        raw=doc.to_dict();raw.update(initial=list(SELECTED),max_evaluations=4);doc=type(doc).from_dict(raw)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    original=shared.solve_two_ground_rectangle;calls=[]
    def solve(polygons,*,box_size,panels_per_edge=32,ground_modes=128,interpolation_degree=12):
        width,height=box_size
        calls.append(dict(width=width,height=height,panels=panels_per_edge,modes=ground_modes,degree=interpolation_degree,
            polygon_hashes=[hashlib.sha256(p.tobytes()).hexdigest() for p in polygons]))
        return original(polygons,box_size=box_size,panels_per_edge=panels_per_edge,
            ground_modes=ground_modes,interpolation_degree=interpolation_degree)
    monkeypatch.setattr(shared,'solve_two_ground_rectangle',solve)
    with monkeypatch.context() as context:
        context.setattr(sampled_module if sampled else single_module,'_current_reuse_scope',nullcontext)
        uncached=request.run()
    before=list(calls);calls.clear();cached=request.run();after=list(calls)
    record_property('two_ground_current_reuse',json.dumps(dict(uncached=uncached,cached=cached,
        uncached_current_inputs=before,cached_current_inputs=after),sort_keys=True))
    assert cached==uncached and cached['execution']['status']=='complete'
    assert cached['execution']['result']['evaluations']==4
    assert len(before)==4 and len(after)==2
    assert before[0]==before[1]==after[0] and before[2]==before[3]==after[1]
    assert _SCOPE.get() is None
