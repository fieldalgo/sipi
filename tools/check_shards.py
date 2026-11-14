# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reject missing, overlapping, incomplete or inconsistent validation partitions."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(reports, *, collect_only=False):
    """Require an exact partition and, normally, execution of every collected case."""
    if not reports:
        raise ValueError('no partition reports')
    first = reports[0]
    count = first['count']
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError('invalid partition count')
    indices = [report['index'] for report in reports]
    if any(type(i) is not int for i in indices) or sorted(indices) != list(range(count)):
        raise ValueError('missing or duplicate partition indices')
    original = first['all_nodeids']
    if not original or len(set(original)) != len(original):
        raise ValueError('empty or duplicate original collection')
    checksum = hashlib.sha256(json.dumps(original, ensure_ascii=True, separators=(',', ':')).encode('ascii')).hexdigest()
    union = set()
    sizes = []
    for report in reports:
        if report['schema'] != 'sipi.pytest-partition/1' or report['count'] != count:
            raise ValueError('inconsistent partition contract')
        if report['all_nodeids'] != original or report['collection_sha256'] != checksum:
            raise ValueError('different original collection')
        if report['collection_errors'] != 0 or report['exit_status'] != 0 or report['collect_only'] is not collect_only:
            raise ValueError('failed, interrupted or unexecuted partition')
        selected = report['selected_nodeids']
        expected = []
        for nodeid in original:
            module = nodeid.split('::', 1)[0].replace('\\', '/')
            assigned = int(hashlib.sha256(module.encode('utf-8')).hexdigest(), 16) % count
            if assigned == report['index']:
                expected.append(nodeid)
        if not selected or selected != expected:
            raise ValueError('partition selection differs from its module assignment')
        if union.intersection(selected):
            raise ValueError('overlapping partition selection')
        if collect_only:
            if report['completed_nodeids']:
                raise ValueError('collection unexpectedly executed tests')
        elif report['completed_nodeids'] != selected:
            raise ValueError('partition did not complete all selected cases')
        union.update(selected)
        sizes.append(len(selected))
    if union != set(original):
        raise ValueError('partition union differs from original collection')
    return dict(cases=len(original), partitions=count, sizes=sizes, collection_sha256=checksum,
                executed=not collect_only)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path, nargs='+')
    parser.add_argument('--collect-only', action='store_true', help='validate discovery only, not executed regression')
    args = parser.parse_args()
    print(json.dumps(verify([json.loads(p.read_text(encoding='utf-8')) for p in args.reports],
                            collect_only=args.collect_only), indent=2))


if __name__ == '__main__':
    main()
