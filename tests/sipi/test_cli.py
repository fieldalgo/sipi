# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sipi import CrossSection, LumpedNetworkDocument, ImpedanceDesignDocument
from sipi import cli
from sipi.execution_request import SavedExecutionRequest
from test_execution import documents, cross, lumped


def input_file(tmp_path, text):
    path = tmp_path / '입력.json'
    path.write_text(text, encoding='utf-8')
    return path


def test_every_input_validates_canonically_without_fields(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(CrossSection, 'mesh', lambda *a, **k: pytest.fail('validation solved fields'))
    count = 0
    for doc in documents():
        assert cli.main(['validate', str(input_file(tmp_path, doc.dumps()))]) == 0
        captured = capsys.readouterr()
        assert captured.out == doc.dumps() + '\n' and captured.err == ''
        count += 1
    assert count == 109


@pytest.mark.parametrize('doc', [lumped, cross])
def test_actual_run_matches_existing_receipt_and_file_stdout(tmp_path, capsys, doc):
    text = doc().dumps(); source = input_file(tmp_path, text)
    expected = SavedExecutionRequest(text).run()
    assert cli.main(['run', str(source)]) == 0
    captured = capsys.readouterr(); assert not captured.err
    assert json.loads(captured.out) == expected
    target = tmp_path / '결과.json'
    assert cli.main(['run', str(source), '--output', str(target)]) == 0
    assert target.read_bytes() == captured.out.encode('utf-8')
    assert capsys.readouterr().out == '' and source.read_text() == text
    assert not list(tmp_path.glob('.sipi-result-*'))


def test_utf8_stdin_byte_boundary_and_canonical_expansion(tmp_path, monkeypatch, capsys):
    raw = LumpedNetworkDocument([0, 1e9], resistance=10, port_names=('입력', '출력')).to_dict()
    text = json.dumps(raw, ensure_ascii=False, separators=(',', ':')); data = text.encode('utf-8')
    assert len(data) > len(text)
    for command in ['run', 'validate']:
        monkeypatch.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(data), encoding='utf-8'))
        assert cli.main([command, '-', '--max-input-bytes', str(len(data))]) == 0
        output = capsys.readouterr(); assert '입력' in output.out and not output.err
        monkeypatch.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(data), encoding='utf-8'))
        assert cli.main([command, '-', '--max-input-bytes', str(len(data)-1)]) == 2
        output = capsys.readouterr(); assert not output.out and 'max_input_bytes' in output.err


@pytest.mark.parametrize('text', ['[]', '{}', 'null', '{"schema":"unknown"}',
    '{"schema":"x","schema":"x"}', '{"a":NaN}', '{"a":1e999}', '\ufeff{}'])
def test_invalid_input_does_not_publish(tmp_path, capsys, text):
    target = tmp_path / 'result.json'
    assert cli.main(['run', str(input_file(tmp_path, text)), '--output', str(target)]) == 2
    assert not target.exists() and 'input:' in capsys.readouterr().err


@pytest.mark.parametrize('options', [['--max-evaluations','1'], ['--max-evaluations','10001'],
    ['--diagnostic','modes','--diagnostic','modes'], ['--diagnostic','modes']])
def test_invalid_controls_reject_before_execution(tmp_path, monkeypatch, capsys, options):
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('invalid controls executed'))
    assert cli.main(['run', str(input_file(tmp_path, lumped().dumps())), *options]) == 2
    assert not capsys.readouterr().out


@pytest.mark.parametrize('value', ['0', '-1', '67108865', 'bad'])
def test_usage_input_limit_is_bounded(value, capsys):
    with pytest.raises(SystemExit) as caught: cli.main(['run', '-', '--max-input-bytes', value])
    assert caught.value.code == 2 and not capsys.readouterr().out


def test_unreadable_or_non_utf8_input(tmp_path, capsys):
    source = tmp_path / 'input.json'
    assert cli.main(['run', str(source)]) == 2
    source.write_bytes(b'\xff')
    assert cli.main(['run', str(source)]) == 2
    assert not capsys.readouterr().out


def test_failed_goal_keeps_real_solver_history(tmp_path, capsys):
    doc = ImpedanceDesignDocument('stripline', dict(width=.0005, plane_spacing=.001, eps_r=4),
        variable='width', bounds=[.00045, .00055], target=500, max_evaluations=3,
        mesh=dict(edge_size=8e-6, far_size=.00025, grade=.3))
    expected = SavedExecutionRequest(doc.dumps()).run()
    assert expected['execution']['status'] == 'failed' and expected['execution']['error']['history']
    target = tmp_path / 'failed.json'
    assert cli.main(['run', str(input_file(tmp_path, doc.dumps())), '--output', str(target)]) == 1
    assert json.loads(target.read_text()) == expected and not capsys.readouterr().err


def test_incomplete_study_preserves_original_failed_rows(tmp_path, monkeypatch, capsys):
    from test_sampled_panel_pair_goal import synthetic
    from test_sampled_panel_pair_yield import random_document
    doc = random_document(); synthetic(monkeypatch, fail_at=2)
    expected = SavedExecutionRequest(doc.dumps()).run()
    assert expected['execution']['status'] == 'incomplete'
    synthetic(monkeypatch, fail_at=2)
    assert cli.main(['run', str(input_file(tmp_path, doc.dumps()))]) == 1
    assert json.loads(capsys.readouterr().out) == expected


def test_runtime_exception_and_interrupt_do_not_invent_receipts(tmp_path, monkeypatch, capsys):
    source = input_file(tmp_path, lumped().dumps()); target = tmp_path / 'result.json'
    for error, code in [(ArithmeticError('original failure'), 1), (KeyboardInterrupt(), 130)]:
        def fail(*a): raise error
        monkeypatch.setattr(SavedExecutionRequest, 'run', fail)
        assert cli.main(['run', str(source), '--output', str(target)]) == code
        assert not target.exists() and not capsys.readouterr().out


