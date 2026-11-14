# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Opt-in, module-preserving pytest partitions with complete collection evidence."""
import hashlib
import json
from pathlib import Path
import pytest

SCHEMA = 'sipi.pytest-partition/1'


def partition(nodeid, count):
    """Assign a whole module, independently of platform, collection order or hash seed."""
    module = nodeid.split('::', 1)[0].replace('\\', '/')
    return int.from_bytes(hashlib.sha256(module.encode('utf-8')).digest(), 'big') % count


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
                         arguments=list(config.invocation_params.args),
                         collect_only=bool(config.getoption('collectonly')),
                         all_nodeids=[], selected_nodeids=[], completed_nodeids=[],
                         collection_errors=None, exit_status=None)

    def save(self):
        self.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report.with_name(self.report.name + '.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
        temporary.replace(self.report)

    @pytest.hookimpl(trylast=True)
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
