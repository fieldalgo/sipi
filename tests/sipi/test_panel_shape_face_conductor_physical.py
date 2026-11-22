# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual face extraction, independent P2 energy and retained failure samples."""
from pathlib import Path
from dataclasses import replace,FrozenInstanceError
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sipi import CrossSectionDocument
from sipi.panel_shape_face_conductor import panel_shape_face_current_factors as solve,PanelShapeFaceCurrentError
import sipi.panel_shape_face_conductor as implementation
from sipi.shape_panel_line import shape_current_record,_sample_record

REFERENCE=json.loads((Path(__file__).parent/'data/panel_shape_faces_reference.json').read_text())


@pytest.fixture(scope='module')
def observed():
    return [(case,solve(CrossSectionDocument.from_dict(case['cross_section']).section,**case['options'])) for case in REFERENCE['cases']]


def snapshot(case,r):
    return dict(input=case['cross_section'],options=case['options'],labels=r.labels,parts=r.parts.tolist(),step_parts=r.step_parts.tolist(),
        whole_parts=r.whole_boundary_step_parts.tolist(),diagnostics=dict(r.diagnostics),
        base=shape_current_record(r.base,case['options']),samples=[_sample_record(s) for s in r.samples])


def test_actual_face_samples_keep_basis_order_and_registered_observations(observed,record_property):
    records=[]
    for case,r in observed:
        np.testing.assert_allclose(r.step_parts,case['parts'],rtol=1e-10,atol=0)
        np.testing.assert_array_equal(r.C0,case['C0'])
        np.testing.assert_array_equal(r.base.boundary_step_parts[-1],case['whole_parts'])
        assert r.base.step_m==case['step_m']
        n=len(r.trace_names);assert len(r.samples)==16*n and r.diagnostics['solve_count']==20*n+5
        assert r.diagnostics['face_step_relative_change']<=1e-4 and r.diagnostics['whole_sum_relative_change']<=1e-4
        assert r.labels[-1]=='reference:bottom' and r.labels[:4]==tuple('signal:'+r.names[0]+':'+f for f in ('bottom','top','left','right'))
        if n==3:assert r.labels[4:8]==tuple('reference:ground:guard:'+f for f in ('bottom','top','left','right'))
        assert not hasattr(r,'current_integrals')
        np.testing.assert_allclose(r.base.current_integrals,np.vstack((np.eye(len(r.names)),-np.ones((1,len(r.names))))),rtol=0,atol=1e-10)
        records.append(snapshot(case,r))
    record_property('actual_shape_face_fields',json.dumps(records,sort_keys=True,allow_nan=False))


def test_selected_panel_refinement_reports_each_energy_matrix(observed,record_property):
    changes=[]
    for i in (0,2):
        a=observed[i][1];b=observed[i+1][1]
        ratios=[float(np.max(abs(x-y))/np.max(abs(y))) for x,y in zip(a.parts,b.parts)]
        assert max(ratios)<=1e-3;changes.append(ratios)
    record_property('shape_face_panel_changes',json.dumps(changes))


def test_independent_P2_volume_energy_and_mesh_sequence(observed,record_property):
    actual=observed[1][1];rows=REFERENCE['independent_P2']['observations'];errors=[]
    for row in rows:
        reference=np.array(row['parts']);errors.append((abs(actual.parts[:,0,0]-reference)/reference).tolist())
        assert row['exact_source_C0_replay']
    assert max(errors[-1])<=.03
    changes=abs(np.array(rows[-1]['parts'])-rows[-2]['parts'])/rows[-1]['parts']
    assert max(changes)<=.02
    assert abs(actual.C0[0,0]-rows[-1]['C0'])/rows[-1]['C0']<=1e-3
    record_property('shape_face_independent_P2',json.dumps(dict(errors=errors,last_mesh_change=changes.tolist(),reference=REFERENCE['independent_P2']),sort_keys=True))


