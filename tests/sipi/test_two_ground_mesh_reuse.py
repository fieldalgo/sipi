# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Bounded detached mesh reuse and full physical paired-goal equivalence."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Barrier
import json

import numpy as np
import pytest
from galerkin import Mesh
from sipi import CrossSection, CrossSectionDocument
from sipi.crosssection import MeshedCrossSection
import sipi._two_ground_mesh_reuse as reuse
from test_two_ground_panel_line import document


def small_mesh():
    mesh=Mesh(np.array([[0.,0.],[1.,0.],[0.,1.]]),np.array([[0,1,2]]),
              {'outer':np.array([0,1,2])},regions=np.array([0]),region_names=['uniform'],
              boundary_edges={'outer':np.array([[0,1],[1,2],[2,0]])})
    return MeshedCrossSection(mesh,np.array([4.]),np.array([.003]),
                              {'positive':np.array([1]),'negative':np.array([2])},np.array([0]))


def fake_mesh(monkeypatch, failure=None):
    calls=[]
    def make(self,**options):
        calls.append(options)
        if failure is not None and len(calls)==1:raise failure('original mesh refusal')
        return small_mesh()
    monkeypatch.setattr(CrossSection,'mesh',make)
    return make,calls


def cross():
    return document('box-8').cross_section


def get(doc=None):
    doc=cross() if doc is None else doc
    return reuse._reuse_mesh(doc,doc.section)


def test_outside_scope_is_uncached_and_returned_meshes_never_alias_snapshot(monkeypatch):
    _,calls=fake_mesh(monkeypatch)
    assert get() is not get() and len(calls)==2
    with reuse._mesh_reuse_scope() as cache:
        a=get();a.mesh.nodes[:]=99;a.mesh.triangles[:]=0;a.mesh.region_names.clear()
        a.signals['positive'][:]=0;a.signals.clear();a.eps_r[:]=100;a.ground[:]=2
        b=get();assert len(calls)==3
        np.testing.assert_array_equal(b.mesh.nodes,small_mesh().mesh.nodes)
        assert b.mesh.region_names==['uniform'] and list(b.signals)==['positive','negative']
        assert b.eps_r[0]==4 and b.ground[0]==0
        b.mesh.nodes[:]=42;b.mesh.boundary['outer'][:]=1;b.mesh.boundary_edges.clear()
        b.tan_delta[:]=.7;b.signals['negative'][:]=0
        c=get();assert c.mesh.nodes[0,0]==0 and c.tan_delta[0]==.003
        assert c.mesh.boundary['outer'].tolist()==[0,1,2] and c.mesh.boundary_edges
        assert c.signals['negative'].tolist()==[2] and len(calls)==3
        assert len(cache)==1 and c is not next(iter(cache.values()))[1]
    assert not cache and reuse._SCOPE.get() is None
    get();assert len(calls)==4


def changed(kind):
    raw=cross().to_dict()
    if kind=='width':raw['box']['width']*=1.01
    elif kind=='boundary':raw['box']['sides']='ground'
    elif kind in ('eps_r','tan_delta','thickness'):raw['layers'][0][kind]*=1.01
    elif kind=='material-name':raw['layers'][0]['name']='another'
    elif kind=='trace-name':raw['traces'][0]['name']='renamed'
    elif kind=='trace-ground':raw['traces'][0]['ground']=True
    elif kind=='trace-order':raw['traces'].reverse()
    elif kind=='vertices':
        for v in raw['traces'][0]['vertices']:v[0]-=1e-7
    elif kind in ('edge_size','far_size','grade'):raw['mesh'][kind]*=.99
    elif kind=='min_angle':raw['mesh']['min_angle']=27.
    elif kind=='corner_size':raw['mesh']['corner_size']=raw['mesh']['edge_size']/2
    return CrossSectionDocument.from_dict(raw)


@pytest.mark.parametrize('kind',['width','boundary','eps_r','tan_delta','thickness','material-name',
    'trace-name','trace-ground','trace-order','vertices','edge_size','far_size','grade','min_angle','corner_size'])
def test_each_saved_mesh_input_invalidates_reuse(monkeypatch,kind):
    _,calls=fake_mesh(monkeypatch)
    with reuse._mesh_reuse_scope():
        get()
        if kind=='corner_size':
            # The saved cross-section contract intentionally does not admit this
            # direct mesh option. A warm cache must not change that contract.
            with pytest.raises(ValueError,match='mesh has missing or unknown fields'):changed(kind)
            get();assert len(calls)==1
        else:
            get(changed(kind));get(changed(kind));assert len(calls)==2


