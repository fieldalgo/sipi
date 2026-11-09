# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Project reopening, A/B isolation and explicit result selection contracts."""
from dataclasses import FrozenInstanceError
import copy
import hashlib
import json
import numpy as np
import pytest

from sipi import CrossSection, LumpedNetworkDocument
from sipi.execution import normalize_saved, saved_schemas
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

# Synthetic test metadata, not a claim about installed artifacts.
ARTIFACTS = [dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)]


def request(resistance=10, **controls):
    return SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=resistance,
                                  port_names=('입력', '출력')).dumps(), **controls)


def project(req=None, **options):
    return SavedProject(request() if req is None else req, project_id='project:1',
                        design_id='a', title='선로 비교', label='기준', **options)


def record(req, run_id='run:1'):
    return SavedExecutionRecord(req, req.run(), run_id=run_id, artifacts=ARTIFACTS)


def rehash(data):
    body = {k: v for k, v in data.items() if k != 'content_sha256'}
    data['content_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return data


def test_real_ab_save_reopen_and_explicit_replay():
    a = request(10)
    first = project(a).attach_record('a', record(a, 'run:a'), select=True)
    duplicate = first.duplicate_design('a', 'b', '대안')
    assert duplicate.design('b')['records'] == [] and duplicate.current_record('b') is None
    b = request(20)
    edited = duplicate.update_design('b', b)
    completed = edited.attach_record('b', record(b, 'run:b'), select=True)
    restored = SavedProject.loads(completed.dumps())
    assert restored.dumps() == completed.dumps() and restored.design_ids == ('a', 'b')
    assert restored.current_record('a').receipt == a.run()
    assert restored.current_record('b').receipt == b.run()
    assert restored.current_record('a').receipt['execution']['result'] != restored.current_record('b').receipt['execution']['result']
    assert restored.prepare('b').run() == restored.current_record('b').receipt
    assert first.design_ids == ('a',) and first.prepare('a').to_dict() == a.to_dict()


@pytest.mark.parametrize('change', ['geometry', 'budget', 'byte_cap'])
def test_semantic_change_clears_selection_but_preserves_history(change):
    a = request()
    saved = record(a)
    first = project(a).attach_record('a', saved, select=True)
    updated = {'geometry': request(11), 'budget': request(max_evaluations=64),
               'byte_cap': request(max_input_bytes=100000)}[change]
    edited = first.update_design('a', updated, label='수정')
    assert edited.current_record('a') is None
    assert edited.design('a')['records'] == [saved.to_dict()]
    assert first.current_record('a').dumps() == saved.dumps()
    assert SavedProject.loads(edited.dumps()).current_record('a') is None
    with pytest.raises(ValueError, match='current design request'):
        edited.select_record('a', saved.run_id)


def test_source_formatting_change_keeps_semantic_selection_and_exact_source():
    a = request()
    before = project(a).attach_record('a', record(a), select=True)
    text = json.dumps(json.loads(a.source_text), ensure_ascii=False, separators=(',', ':'))
    changed = SavedExecutionRequest(text, **a.controls)
    assert changed.request_id == a.request_id and changed.source_text != a.source_text
    after = before.update_design('a', changed)
    assert after.current_record('a').run_id == 'run:1'
    assert SavedProject.loads(after.dumps()).prepare('a').source_text == text
    assert after.current_record('a').prepare().source_text == a.source_text


def test_late_response_is_history_only_and_never_implicitly_latest():
    a, b = request(10), request(20)
    first = project(a)
    old_response = record(a, 'old')
    edited = first.update_design('a', b).attach_record('a', record(b, 'new'), select=True)
    late = edited.attach_record('a', old_response)
    assert late.current_record('a').run_id == 'new'
    assert [r['run_id'] for r in late.design('a')['records']] == ['new', 'old']
    with pytest.raises(ValueError, match='current design request'):
        edited.attach_record('a', old_response, select=True)
    assert len(edited.design('a')['records']) == 1


def test_identical_repeated_requests_still_need_explicit_run_selection():
    a = request()
    first = project(a).attach_record('a', record(a, 'one'), select=True)
    two = first.attach_record('a', record(a, 'two'))
    assert two.current_record('a').run_id == 'one'
    assert two.select_record('a', 'two').current_record('a').run_id == 'two'
    assert two.select_record('a', None).current_record('a') is None
    assert two.current_record('a').run_id == 'one'


def test_selection_is_scoped_to_design_and_run_ids_are_globally_unique():
    a = request()
    first = project(a).attach_record('a', record(a), select=True).duplicate_design('a', 'b', 'B')
    with pytest.raises(ValueError, match='in this design'):
        first.select_record('b', 'run:1')
    with pytest.raises(ValueError, match='unique across'):
        first.attach_record('b', record(a))
    with pytest.raises(ValueError, match='unique across'):
        first.attach_record('a', record(a))


def test_explicit_removal_preserves_original_and_cannot_leave_empty_project():
    a = request()
    first = project(a).attach_record('a', record(a), select=True).duplicate_design('a', 'b', 'B')
    removed = first.remove_record('a', 'run:1')
    assert removed.current_record('a') is None and removed.design('a')['records'] == []
    assert first.current_record('a') is not None
    one = removed.remove_design('b')
    assert one.design_ids == ('a',)
    with pytest.raises(ValueError, match='1..64'):
        one.remove_design('a')
    with pytest.raises(ValueError, match='not in this design'):
        one.remove_record('a', 'missing')


def test_load_edit_and_prepare_do_not_execute_mesh_optimize_or_access_files(monkeypatch):
    import sipi.tensor_dielectric_fit as fitting
    a = request()
    original = project(a).attach_record('a', record(a), select=True)
    text = original.dumps()
    def forbidden(*args, **kwargs):
        pytest.fail('project operation executed computation or file I/O')
    monkeypatch.setattr(SavedExecutionRequest, 'run', forbidden)
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(fitting, 'nnls', forbidden)
    monkeypatch.setattr(np.linalg, 'svd', forbidden)
    monkeypatch.setattr('builtins.open', forbidden)
    restored = SavedProject.loads(text)
    assert restored.prepare('a').to_dict() == a.to_dict()
    assert restored.current_record('a').run_id == 'run:1'
    assert restored.duplicate_design('a', 'b', 'B').prepare('b').to_dict() == a.to_dict()
    assert restored.dumps() == text


def test_all_registered_inputs_are_projects_without_execution(monkeypatch):
    from test_execution import documents
    docs = documents()
    assert len(docs) == len(saved_schemas()) == 109
    def forbidden(*args, **kwargs):
        pytest.fail('project preparation executed fields')
    monkeypatch.setattr(SavedExecutionRequest, 'run', forbidden)
    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    for doc in docs:
        req = SavedExecutionRequest(doc.dumps())
        saved = project(req)
        assert SavedProject.loads(saved.dumps()).prepare('a').to_dict() == req.to_dict()
    with pytest.raises(ValueError):
        normalize_saved(saved.dumps())


@pytest.mark.parametrize('status', ['complete', 'incomplete', 'failed'])
def test_structural_history_statuses_are_not_relabelled(status):
    req = request()
    # Structural fixtures, not a claim that these calculations ran.
    result = None if status == 'failed' else {'accepted': False, 'failed_rows': [1, 2]}
    error = {'type': 'NotExecutedFixture', 'message': 'fixture only', 'history': [3, 4]} if status == 'failed' else None
    receipt = dict(schema='sipi.execution-receipt/1', request=req.to_dict(), execution=dict(
        schema='sipi.execution/1', input=req.to_dict()['input'], status=status, result=result, error=error))
    saved = SavedExecutionRecord(req, receipt, run_id=status, artifacts=ARTIFACTS)
    restored = SavedProject.loads(project(req).attach_record('a', saved, select=True).dumps())
    assert restored.current_record('a').receipt == receipt


def test_detached_snapshot_and_frozen_fields():
    p = project()
    data = p.to_dict()
    data['designs'][0]['controls']['max_evaluations'] = 3
    d = p.design('a')
    d['records'].append({})
    assert p.prepare('a').max_evaluations == 128 and p.design('a')['records'] == []
    with pytest.raises(FrozenInstanceError):
        p._data_json = '{}'
    copy_loaded = SavedProject.from_dict(p.to_dict())
    assert copy_loaded.dumps() == p.dumps()


def test_original_utf8_input_cap_and_project_exact_cap():
    source = json.dumps(json.loads(request().source_text), ensure_ascii=False, separators=(',', ':'))
    req = SavedExecutionRequest(source, max_input_bytes=len(source.encode()))
    assert len(req.input_json.encode()) > req.max_input_bytes
    p = project(req).attach_record('a', record(req), select=True)
    text = p.dumps()
    n = len(text.encode())
    restored = SavedProject.loads(text, max_project_bytes=n)
    assert restored.prepare('a').source_text == source and restored.current_record('a').receipt == req.run()
    with pytest.raises(ValueError, match='max_project_bytes'):
        SavedProject.loads(text, max_project_bytes=n-1)
    with pytest.raises(ValueError, match='max_project_bytes'):
        SavedProject.loads(' '+text, max_project_bytes=n)
    with pytest.raises(ValueError, match='max_project_bytes'):
        restored.duplicate_design('a', 'b', 'B')
    assert restored.remove_record('a', 'run:1').prepare('a').source_text == source


def test_design_and_record_count_boundaries_are_admitted_exactly():
    req = request()
    p = project(req)
    data = p.to_dict()
    base = copy.deepcopy(data['designs'][0])
    data['designs'] = [dict(copy.deepcopy(base), design_id=f'd{i}') for i in range(64)]
    accepted = SavedProject.from_dict(rehash(data))
    assert len(accepted.design_ids) == 64
    with pytest.raises(ValueError, match='1..64'):
        accepted.add_design('extra', 'Extra', req)
    receipt = req.run()
    records = [SavedExecutionRecord(req, receipt, run_id=f'r{i}', artifacts=ARTIFACTS).to_dict() for i in range(128)]
    data = p.to_dict()
    data['designs'][0]['records'] = records
    accepted = SavedProject.from_dict(rehash(data))
    assert len(accepted.design('a')['records']) == 128
    with pytest.raises(ValueError, match='128'):
        accepted.attach_record('a', record(req, 'extra'))
    assert len(accepted.remove_record('a', 'r0').attach_record('a', record(req, 'extra')).design('a')['records']) == 128


def test_content_hash_detects_mutation_but_is_not_authentication():
    raw = project().to_dict()
    raw['title'] = 'Changed'
    with pytest.raises(ValueError, match='digest mismatch'):
        SavedProject.from_dict(raw)
    # Recomputing the checksum creates valid changed content, not a trusted signature.
    assert SavedProject.from_dict(rehash(raw)).to_dict()['title'] == 'Changed'


def test_nested_record_tamper_is_rejected_even_with_new_project_checksum():
    req = request()
    raw = project(req).attach_record('a', record(req), select=True).to_dict()
    raw['designs'][0]['records'][0]['artifacts']['items'][0]['version'] = 'altered'
    with pytest.raises(ValueError, match='digest mismatch'):
        SavedProject.from_dict(rehash(raw))


@pytest.mark.parametrize('bad', [0, -1, True, 1.0, None, 64*1024*1024+1])
def test_reject_invalid_project_limits(bad):
    with pytest.raises(ValueError):
        project(max_project_bytes=bad)


@pytest.mark.parametrize('target,value', [
    ('schema', 'sipi.project/2'), ('project_id', ''), ('project_id', 'bad id'),
    ('project_id', 1), ('project_id', 'a'*129), ('title', ''), ('title', ' '),
    ('title', 'x\ny'), ('title', '\x7f'), ('title', '한'*171),
    ('designs', []), ('designs', {}), ('designs', [None]),
])
def test_reject_invalid_project_structure(target, value):
    raw = project().to_dict()
    raw[target] = value
    with pytest.raises(ValueError):
        SavedProject.from_dict(rehash(raw))


@pytest.mark.parametrize('target,value', [
    ('design_id', ''), ('design_id', True), ('design_id', 'a'*129),
    ('label', ''), ('label', 'x\ty'), ('label', '한'*86),
    ('source_text', '{}'), ('source_text', 1), ('controls', {}),
    ('records', {}), ('records', [None]), ('selected_run_id', True),
    ('selected_run_id', 'missing'),
])
def test_reject_invalid_design_structure(target, value):
    raw = project().to_dict()
    raw['designs'][0][target] = value
    with pytest.raises(ValueError):
        SavedProject.from_dict(rehash(raw))


@pytest.mark.parametrize('where', ['project', 'design', 'controls'])
def test_reject_unknown_keys(where):
    raw = project().to_dict()
    objects = {'project': raw, 'design': raw['designs'][0], 'controls': raw['designs'][0]['controls']}
    objects[where]['unknown'] = 1
    with pytest.raises(ValueError):
        SavedProject.from_dict(rehash(raw))


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '1e999'])
def test_reject_nonfinite_and_duplicate_json(bad):
    text = project().dumps()
    with pytest.raises(ValueError):
        SavedProject.loads(text.replace('"title":', f'"bad":{bad},"title":'))
    with pytest.raises(ValueError):
        SavedProject.loads(text.replace('"title":', '"title":"duplicate","title":'))


def test_input_argument_validation_and_duplicate_design_ids():
    p = project()
    with pytest.raises(ValueError):
        p.add_design('a', 'Duplicate', request())
    for operation in [lambda: p.design([]), lambda: p.prepare('missing'),
                      lambda: p.update_design('a', {}), lambda: p.add_design('b', 'B', {}),
                      lambda: p.attach_record('a', {}),
                      lambda: p.attach_record('a', record(request()), select=1),
                      lambda: SavedProject.loads(None)]:
        with pytest.raises(ValueError):
            operation()