def test_existing_output_refuses_before_any_calculation(tmp_path, monkeypatch, capsys):
    source = input_file(tmp_path, lumped().dumps())
    monkeypatch.setattr(SavedExecutionRequest, 'run', lambda *a: pytest.fail('output conflict calculated'))
    assert cli.main(['run', str(source), '--output', str(source)]) == 3
    assert source.read_text() == lumped().dumps() and 'already exists' in capsys.readouterr().err


def test_output_directory_is_not_created(tmp_path, capsys):
    source = input_file(tmp_path, lumped().dumps()); target = tmp_path / 'missing' / 'out.json'
    assert cli.main(['validate', str(source), '--output', str(target)]) == 3
    assert not target.parent.exists() and 'No result was published' in capsys.readouterr().err


@pytest.mark.parametrize('phase', ['write', 'fsync', 'publish'])
def test_failed_publication_cleans_temp_without_creating_target(tmp_path, monkeypatch, phase):
    def fail(*a, **k): raise OSError('injected ' + phase)
    if phase == 'write':
        create = cli.tempfile.NamedTemporaryFile
        def failed_stream(*a, **k):
            stream = create(*a, **k); stream.write = fail; return stream
        monkeypatch.setattr(cli.tempfile, 'NamedTemporaryFile', failed_stream)
    else:
        monkeypatch.setattr(cli.os, 'fsync' if phase == 'fsync' else 'link', fail)
    target = tmp_path / 'result.json'
    with pytest.raises(cli._OutputError) as caught: cli._write_output(target, '{}\n')
    assert not caught.value.published and not target.exists()
    assert not list(tmp_path.glob('.sipi-result-*'))


def test_cleanup_failure_reports_published_file_and_keeps_complete_bytes(tmp_path, monkeypatch):
    unlink = Path.unlink
    def fail(path, *a, **k):
        if path.name.startswith('.sipi-result-'): raise OSError('injected cleanup')
        return unlink(path, *a, **k)
    monkeypatch.setattr(Path, 'unlink', fail); target = tmp_path / 'result.json'
    with pytest.raises(cli._OutputError, match='was published') as caught: cli._write_output(target, '{"a":1}\n')
    assert caught.value.published and target.read_bytes() == b'{"a":1}\n'
    for p in tmp_path.glob('.sipi-result-*'): unlink(p)


def test_no_clobber_under_concurrent_publishers(tmp_path):
    gate = Barrier(2); target = tmp_path / 'result.json'
    def write(value):
        gate.wait()
        try: cli._write_output(target, value); return ('saved', value)
        except cli._OutputError as exc: assert not exc.published; return ('conflict', value)
    with ThreadPoolExecutor(2) as pool: results = list(pool.map(write, ['first', 'second']))
    assert sorted(a for a, b in results) == ['conflict', 'saved']
    assert target.read_text() == next(b for a, b in results if a == 'saved')
    assert not list(tmp_path.glob('.sipi-result-*'))


def test_existing_symlink_is_not_followed_or_replaced(tmp_path, capsys):
    source = input_file(tmp_path, lumped().dumps()); target = tmp_path / 'result.json'
    target.symlink_to(tmp_path / 'absent')
    assert cli.main(['validate', str(source), '--output', str(target)]) == 3
    assert target.is_symlink() and not target.exists() and not capsys.readouterr().out


def test_commands_do_not_start_hosts_or_change_directory(tmp_path, monkeypatch, capsys):
    import socket, webbrowser
    def forbidden(*a, **k): pytest.fail('CLI started a network/browser host')
    monkeypatch.setattr(socket, 'socket', forbidden); monkeypatch.setattr(webbrowser, 'open', forbidden)
    before = Path.cwd()
    assert cli.main(['run', str(input_file(tmp_path, lumped().dumps()))]) == 0
    assert Path.cwd() == before and json.loads(capsys.readouterr().out)['schema'] == 'sipi.execution-receipt/1'


def test_python_module_entrypoint_outside_checkout(tmp_path):
    source = input_file(tmp_path, lumped().dumps())
    result = subprocess.run([sys.executable, '-m', 'sipi', 'validate', str(source)],
                            cwd=tmp_path, capture_output=True, check=False)
    assert result.returncode == 0 and result.stdout == (lumped().dumps()+'\n').encode()
    assert not result.stderr


def test_closed_output_pipe_keeps_documented_exit_code(tmp_path):
    source = input_file(tmp_path, lumped().dumps())
    process = subprocess.Popen([sys.executable, '-m', 'sipi', 'validate', str(source)],
                               cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    process.stdout.close()
    error = process.stderr.read()
    assert process.wait(timeout=20) == 3, error.decode()
    assert b'sipi: output:' in error


def test_complete_fit_retains_separate_rejected_sample_acceptance(tmp_path, capsys):
    from test_tensor_dielectric_fit_document import document
    doc = document(mismatch=True)
    assert cli.main(['run', str(input_file(tmp_path, doc.dumps()))]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['execution']['status'] == 'complete'
    assert output['execution']['result']['accepted'] is False
    assert output == SavedExecutionRequest(doc.dumps()).run()


def test_valid_execution_controls_and_diagnostics_are_preserved(tmp_path, capsys):
    from test_execution import line
    doc = line()
    assert cli.main(['run', str(input_file(tmp_path, doc.dumps())), '--max-evaluations', '20',
                     '--diagnostic', 'modes', '--diagnostic', 'characteristic']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output == SavedExecutionRequest(doc.dumps(), max_evaluations=20,
                         diagnostics=['modes', 'characteristic']).run()
