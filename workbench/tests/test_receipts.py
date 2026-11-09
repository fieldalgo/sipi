"""Transport semantic receipts without replacing controls or numerical results."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tests' / 'sipi'))
from engine import execute
from sipi import LumpedNetworkDocument
from sipi.execution import execute_saved
from sipi.execution_request import SavedExecutionRequest
from test_desktop import server, call, finish


def source():
    return LumpedNetworkDocument([0, 1e9], resistance=10,
                                port_names=('입력', '출력')).dumps()


def request(text=None, **options):
    return dict(action='saved-receipt', text=source() if text is None else text, **options)


def controls(**options):
    return dict(max_input_bytes=200*1024, max_evaluations=128, diagnostics=[], **options)


def test_receipt_matches_old_execution_and_repeated_semantic_identity():
    raw = source()
    result = execute(request(raw))
    assert set(result) == {'engine', 'receipt'}
    expected = SavedExecutionRequest(raw, **controls())
    assert result['receipt'] == expected.run()
    assert result['receipt']['execution'] == execute(dict(action='saved-analyze', text=raw))['execution']
    assert execute(request(raw)) == result  # Not a unique run ID or artifact declaration.
    assert set(result['engine']) == {'sipi'}


def test_complete_external_controls_and_formatting_preserve_identity():
    raw = json.dumps(json.loads(source()), ensure_ascii=False, separators=(',', ':'))
    values = dict(max_input_bytes=262144, max_evaluations=72, diagnostics=[])
    expected = SavedExecutionRequest(raw, **values)
    out = execute(request(raw, controls=values))['receipt']
    assert out == expected.run() and out['request']['controls'] == values
    assert execute(request(source(), controls=values))['receipt']['request'] == out['request']
    assert out['request']['request_id'] != execute(request(raw))['receipt']['request']['request_id']
    assert values == dict(max_input_bytes=262144, max_evaluations=72, diagnostics=[])


@pytest.mark.parametrize('bad', [None, {}, [], {'max_evaluations': 4},
    dict(max_input_bytes=True, max_evaluations=4, diagnostics=[]),
    dict(max_input_bytes=262144, max_evaluations=True, diagnostics=[]),
    dict(max_input_bytes=262144, max_evaluations=129, diagnostics=[]),
    dict(max_input_bytes=262144, max_evaluations=10001, diagnostics=[]),
    dict(max_input_bytes=262144, max_evaluations=4, diagnostics=['modes']),
    dict(max_input_bytes=262144, max_evaluations=4, diagnostics=[], extra=1)])
def test_bad_controls_refuse_before_execution(bad, monkeypatch):
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('invalid request executed'))
    with pytest.raises(ValueError):
        execute(request(controls=bad))


@pytest.mark.parametrize('bad', [dict(action='saved-receipt'),
    dict(action='saved-receipt', text='{}', extra=1),
    dict(action='saved-receipt', text=None), dict(action='saved-receipt', text={}),
    dict(action='saved-receipt', text='{"schema":"x","schema":"x"}'),
    dict(action='saved-receipt', text='{"schema":NaN}')])
def test_invalid_requests_refuse_without_execution(bad, monkeypatch):
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('invalid request executed'))
    with pytest.raises(ValueError):
        execute(bad)


def test_raw_utf8_boundary_independent_of_declared_control():
    raw = source()
    raw += ' ' * (200*1024 - len(raw.encode('utf-8')))
    values = dict(max_input_bytes=262144, max_evaluations=128, diagnostics=[])
    out = execute(request(raw, controls=values))['receipt']
    assert out['request'] == SavedExecutionRequest(raw, **values).to_dict()
    with pytest.raises(ValueError, match='200 KiB'):
        execute(request(raw + ' ', controls=values))
    with pytest.raises(ValueError, match='max_input_bytes'):
        execute(request(source(), controls={**values, 'max_input_bytes': len(source().encode('utf-8'))-1}))


def test_encoded_envelope_boundary_before_execution(monkeypatch):
    # Valid JSON whitespace has a short raw form but escapes inside the envelope.
    raw = source()
    value = request(raw)
    size = len(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8'))
    extra = 256*1024 - size
    value['text'] += '\t'*(extra//2) + ' '*(extra%2)
    assert len(value['text'].encode('utf-8')) < 200*1024
    assert len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')) == 256*1024
    out = execute(value)['receipt']
    assert out['request'] == SavedExecutionRequest(value['text'], **controls()).to_dict()
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('oversized request executed'))
    with pytest.raises(ValueError, match='256 KiB'):
        execute({**value, 'text': value['text']+' '})


@pytest.mark.parametrize('fail_at', [None, 2])
def test_complete_and_incomplete_study_history_is_exact(monkeypatch, fail_at):
    from test_sampled_panel_pair_yield import random_document
    from test_sampled_panel_pair_goal import synthetic
    text = random_document().dumps()
    values = dict(max_input_bytes=200*1024, max_evaluations=4, diagnostics=[])
    synthetic(monkeypatch, fail_at=fail_at)
    expected = execute_saved(text, **values)
    synthetic(monkeypatch, fail_at=fail_at)
    out = execute(request(text, controls=values))['receipt']
    assert out['execution'] == expected
    assert expected['status'] == ('incomplete' if fail_at else 'complete')
    if fail_at:
        assert expected['result']['rows'][1]['error'] == 'original failed frequency batch'


def test_goal_failure_preserves_attempts_and_history(monkeypatch):
    from test_sampled_panel_pair_goal_document import document, Document
    from test_sampled_panel_pair_goal import synthetic
    raw = document().to_dict()
    raw['initial'] = [1.35*.3e-3, .8*.2e-3]
    raw['max_evaluations'] = 4
    text = Document.from_dict(raw).dumps()
    values = dict(max_input_bytes=200*1024, max_evaluations=4, diagnostics=[])
    synthetic(monkeypatch, fail_at=2)
    expected = execute_saved(text, **values)
    synthetic(monkeypatch, fail_at=2)
    actual = execute(request(text, controls=values))['receipt']['execution']
    assert actual == expected and actual['status'] == 'failed'
    assert actual['error']['attempts'] == 2 and len(actual['error']['history']) == 1


def test_actual_spawned_http_receipt_recovery(server):
    raw = source()
    expected = execute(request(raw))
    assert call(server, 'POST', '/api/job', request(raw))[0] == 202
    result = finish(server)
    assert result['status'] == 'complete' and result['result'] == expected
    assert call(server, 'POST', '/api/job', request(raw, controls={}))[0] == 202
    assert finish(server)['status'] == 'error'
    assert call(server, 'POST', '/api/job', request(raw))[0] == 202
    assert finish(server)['result'] == expected