@pytest.mark.parametrize('producer',['mesh','generate','from_mesher'])
def test_producer_identity_and_lifetime_are_retained(monkeypatch,producer):
    original,calls=fake_mesh(monkeypatch)
    with reuse._mesh_reuse_scope() as cache:
        get()
        if producer=='mesh':
            def other(self,**options):return original(self,**options)
            monkeypatch.setattr(CrossSection,'mesh',other)
        else:
            monkeypatch.setattr(reuse.crosssection,producer,lambda *a,**k:None)
        get();get();assert len(calls)==2 and len(cache)==2
        assert next(iter(cache.values()))[0][0] is original


def test_mesh_settings_admission_still_runs_on_warm_key(monkeypatch):
    _,calls=fake_mesh(monkeypatch);doc=cross();sec=doc.section
    with reuse._mesh_reuse_scope() as cache:
        reuse._reuse_mesh(doc,sec)
        def refuse(**options):raise ValueError('original settings refusal')
        monkeypatch.setattr(sec,'mesh_settings',refuse)
        with pytest.raises(ValueError,match='original settings refusal'):reuse._reuse_mesh(doc,sec)
        assert len(cache)==1 and len(calls)==1


@pytest.mark.parametrize('failure',[ArithmeticError,KeyboardInterrupt])
def test_failed_mesh_is_not_cached(monkeypatch,failure):
    _,calls=fake_mesh(monkeypatch,failure)
    with reuse._mesh_reuse_scope() as cache:
        with pytest.raises(failure,match='original mesh refusal'):get()
        assert not cache
        get();get();assert len(calls)==2


def test_two_entry_lru_and_total_array_payload_limit(monkeypatch):
    _,calls=fake_mesh(monkeypatch);size=reuse._array_bytes(small_mesh())
    with reuse._mesh_reuse_scope() as cache:
        get();get(changed('width'));get();get(changed('grade'))
        assert len(cache)==2 and len(calls)==3
        get();assert len(calls)==3
        get(changed('width'));assert len(calls)==4
    monkeypatch.setattr(reuse,'_ARRAY_BYTES',2*size-1)
    with reuse._mesh_reuse_scope() as cache:
        get();get(changed('width'));get();assert len(cache)==1 and len(calls)==7
        assert sum(row[2] for row in cache.values())==size
    monkeypatch.setattr(reuse,'_ARRAY_BYTES',size-1)
    with reuse._mesh_reuse_scope() as cache:
        get();get();assert not cache and len(calls)==9


@pytest.mark.parametrize('warm',[False,True])
def test_cache_copy_memory_refusal_falls_back_to_direct_result(monkeypatch,warm):
    _,calls=fake_mesh(monkeypatch)
    with reuse._mesh_reuse_scope():
        if warm:get()
        def refuse(value):raise MemoryError('cache-only allocation')
        monkeypatch.setattr(reuse,'deepcopy',refuse)
        result=get();assert result.eps_r[0]==4 and len(calls)==1+warm


def test_array_accounting_includes_nested_mesh_metadata_and_no_duplicate_objects():
    m=small_mesh();old=reuse._array_bytes(m)
    a=np.ones((3,4));m.mesh.selection_edges={'one':a,'same':a};m.mesh.provenance_edges={'p':a}
    assert reuse._array_bytes(m)==old+a.nbytes


def test_refined_mesh_limit_is_not_hidden_by_warm_nominal(monkeypatch):
    from meshine.refine import MeshSizeLimitError
    calls=[];nominal=cross();refined=changed('edge_size')
    def make(self,**options):
        calls.append(options)
        if options['edge_size']!=nominal.mesh_options['edge_size']:
            raise MeshSizeLimitError('original mesh limit')
        return small_mesh()
    monkeypatch.setattr(CrossSection,'mesh',make)
    with reuse._mesh_reuse_scope() as cache:
        get(nominal)
        for _ in range(2):
            with pytest.raises(MeshSizeLimitError,match='original mesh limit'):get(refined)
        get(nominal);assert len(calls)==3 and len(cache)==1


