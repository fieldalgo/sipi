# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""CLI dispatch is explicit; the actual installed host is checked separately."""
import sys
from types import ModuleType
import pytest
from sipi import cli


@pytest.mark.parametrize('arguments,expected', [([], []), (['gui'], ['--port', '0']),
    (['gui', '--no-browser'], ['--port', '0', '--no-browser']),
    (['gui', '--port', '12345'], ['--port', '12345'])])
def test_default_and_explicit_ui_dispatch_to_same_host(monkeypatch, arguments, expected):
    host = ModuleType('sipi._workbench.main'); calls = []
    host.main = lambda argv: calls.append(argv)
    monkeypatch.setitem(sys.modules, host.__name__, host)
    assert cli.main(arguments) == 0 and calls == [expected]


@pytest.mark.parametrize('arguments', [['gui','--port','-1'], ['gui','--port','65536'],
    ['gui','--port','bad'], ['run','-','--no-browser'], ['validate','-','--port','0']])
def test_invalid_ui_options_do_not_start_a_host(monkeypatch, capsys, arguments):
    monkeypatch.setattr(cli, '_launch_gui', lambda *a: pytest.fail('invalid args launched UI'))
    with pytest.raises(SystemExit) as caught: cli.main(arguments)
    assert caught.value.code == 2 and not capsys.readouterr().out


@pytest.mark.parametrize('arguments', [['--help'], ['--version'], ['gui','--help']])
def test_help_and_version_do_not_launch(monkeypatch, capsys, arguments):
    monkeypatch.setattr(cli, '_launch_gui', lambda *a: pytest.fail('help launched UI'))
    with pytest.raises(SystemExit) as caught: cli.main(arguments)
    assert caught.value.code == 0 and capsys.readouterr().out


def test_missing_built_assets_give_actionable_error(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'sipi._workbench.main', None)
    assert cli.main([]) == 1
    output = capsys.readouterr(); assert not output.out and 'Install a built SIPI wheel' in output.err


def test_startup_error_is_not_reported_as_a_success(monkeypatch, capsys):
    host = ModuleType('sipi._workbench.main')
    def fail(argv): raise OSError('port unavailable')
    host.main = fail; monkeypatch.setitem(sys.modules, host.__name__, host)
    assert cli.main(['gui','--no-browser']) == 1
    assert 'port unavailable' in capsys.readouterr().err
