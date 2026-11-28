# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, time-balanced pytest partitions with complete collection evidence.

Each platform has its own table, ``shards/durations-<platform>.json`` beside this file
(``linux``, ``darwin`` or ``win32``, as ``sys.platform``), of recorded seconds per unit from
the JUnit XML of complete CI runs on that platform. A unit is a whole test module, keeping its
module fixtures together, except for the modules the table lists under ``split``: their cases
are separate units (node IDs). Only modules whose expensive cases do not share a module fixture
are split. Recorded units are assigned largest first, each to the partition with the least
recorded time so far (ties go to the lower index). A module missing from the table keeps the
stable SHA-256 assignment of its relative path (a missing case of a split module, of its node
ID). The assignment depends only on the table, the partition count and the node ID, never on
collection order or hash seed, so every partition and ``tools/check_shards.py`` compute the
same plan; the manifest names the table it used.

Rebuild a table from the source and installed JUnit XML of all partitions of complete runs on
one platform, from the repository root (one ``--update`` per complete suite run; a unit's time
is the mean over the runs that have it)::

    python tools/pytest_shard.py --table linux --update source-*.xml --update installed-*.xml \
        --split <module> ... --collected <node IDs> --source "<run, commit, date, files>"
"""
import argparse
import functools
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

try:
    import pytest
except ModuleNotFoundError:  # tools/check_shards.py recomputes the plan without pytest installed
    pytest = None

SCHEMA = 'sipi.pytest-partition/3'
SHARDS = Path(__file__).resolve().with_name('shards')
TABLES = ('linux', 'darwin', 'win32')


def table_path(name):
    if name not in TABLES:
        raise ValueError(f'unknown durations table {name!r}; expected one of {TABLES}')
    return SHARDS / f'durations-{name}.json'


def platform_table():
    """The table of the running platform."""
    return {'linux': 'linux', 'darwin': 'darwin', 'win32': 'win32'}[sys.platform]


DURATIONS = table_path(platform_table()) if sys.platform in TABLES else None


def module_of(nodeid):
    return nodeid.split('::', 1)[0].replace('\\', '/')


def normalized(nodeid):
    module, sep, rest = nodeid.partition('::')
    return module.replace('\\', '/') + sep + rest


def hashed(module, count):
    """The stable path hash used for modules without a recorded time."""
    return int.from_bytes(hashlib.sha256(module.encode('utf-8')).digest(), 'big') % count


def load_table(path=DURATIONS):
    """(seconds per unit, split modules) of a table, after checking its format."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(data) != {'source', 'command', 'split', 'seconds'} or not isinstance(data['source'], str) \
            or not data['source']:
        raise ValueError(f'{path}: expected source, command, split and seconds')
    split = data['split']
    if not isinstance(split, list) or len(set(split)) != len(split) or not all(
            isinstance(k, str) and k.endswith('.py') and '\\' not in k for k in split):
        raise ValueError(f'{path}: split must list distinct module paths')
    seconds = data['seconds']
    if not seconds or not all(isinstance(k, str) and '\\' not in k.split('::', 1)[0] and module_of(k).endswith('.py')
                              and type(v) in (int, float) and v >= 0 for k, v in seconds.items()):
        raise ValueError(f'{path}: every entry must map a module path or node ID to seconds >= 0')
    for key in seconds:
        if ('::' in key) != (module_of(key) in split):
            raise ValueError(f'{path}: {key!r}: node IDs exactly for the split modules')
    return seconds, split


def load_durations(path=DURATIONS):
    return load_table(path)[0]