@pytest.mark.parametrize('stage',['mesh','dielectric'])
def test_warm_line_failure_keeps_original_stage_and_current_evidence(monkeypatch,stage):
    from sipi.two_ground_panel_line import TwoGroundPanelLineError
    import sipi.two_ground_panel_line as line
    from test_two_ground_current_reuse import fake_solver
    fake_solver(monkeypatch);fake_mesh(monkeypatch);doc=document('box-8')
    def refuse(*a,**k):raise ArithmeticError('original line refusal')
    with reuse._mesh_reuse_scope():
        get(doc.cross_section)
        if stage=='mesh':monkeypatch.setattr(CrossSection,'mesh',refuse)
        else:monkeypatch.setattr(line,'_dispersive_from_mesh',refuse)
        with pytest.raises(TwoGroundPanelLineError) as info:doc.analyze()
        record=info.value.to_dict()
        assert info.value.stage==stage and info.value.cause_type=='ArithmeticError'
        assert record['message']=='original line refusal' and record['current_solver']
        assert (record['dielectric_mesh'] is None)==(stage=='mesh')


def test_nested_and_concurrent_requests_do_not_share_mutable_entries(monkeypatch):
    _,calls=fake_mesh(monkeypatch)
    with reuse._mesh_reuse_scope() as outer:
        get()
        with reuse._mesh_reuse_scope() as inner:get();get()
        assert not inner and len(outer)==1
        get();assert len(calls)==2
    assert not outer
    barrier=Barrier(2)
    def run():
        with reuse._mesh_reuse_scope() as cache:
            get();barrier.wait(timeout=10);get()
            return id(cache),next(iter(cache.values()))[1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks=[pool.submit(run) for _ in range(2)];a,b=[t.result(timeout=20) for t in tasks]
    assert a[0]!=b[0] and a[1] is not b[1] and len(calls)==4 and reuse._SCOPE.get() is None


@pytest.mark.parametrize('failure',[ValueError,KeyboardInterrupt])
def test_exception_and_interrupt_clear_scope(monkeypatch,failure):
    _,calls=fake_mesh(monkeypatch)
    with pytest.raises(failure):
        with reuse._mesh_reuse_scope() as cache:get();raise failure('leave request')
    assert not cache and reuse._SCOPE.get() is None
    get();assert len(calls)==2


@pytest.mark.parametrize('sampled',[False,True],ids=['single','finite-grid'])
def test_actual_goals_keep_all_results_and_attempts_with_two_meshes(monkeypatch,sampled,record_property):
    import sipi.two_ground_pair_goal as single_module
    import sipi.two_ground_sampled_pair_goal as sampled_module
    from sipi.execution_request import SavedExecutionRequest
    from test_two_ground_pair_goal_document import document as single_document
    from test_two_ground_sampled_pair_goal_document import document as sampled_document,SELECTED
    doc=sampled_document(True,initial=SELECTED,max_evaluations=4) if sampled else single_document(True)
    if not sampled:
        raw=doc.to_dict();raw.update(initial=list(SELECTED),max_evaluations=4);doc=type(doc).from_dict(raw)
    request=SavedExecutionRequest(doc.dumps(),max_evaluations=4)
    original=CrossSection.mesh;calls=[];payloads=[]
    def make(self,**options):
        calls.append(CrossSectionDocument(self,mesh=options).dumps())
        result=original(self,**options);payloads.append(reuse._array_bytes(result));return result
    monkeypatch.setattr(CrossSection,'mesh',make)
    with monkeypatch.context() as context:
        context.setattr(sampled_module if sampled else single_module,'_mesh_reuse_scope',nullcontext)
        uncached=request.run()
    before=list(calls);calls.clear();payloads.clear();cached=request.run();after=list(calls)
    record_property('two_ground_mesh_reuse',json.dumps(dict(uncached=uncached,cached=cached,
        uncached_mesh_inputs=before,cached_mesh_inputs=after,cached_array_payload_bytes=payloads),sort_keys=True))
    assert cached==uncached and cached['execution']['status']=='complete'
    assert cached['execution']['result']['evaluations']==4
    assert len(before)==4 and len(after)==2
    assert before[0]==before[2]==after[0] and before[1]==before[3]==after[1]
    assert sum(payloads)<=reuse._ARRAY_BYTES and reuse._SCOPE.get() is None
