# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exercise real collection, module fixtures, failures and interrupted partitions."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest

TOOLS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_shards', TOOLS / 'check_shards.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def suite(tmp_path):
    (tmp_path / 'tools').mkdir()
    shutil.copy2(TOOLS / 'pytest_shard.py', tmp_path / 'tools/pytest_shard.py')
    (tmp_path / 'tools/shards').mkdir()
    shutil.copy2(TOOLS / 'shards/durations.json', tmp_path / 'tools/shards/durations.json')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    for i in range(12):
        (tmp_path / 'tests' / f'test_module_{i}.py').write_text('''import pytest
from pathlib import Path
@pytest.fixture(scope='module')
def once():
    with Path('fixtures.txt').open('a') as f:f.write(__name__+'\\n')
@pytest.mark.parametrize('value',[0,1,2],ids=['zero','one','two'])
def test_case(once,value):
    assert value>=0
''', encoding='utf-8')
    return tmp_path


def run(root, *args):
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    env.pop('PYTHONPATH', None)
    return subprocess.run([sys.executable, '-m', 'pytest', '-q', *map(str, args)],
                          cwd=root, env=env, capture_output=True, text=True)


def shard(root, index, *args):
    return run(root, 'tests', '-p', 'tools.pytest_shard', '--sipi-shard-count=3',
               f'--sipi-shard-index={index}', f'--sipi-shard-report={index}.json', *args)


@pytest.fixture
def completed(suite):
    plain = run(suite, 'tests', '--junitxml=plain.xml')
    assert plain.returncode == 0, plain.stdout + plain.stderr
    plain_fixtures = (suite / 'fixtures.txt').read_text().splitlines()
    (suite / 'fixtures.txt').unlink()
    reports = []
    for index in range(3):
        result = shard(suite, index, f'--junitxml=part-{index}.xml')
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(json.loads((suite / f'{index}.json').read_text()))
    assert sorted(plain_fixtures) == sorted((suite / 'fixtures.txt').read_text().splitlines())
    def cases(path):
        return {(x.get('classname'), x.get('name')) for x in ET.parse(path).findall('.//testcase')}
    parts = [cases(suite / f'part-{i}.xml') for i in range(3)]
    assert set.union(*parts) == cases(suite / 'plain.xml')
    assert sum(map(len, parts)) == len(cases(suite / 'plain.xml')) == 36
    return suite, reports


def test_full_collection_and_whole_module_fixtures_are_preserved(completed):
    root, reports = completed
    result = checker.verify(reports)
    assert result['cases'] == 36 and result['executed'] and result['partitions'] == 3
    with pytest.raises(ValueError):checker.verify(reports, collect_only=True)
    command = subprocess.run([sys.executable, str(TOOLS / 'check_shards.py'),
                              *[str(root / f'{i}.json') for i in range(3)]], capture_output=True, text=True)
    assert command.returncode == 0 and json.loads(command.stdout) == result


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'changed-collection', 'changed-digest',
    'overlap', 'omission', 'wrong-module', 'unfinished', 'failed', 'collect-only', 'collection-error',
    'other-table', 'old-schema'])
def test_missing_or_incomplete_evidence_never_passes(completed, fault):
    _, reports = completed; reports = copy.deepcopy(reports)
    if fault == 'missing':reports.pop()
    elif fault == 'duplicate':reports[1] = reports[0]
    elif fault == 'changed-collection':reports[1]['all_nodeids'].pop()
    elif fault == 'changed-digest':reports[1]['collection_sha256'] = 'wrong'
    elif fault == 'overlap':reports[1]['selected_nodeids'].append(reports[0]['selected_nodeids'][0])
    elif fault == 'omission':reports[1]['selected_nodeids'].pop()
    elif fault == 'wrong-module':reports[1]['selected_nodeids'], reports[0]['selected_nodeids'] = reports[0]['selected_nodeids'], reports[1]['selected_nodeids']
    elif fault == 'unfinished':reports[1]['completed_nodeids'].pop()
    elif fault == 'failed':reports[1]['exit_status'] = 1
    elif fault == 'collect-only':reports[1]['collect_only'] = True
    elif fault == 'collection-error':reports[1]['collection_errors'] = 1
    elif fault == 'other-table':reports[1]['durations_sha256'] = '0' * 64
    elif fault == 'old-schema':reports[1]['schema'] = 'sipi.pytest-partition/1'
    with pytest.raises(ValueError):checker.verify(reports)


def test_discovery_only_never_claims_execution(suite):
    reports = []
    for i in range(3):
        result = shard(suite, i, '--collect-only')
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(json.loads((suite / f'{i}.json').read_text()))
    assert not (suite / 'fixtures.txt').exists()
    assert checker.verify(reports, collect_only=True)['executed'] is False
    with pytest.raises(ValueError):checker.verify(reports)


@pytest.mark.parametrize('extra', [['--sipi-shard-index=3'], ['--sipi-shard-count=0'],
    ['-k', 'case'], ['-m', 'slow'], ['--deselect=tests/test_module_0.py::test_case[zero]']])
def test_invalid_or_partial_selection_is_rejected_before_execution(suite, extra):
    result = shard(suite, 0, *extra)
    assert result.returncode != 0 and not (suite / 'fixtures.txt').exists()


def test_existing_evidence_is_preserved(suite):
    (suite / '0.json').write_text('original failure', encoding='utf-8')
    result = shard(suite, 0)
    assert result.returncode != 0 and (suite / '0.json').read_text() == 'original failure'
    assert not (suite / 'fixtures.txt').exists()


@pytest.mark.parametrize('stop', [False, True])
def test_real_failure_is_retained_and_never_reported_as_pass(suite, stop):
    for path in (suite / 'tests').glob('*.py'):
        path.write_text(path.read_text().replace('assert value>=0', 'assert value != 0'), encoding='utf-8')
    result = shard(suite, 0, '--junitxml=failure.xml', *(['-x'] if stop else []))
    assert result.returncode == 1
    report = json.loads((suite / '0.json').read_text())
    assert report['exit_status'] == 1 and ET.parse(suite / 'failure.xml').findall('.//failure')
    assert bool(len(report['completed_nodeids']) < len(report['selected_nodeids'])) is stop


def test_collection_error_and_empty_shard_are_not_success(suite):
    (suite / 'tests/test_broken.py').write_text('raise RuntimeError("collection failure")', encoding='utf-8')
    result = shard(suite, 0)
    assert result.returncode != 0
    report = json.loads((suite / '0.json').read_text())
    assert report['collection_errors'] > 0 and report['exit_status'] != 0
    assert not report['completed_nodeids']
    # All parameterizations of a single module must stay together; empty parts fail.
    for path in (suite / 'tests').glob('*.py'):
        if path.name != 'test_module_0.py':path.unlink()
    (suite / '0.json').unlink()
    results = [shard(suite, i) for i in range(3)]
    assert sorted(result.returncode for result in results) == [0, 4, 4]