def durations_digest(path=DURATIONS):
    """SHA-256 of the canonical table content, unchanged by line-ending conversion on checkout."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('ascii')).hexdigest()


def balance(seconds, count):
    """Largest-first assignment of the recorded units to the least-loaded partition."""
    load = [0.0] * count
    plan = {}
    for module in sorted(seconds, key=lambda name: (-seconds[name], name)):
        index = min(range(count), key=lambda i: (load[i], i))
        plan[module] = index
        load[index] += seconds[module]
    return plan


@functools.lru_cache(maxsize=None)
def _plan(path, count):
    seconds, split = load_table(path)
    return balance(seconds, count), frozenset(split)


def unit_of(nodeid, split):
    """The node ID itself in a split module, otherwise its module."""
    module = module_of(nodeid)
    return normalized(nodeid) if module in split else module


def partition(nodeid, count, durations=DURATIONS):
    """Assign a unit: by recorded time when listed, otherwise by its stable path hash."""
    plan, split = _plan(str(durations), count)
    unit = unit_of(nodeid, split)
    return plan[unit] if unit in plan else hashed(unit, count)


def digest(nodeids):
    payload = json.dumps(nodeids, ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(payload).hexdigest()


def pytest_addoption(parser):
    group = parser.getgroup('sipi-partitions')
    group.addoption('--sipi-shard-index', type=int, default=None)
    group.addoption('--sipi-shard-count', type=int, default=None)
    group.addoption('--sipi-shard-report', type=Path, default=None)
    group.addoption('--sipi-shard-durations', choices=TABLES, default=None,
                    help='durations table (default: the running platform)')


def pytest_configure(config):
    index = config.getoption('--sipi-shard-index')
    count = config.getoption('--sipi-shard-count')
    report = config.getoption('--sipi-shard-report')
    if index is None and count is None and report is None:
        return
    if index is None or count is None or report is None or not 0 <= index < count <= 64:
        raise pytest.UsageError('provide a report and 0 <= sipi-shard-index < sipi-shard-count <= 64')
    if report.exists():
        raise pytest.UsageError('partition report already exists; use a fresh report path')
    if config.getoption('keyword') or config.getoption('markexpr') or config.getoption('deselect'):
        raise pytest.UsageError('partition collection must not use -k, -m or --deselect')
    table = config.getoption('--sipi-shard-durations') or platform_table()
    config.pluginmanager.register(PartitionRun(index, count, report, config, table), 'sipi-partition-run')


class PartitionRun:
    def __init__(self, index, count, report, config, table):
        self.report = report
        self.completed = []
        self.durations = table_path(table)
        self.data = dict(schema=SCHEMA, index=index, count=count, durations_table=table,
                         durations_sha256=durations_digest(self.durations),
                         arguments=list(config.invocation_params.args),
                         collect_only=bool(config.getoption('collectonly')),
                         all_nodeids=[], selected_nodeids=[], completed_nodeids=[],
                         collection_errors=None, exit_status=None)

    def save(self):
        self.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report.with_name(self.report.name + '.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
        temporary.replace(self.report)

    @(pytest.hookimpl(trylast=True) if pytest else (lambda hook: hook))
    def pytest_collection_modifyitems(self, session, config, items):
        all_ids = [item.nodeid for item in items]
        if len(set(all_ids)) != len(all_ids):
            raise pytest.UsageError('duplicate collected node IDs cannot establish partition coverage')
        selected, omitted = [], []
        for item in items:
            (selected if partition(item.nodeid, self.data['count'], self.durations) == self.data['index']
             else omitted).append(item)
        self.data.update(all_nodeids=all_ids, collection_sha256=digest(all_ids),
                         selected_nodeids=[item.nodeid for item in selected],
                         collection_errors=session.testsfailed)
        self.save()
        if not selected:
            raise pytest.UsageError('empty partition cannot establish regression coverage')
        config.hook.pytest_deselected(items=omitted)
        items[:] = selected

    def pytest_runtest_logreport(self, report):
        if report.when == 'teardown':
            self.completed.append(report.nodeid)

    def pytest_sessionfinish(self, session, exitstatus):
        self.data.update(completed_nodeids=self.completed, exit_status=int(exitstatus))
        self.save()


def case_module(classname, root):
    """The test module of a JUnit classname (dotted path, optionally followed by classes).

    A module absent from this checkout (the run tested another commit) is named by the
    dotted path up to its first capitalized (class) component.
    """
    parts = classname.split('.')
    for n in range(len(parts), 0, -1):
        path = Path(root).joinpath(*parts[:n]).with_suffix('.py')
        if path.is_file():
            return '/'.join(parts[:n]) + '.py'
    module = []
    for part in parts:
        if not part or part[0].isupper():
            break
        module.append(part)
    return '/'.join(module) + '.py' if module and module[-1].startswith('test_') else None


def case_nodeid(case, module):
    """The pytest node ID of a JUnit test case in ``module``."""
    classes = case.get('classname', '').split('.')[len(module[:-3].split('/')):]
    return '::'.join([module, *classes, case.get('name', '')])


def unit_seconds(xml_paths, root=Path('.'), split=(), collected=None):
    """Sum the JUnit test-case times of one complete suite run per unit."""
    seconds = {}
    modules = None if collected is None else {module_of(nodeid) for nodeid in collected}
    for xml_path in xml_paths:
        for case in ET.parse(xml_path).getroot().iter('testcase'):
            module = case_module(case.get('classname', ''), root)
            if module is None:
                raise SystemExit(f'{xml_path}: no test module for {case.get("classname")!r}; '
                                 'run from the repository root')
            nodeid = case_nodeid(case, module)
            if modules is not None and module in modules and nodeid not in collected:
                continue
            unit = nodeid if module in split else module
            seconds[unit] = seconds.get(unit, 0.0) + float(case.get('time', 0) or 0)
    return seconds


def update(groups, source, output, root=Path('.'), split=(), collected=None):
    """Write the table: per unit, the mean over the suite runs (groups of XML) that have it.

    Each group is the XML of every partition of one complete suite run. With ``collected`` (a
    set of node IDs), cases no longer collected are left out, so tests moved out of the regular
    suite stop counting. Cases of the ``split`` modules are separate units.
    """
    runs = [unit_seconds(paths, root, set(split), collected) for paths in groups]
    seconds = {}
    for unit in sorted(set().union(*runs)):
        found = [run[unit] for run in runs if unit in run]
        seconds[unit] = round(sum(found) / len(found), 1)
    command = 'python tools/pytest_shard.py --table <platform> ' + ' '.join(
        ['--update <JUnit XML of every partition of one suite run>'] * len(groups))
    if split:
        command += ' --split ' + ' '.join(sorted(split))
    if collected is not None:
        command += ' --collected <node IDs>'
    table = dict(source=source, command=command + ' --source <runs>', split=sorted(split), seconds=seconds)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(table, indent=1) + '\n', encoding='utf-8')
    load_table(output)
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description='Rebuild the recorded durations of one platform.')
    parser.add_argument('--table', choices=TABLES, required=True, help='platform of the runs')
    parser.add_argument('--update', nargs='+', action='append', metavar='JUNIT_XML', required=True,
                        help='JUnit XML of every partition of one complete suite run; repeat per run')
    parser.add_argument('--source', required=True, help='where the times come from (runs, commit, date)')
    parser.add_argument('--output', type=Path, default=None, help='default: shards/durations-<table>.json')
    parser.add_argument('--split', nargs='*', default=[], metavar='MODULE',
                        help='modules whose cases are separate units (no shared expensive module fixture)')
    parser.add_argument('--collected', type=Path, default=None,
                        help='node IDs collected now, one per line (pytest --collect-only -q); '
                             'cases of these modules that are not listed are left out')
    args = parser.parse_args(argv)
    collected = None
    if args.collected is not None:
        collected = {line.strip() for line in args.collected.read_text(encoding='utf-8').splitlines()
                     if '::' in line}
    output = args.output or table_path(args.table)
    table = update(args.update, args.source, output, split=args.split, collected=collected)
    total = sum(table['seconds'].values())
    absent = [name for name in table['seconds'] if not Path(module_of(name)).is_file()]
    print(f"{len(table['seconds'])} units, {total / 60:.1f} min, {len(absent)} not in this checkout, "
          f"written to {output}")


if __name__ == '__main__':
    sys.exit(main())