def test_all_evidence_is_immutable_and_invalid_metadata_is_rejected(observed):
    _,r=observed[-1]
    for a in (r.parts,r.step_parts,r.C0,r.total,r.whole_boundary_step_parts,r.samples[0].capacitance_per_permittivity,r.samples[0].request.polygons[0]):
        with pytest.raises(ValueError):a.flat[0]=0.
        with pytest.raises(ValueError):a.setflags(write=True)
    with pytest.raises(TypeError):r.diagnostics['solve_count']=0
    with pytest.raises(FrozenInstanceError):r.trace_names=()
    for changes in (dict(trace_ground=(False,)*3),dict(trace_names=r.trace_names[::-1]),dict(samples=r.samples[:-1]),dict(step_parts=r.step_parts[:1])):
        with pytest.raises(ValueError):replace(r,**changes)
    copy=r.samples[0].request.arguments();copy['polygons'][0][0][0]=99.
    assert r.samples[0].request.arguments()['polygons'][0][0][0]!=99.


def replay(monkeypatch,observed,alter=None):
    case,r=observed[-1];calls=[]
    monkeypatch.setattr(implementation,'panel_shape_current_factors',lambda *a,**k:r.base)
    def field(**request):
        i=len(calls);calls.append(request);sample=r.samples[i]
        assert request==sample.request.arguments()
        cap=sample.capacitance_per_permittivity.copy()
        if alter is not None:cap=alter(i,cap,r)
        return SimpleNamespace(capacitance_per_permittivity=cap,**dict(sample.diagnostics))
    monkeypatch.setattr(implementation,'_panel_solver',lambda:field)
    return case,r,calls


@pytest.mark.parametrize('index',[0,12,47])
def test_face_solver_failure_keeps_completed_whole_and_face_samples(observed,monkeypatch,index):
    original=ValueError('original face solve failure')
    def change(i,cap,r):
        if i==index:raise original
        return cap
    case,r,calls=replay(monkeypatch,observed,change)
    with pytest.raises(PanelShapeFaceCurrentError) as caught:solve(CrossSectionDocument.from_dict(case['cross_section']).section,**case['options'])
    e=caught.value;assert e.base is r.base and e.__cause__ is original and len(e.samples)==index
    assert e.request.arguments()==calls[-1] and e.step_parts is None
    for a,b in zip(e.samples,r.samples):np.testing.assert_array_equal(a.capacitance_per_permittivity,b.capacitance_per_permittivity)


@pytest.mark.parametrize('kind',['two-step','whole-sum','reciprocity','psd','nonfinite'])
def test_numerical_refusal_keeps_original_evidence(observed,monkeypatch,kind):
    def change(i,cap,r):
        base=r.base.samples[0].capacitance_per_permittivity
        if kind=='two-step' and i==0:cap[0,0]+=1e-6
        if kind=='whole-sum':cap=base+1.01*(cap-base)
        if kind=='reciprocity' and i==0:cap[0,2]+=1e-6
        if kind=='nonfinite' and i==0:cap[0,0]=np.inf
        if kind=='psd':
            n=len(r.trace_names);level=i//(8*n);face=(i%(8*n))//2;sign=-1 if i%2==0 else 1
            desired=r.step_parts[level].copy();old=desired[0].copy();desired[0]=-old;desired[1]+=2*old
            signal=[j for j,g in enumerate(r.trace_ground) if not g];css=base[np.ix_(signal,signal)]
            raw=np.zeros_like(base);block=css@desired[face]@css;raw[np.ix_(signal,signal)]=(block+block.T)/2
            cap=base-sign*(r.base.step_m/(2**level))*raw
        return cap
    case,r,calls=replay(monkeypatch,observed,change)
    match={'two-step':'difference steps','whole-sum':'face sums','reciprocity':'reciprocity','psd':'semidefinite','nonfinite':'nonfinite'}[kind]
    with pytest.raises(PanelShapeFaceCurrentError,match=match) as caught:solve(CrossSectionDocument.from_dict(case['cross_section']).section,**case['options'])
    e=caught.value;assert e.base is r.base
    if kind=='nonfinite':assert len(e.samples)==0 and e.request.arguments()==calls[0]
    else:
        assert len(e.samples)==len(r.samples)
        if kind!='reciprocity':assert e.step_parts.shape==r.step_parts.shape


def test_interrupt_during_face_solve_is_propagated(observed,monkeypatch):
    def change(*a):raise KeyboardInterrupt()
    case,_,calls=replay(monkeypatch,observed,change)
    with pytest.raises(KeyboardInterrupt):solve(CrossSectionDocument.from_dict(case['cross_section']).section,**case['options'])
    assert len(calls)==1
