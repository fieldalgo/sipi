# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Fixed-guard adapter joins the bounded physical-current scope explicitly."""
import dataclasses
import pytest
from sipi import CrossSection
from sipi._two_ground_current_reuse import _current_reuse_scope
import sipi.two_ground_harmonic_guard_corner_conductor as module
from test_two_ground_harmonic_guard_corner_conductor import section


def test_adapter_reuses_exact_geometry_and_controls_only_inside_the_scope(monkeypatch):
    calls=[]
    def solver(*args,**kwargs):calls.append((args,kwargs));return object()
    monkeypatch.setattr(module,'_solver',lambda:solver)
    monkeypatch.setattr(module,'_extract_result',lambda checked,polygons,shared,method:shared)
    s=section();traces=list(s.traces);traces[0]=dataclasses.replace(traces[0],width=traces[0].width*.99)
    changed=CrossSection(s.layers,traces,s.width,top='ground')
    with _current_reuse_scope():
        first=module.two_ground_harmonic_guard_corner_face_current_factors(s)
        assert module.two_ground_harmonic_guard_corner_face_current_factors(section(dielectric=9.)) is first
        refined=module.two_ground_harmonic_guard_corner_face_current_factors(s,panels_per_edge=48)
        moved=module.two_ground_harmonic_guard_corner_face_current_factors(changed)
        assert first is not refined and first is not moved and len(calls)==3
        with pytest.raises(ValueError):module.two_ground_harmonic_guard_corner_face_current_factors(s,panels_per_edge=50)
        assert len(calls)==3
    assert module.two_ground_harmonic_guard_corner_face_current_factors(s) is not first
    assert len(calls)==4


def test_adapter_keeps_failed_solve_out_of_reuse(monkeypatch):
    attempts=[]
    def solver(*args,**kwargs):
        attempts.append(1)
        if len(attempts)==1:raise ArithmeticError('explicit field refusal')
        return object()
    monkeypatch.setattr(module,'_solver',lambda:solver)
    monkeypatch.setattr(module,'_extract_result',lambda checked,polygons,shared,method:shared)
    with _current_reuse_scope():
        with pytest.raises(ArithmeticError,match='field refusal'):module.two_ground_harmonic_guard_corner_face_current_factors(section())
        good=module.two_ground_harmonic_guard_corner_face_current_factors(section())
        assert module.two_ground_harmonic_guard_corner_face_current_factors(section()) is good
        assert len(attempts)==2


def test_guard_assignment_changes_scoped_identity(monkeypatch):
    calls=[]
    def solver(*args,**kwargs):calls.append(kwargs['signal_indices']);return object()
    monkeypatch.setattr(module,'_solver',lambda:solver)
    monkeypatch.setattr(module,'_extract_result',lambda checked,polygons,shared,method:shared)
    s=section();traces=[dataclasses.replace(t,ground=(i==1)) for i,t in enumerate(s.traces)]
    changed=CrossSection(s.layers,traces,s.width,top='ground')
    with _current_reuse_scope():
        first=module.two_ground_harmonic_guard_corner_face_current_factors(s)
        second=module.two_ground_harmonic_guard_corner_face_current_factors(changed)
        assert first is not second
        assert module.two_ground_harmonic_guard_corner_face_current_factors(s) is first
    assert calls==[(0,1),(0,2)]
