# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, module-preserving, time-balanced pytest partitions with complete collection evidence.

Whole test modules are assigned to partitions. Modules listed in ``shards/durations.json``
beside this file (recorded seconds per module from the JUnit XML of a complete CI run) are
assigned largest first, each to the partition with the least recorded time so far (ties go to
the lower index). A module missing from the table keeps the stable SHA-256 assignment of its
relative path. The assignment depends only on the table, the partition count and the module
path, never on platform, collection order or hash seed, so every partition and
``tools/check_shards.py`` compute the same plan.

Rebuild the table from the source JUnit XML of all partitions of one complete run, from the
repository root::

    python tools/pytest_shard.py --update source-*.xml --source "<run, commit, date, files>"
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

SCHEMA = 'sipi.pytest-partition/2'
DURATIONS = Path(__file__).resolve().with_name('shards') / 'durations.json'


def module_of(nodeid):
    return nodeid.split('::', 1)[0].replace('\\', '/')


def hashed(module, count):
    """The stable path hash used for modules without a recorded time."""
    return int.from_bytes(hashlib.sha256(module.encode('utf-8')).digest(), 'big') % count


def load_durations(path=DURATIONS):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(data) != {'source', 'command', 'seconds'} or not isinstance(data['source'], str) or not data['source']:
        raise ValueError(f'{path}: expected source, command and seconds')
    seconds = data['seconds']
    if not seconds or not all(isinstance(k, str) and k.endswith('.py') and '\\' not in k
                              and type(v) in (int, float) and v >= 0 for k, v in seconds.items()):
        raise ValueError(f'{path}: every entry must map a module path to seconds >= 0')
    return seconds


def durations_digest(path=DURATIONS):
    """SHA-256 of the canonical table content, unchanged by line-ending conversion on checkout."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    canonical = json.dumps(data, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('ascii')).hexdigest()


def balance(seconds, count):
    """Largest-first assignment of the recorded modules to the least-loaded partition."""
    load = [0.0] * count
    plan = {}
    for module in sorted(seconds, key=lambda name: (-seconds[name], name)):
        index = min(range(count), key=lambda i: (load[i], i))
        plan[module] = index
        load[index] += seconds[module]
    return plan


@functools.lru_cache(maxsize=None)
def _plan(path, count):
    return balance(load_durations(path), count)


def partition(nodeid, count, durations=DURATIONS):
    """Assign a whole module: by recorded time when listed, otherwise by its stable path hash."""
    module = module_of(nodeid)
    plan = _plan(str(durations), count)
    return plan[module] if module in plan else hashed(module, count)


def digest(nodeids):
    payload = json.dumps(nodeids, ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(payload).hexdigest()


def pytest_addoption(parser):
    group = parser.getgroup('sipi-partitions')
    group.addoption('--sipi-shard-index', type=int, default=None)
    group.addoption('--sipi-shard-count', type=int, default=None)
    group.addoption('--sipi-shard-report', type=Path, default=None)


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
    config.pluginmanager.register(PartitionRun(index, count, report, config), 'sipi-partition-run')


class PartitionRun:
    def __init__(self, index, count, report, config):
        self.report = report
        self.completed = []
        self.data = dict(schema=SCHEMA, index=index, count=count,
                         durations_sha256=durations_digest(),
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
            (selected if partition(item.nodeid, self.data['count']) == self.data['index'] else omitted).append(item)
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


def update(xml_paths, source, output=DURATIONS, root=Path('.')):
    """Sum the JUnit test-case times per module and write the table."""
    seconds = {}
    for xml_path in xml_paths:
        for case in ET.parse(xml_path).getroot().iter('testcase'):
            module = case_module(case.get('classname', ''), root)
            if module is None:
                raise SystemExit(f'{xml_path}: no test module for {case.get("classname")!r}; '
                                 'run from the repository root')
            seconds[module] = seconds.get(module, 0.0) + float(case.get('time', 0) or 0)
    table = dict(source=source,
                 command='python tools/pytest_shard.py --update <source JUnit XML of every partition> '
                         '--source <run>',
                 seconds={k: round(v, 1) for k, v in sorted(seconds.items())})
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(table, indent=1) + '\n', encoding='utf-8')
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description='Rebuild the recorded module durations.')
    parser.add_argument('--update', nargs='+', metavar='JUNIT_XML', required=True,
                        help='source JUnit XML of every partition of one complete run')
    parser.add_argument('--source', required=True, help='where the times come from (run, commit, date)')
    parser.add_argument('--output', type=Path, default=DURATIONS)
    args = parser.parse_args(argv)
    table = update(args.update, args.source, args.output)
    total = sum(table['seconds'].values())
    absent = [name for name in table['seconds'] if not Path(name).is_file()]
    print(f"{len(table['seconds'])} modules, {total / 60:.1f} min, {len(absent)} not in this checkout, "
          f"written to {args.output}")


if __name__ == '__main__':
    sys.exit(main())
