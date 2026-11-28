# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The recorded per-platform durations and the time-balanced partition plans built from them."""
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys
import pytest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parent
spec = importlib.util.spec_from_file_location('pytest_shard_plan', TOOLS / 'pytest_shard.py')
shard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shard)
COUNT = 24  # .github/workflows/validate.yml matrix and coverage job
TABLES = [shard.table_path(name) for name in shard.TABLES]
WORKFLOW = (ROOT / '.github/workflows/validate.yml').read_text(encoding='utf-8')


def test_every_platform_has_a_table_and_the_workflow_uses_them_with_the_count():
    assert sorted(path.name for path in shard.SHARDS.iterdir()) == sorted(path.name for path in TABLES)
    assert f'--sipi-shard-count={COUNT} ' in WORKFLOW and f'--shard-count={COUNT} ' in WORKFLOW
    assert f'for i in range({COUNT})' in WORKFLOW
    assert 'shard: [' + ', '.join(map(str, range(COUNT))) + ']' in WORKFLOW
    assert "{'ubuntu-latest': 'linux', 'macos-15': 'darwin', 'windows-latest': 'win32'}" in WORKFLOW
    assert "'--durations-table', table" in WORKFLOW


@pytest.mark.parametrize('path', TABLES, ids=shard.TABLES)
def test_the_stored_table_has_its_source_command_and_sorted_unit_seconds(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    assert list(data) == ['source', 'command', 'split', 'seconds']
    assert 'run' in data['source'] and data['command'].startswith('python tools/pytest_shard.py --table')
    seconds, split = shard.load_table(path)
    assert list(seconds) == sorted(seconds) and split == sorted(split)
    assert all(shard.module_of(name).startswith(('tests/', 'integration/')) for name in seconds)
    # A module removed since the recorded run only adds its estimate to one part; refresh the
    # table with --update when this grows.
    missing = [name for name in seconds if not (ROOT / shard.module_of(name)).is_file()]
    assert len(missing) <= len(seconds) // 10, missing
    # Only modules whose cases do not share an expensive module fixture are split.
    assert split == ['tests/sipi/test_two_ground_harmonic_guard_corner_face_panel_line.py',
                     'tests/sipi/test_two_ground_harmonic_three_active_corner_face_panel_line.py']


@pytest.mark.parametrize('table', [{'source': 'x', 'split': [], 'seconds': {'tests/a.py': 1}},
    {'source': 'x', 'command': 'c', 'seconds': {'tests/a.py': 1}},
    {'source': '', 'command': 'c', 'split': [], 'seconds': {'tests/a.py': 1}},
    {'source': 'x', 'command': 'c', 'split': [], 'seconds': {}},
    {'source': 'x', 'command': 'c', 'split': [], 'seconds': {'tests/a.py': -1}},
    {'source': 'x', 'command': 'c', 'split': [], 'seconds': {'tests/a.py': True}},
    {'source': 'x', 'command': 'c', 'split': [], 'seconds': {'tests\\a.py': 1}},
    {'source': 'x', 'command': 'c', 'split': [], 'seconds': {'tests/a.py::test': 1}},
    {'source': 'x', 'command': 'c', 'split': ['tests/a.py'], 'seconds': {'tests/a.py': 1}},
    {'source': 'x', 'command': 'c', 'split': ['tests/a.py', 'tests/a.py'], 'seconds': {'tests/a.py::t': 1}},
    {'source': 'x', 'command': 'c', 'split': 'tests/a.py', 'seconds': {'tests/a.py::t': 1}}])
def test_malformed_tables_are_refused(tmp_path, table):
    path = tmp_path / 'durations.json'
    path.write_text(json.dumps(table), encoding='utf-8')
    with pytest.raises(ValueError):
        shard.load_table(path)


def test_largest_first_to_the_least_loaded_part_with_names_breaking_ties():
    seconds = {'tests/a.py': 10.0, 'tests/b.py': 2.0, 'tests/c.py': 4.0, 'tests/d.py': 4.0}
    # a (10) -> 0; c (4) -> 1; d (4) -> 1 (4 < 10); b (2) -> 1 (8 < 10).
    assert shard.balance(seconds, 2) == {'tests/a.py': 0, 'tests/c.py': 1, 'tests/d.py': 1, 'tests/b.py': 1}
    assert set(shard.balance(seconds, 1).values()) == {0}


@pytest.mark.parametrize('path', TABLES, ids=shard.TABLES)
def test_the_plan_depends_only_on_the_table_and_count(path):
    seconds = shard.load_durations(path)
    plan = shard.balance(seconds, COUNT)
    for seed in range(3):
        items = list(seconds.items())
        random.Random(seed).shuffle(items)
        assert shard.balance(dict(items), COUNT) == plan
    assert set(plan) == set(seconds) and set(plan.values()) == set(range(COUNT))


def test_unlisted_modules_keep_the_stable_path_hash(tmp_path):
    path = tmp_path / 'durations.json'
    path.write_text(json.dumps({'source': 'x', 'command': 'c', 'split': ['tests/s.py'],
                                'seconds': {'tests/a.py': 5, 'tests/s.py::one': 9, 'tests/s.py::two': 8}}),
                    encoding='utf-8')
    for name in ('tests/new_one.py', 'integration/test_other.py'):
        assert shard.partition(name + '::test[0]', 7, path) == shard.hashed(name, 7)
    assert shard.partition('tests\\a.py::test', 7, path) == 2
    # Split cases are units of their own, also with Windows separators; a new case keeps its own hash.
    assert shard.partition('tests/s.py::one', 7, path) == 0 and shard.partition('tests\\s.py::two', 7, path) == 1
    assert shard.partition('tests/s.py::three', 7, path) == shard.hashed('tests/s.py::three', 7)


@pytest.mark.parametrize('count', [16, COUNT])
@pytest.mark.parametrize('path', TABLES, ids=shard.TABLES)
def test_the_stored_table_balances_the_parts(path, count):
    seconds = shard.load_durations(path)
    plan = shard.balance(seconds, count)
    load = [sum(seconds[m] for m, i in plan.items() if i == part) for part in range(count)]
    # Largest first: no part exceeds the even share by more than the largest module.
    assert max(load) <= sum(load) / count + max(seconds.values())
    assert min(load) > 0


@pytest.mark.parametrize('path', TABLES, ids=shard.TABLES)
def test_no_unit_is_much_longer_than_a_part_of_the_suite(path):
    # Whole units are assigned, so a unit far above a part of the suite sets the run's floor;
    # split a module without shared expensive fixtures, or move a study out of the regular
    # suite, instead. On macOS one conductor module (34 min) is just above a 24th (32 min).
    seconds = shard.load_durations(path)
    assert max(seconds.values()) <= 1.1 * sum(seconds.values()) / COUNT, max(seconds, key=seconds.get)


def test_digest_ignores_line_endings_but_not_content(tmp_path):
    text = json.dumps({'source': 'x', 'command': 'c', 'seconds': {'tests/a.py': 5}}, indent=1) + '\n'
    lf, crlf, other = tmp_path / 'lf.json', tmp_path / 'crlf.json', tmp_path / 'other.json'
    lf.write_bytes(text.encode())
    crlf.write_bytes(text.replace('\n', '\r\n').encode())
    other.write_bytes(text.replace('5', '6').encode())
    assert shard.durations_digest(lf) == shard.durations_digest(crlf) != shard.durations_digest(other)


def update(tmp_path, *args):
    return subprocess.run([sys.executable, str(TOOLS / 'pytest_shard.py'), '--table', 'linux', *map(str, args)],
                          cwd=tmp_path, capture_output=True, text=True)


def test_update_sums_junit_times_per_unit_and_averages_runs(tmp_path):
    (tmp_path / 'tests').mkdir()
    for name in ('test_a.py', 'test_s.py'):
        (tmp_path / 'tests' / name).write_text('', encoding='utf-8')
    xml = tmp_path / 'part.xml'
    xml.write_text('<testsuites><testsuite>'
                   '<testcase classname="tests.test_a" name="one" time="1.25"/>'
                   '<testcase classname="tests.test_a.TestGroup" name="two" time="2"/>'
                   '<testcase classname="tests.test_gone" name="three" time="0.5"/>'
                   '<testcase classname="tests.test_s" name="big[0]" time="10"/>'
                   '<testcase classname="tests.test_s.TestGroup" name="small" time="1"/>'
                   '</testsuite></testsuites>', encoding='utf-8')
    other = tmp_path / 'installed.xml'
    other.write_text('<testsuites><testsuite>'
                     '<testcase classname="tests.test_a" name="one" time="4.75"/>'
                     '<testcase classname="tests.test_s" name="big[0]" time="20"/>'
                     '<testcase classname="integration.test_only" name="x" time="7"/>'
                     '</testsuite></testsuites>', encoding='utf-8')
    output = tmp_path / 'tools/shards/durations.json'
    result = update(tmp_path, '--update', xml, '--update', other, '--split', 'tests/test_s.py',
                    '--source', 'run 1', '--output', output)
    assert result.returncode == 0, result.stderr
    assert '2 not in this checkout' in result.stdout
    # Each unit is the mean over the runs that have it.
    assert shard.load_table(output) == ({'integration/test_only.py': 7.0, 'tests/test_a.py': 4.0,
                                         'tests/test_gone.py': 0.5, 'tests/test_s.py::TestGroup::small': 1.0,
                                         'tests/test_s.py::big[0]': 15.0}, ['tests/test_s.py'])
    data = json.loads(output.read_text())
    assert data['command'].count('--update') == 2 and '--split tests/test_s.py' in data['command']
    bad = tmp_path / 'bad.xml'
    bad.write_text('<testsuites><testcase classname="Weird" name="x" time="1"/></testsuites>', encoding='utf-8')
    result = update(tmp_path, '--update', bad, '--source', 'run 1', '--output', output)
    assert result.returncode != 0 and 'no test module' in result.stderr


def test_update_leaves_out_cases_no_longer_collected(tmp_path):
    (tmp_path / 'tests').mkdir()
    for name in ('test_a.py', 'test_b.py'):
        (tmp_path / 'tests' / name).write_text('', encoding='utf-8')
    xml = tmp_path / 'part.xml'
    xml.write_text('<testsuites><testsuite>'
                   '<testcase classname="tests.test_a" name="kept[0]" time="1"/>'
                   '<testcase classname="tests.test_a" name="moved[0]" time="30"/>'
                   '<testcase classname="tests.test_a.TestGroup" name="kept" time="2"/>'
                   '<testcase classname="tests.test_b" name="other" time="4"/>'
                   '</testsuite></testsuites>', encoding='utf-8')
    collected = tmp_path / 'collected.txt'
    collected.write_text('tests/test_a.py::kept[0]\ntests/test_a.py::TestGroup::kept\n\n3 tests collected\n',
                         encoding='utf-8')
    output = tmp_path / 'durations.json'
    result = update(tmp_path, '--update', xml, '--source', 'run 1', '--output', output, '--collected', collected)
    assert result.returncode == 0, result.stderr
    # test_b is not in the collection list at all, so its recorded time is kept.
    assert shard.load_durations(output) == {'tests/test_a.py': 3.0, 'tests/test_b.py': 4.0}
    assert json.loads(output.read_text())['command'].endswith('--collected <node IDs> --source <runs>')
