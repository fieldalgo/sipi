# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Write linear-line-study-base.json from line-study JUnit XML and a local base sweep.

Run from the repository root with the JUnit XML of runs of the linear corner-face line study
(each labelled by platform and suite): the source and installed partitions of a Validate run
from before the study became dispatch-only, or the artifacts of the dispatch-only
``resolution-studies`` job (``SIPI_RESOLUTION_STUDIES=1``)::

    PYTHONPATH=src python tests/sipi/reference_data/resolution_studies/generate_linear_line_study_base.py \\
        --junit ubuntu-latest/source=<source.xml> macos-15/source=<source.xml> ... --source "<run>"

The study test ``test_actual_scalar_sweep_refinement_and_complex_closed_forms`` writes the
property ``two_ground_linear_corner_face_scalar_study`` only after all of its assertions pass:
for each of the three sweep samples, R, L and C0 at 32, 64 and 128 panels per edge (each level
within 1% of the next) and the closed-form propagation. The record keeps, per sample, the base
level (32 panels, the regular sweep's resolution) once per distinct dielectric mesh; copies
with the same mesh must agree within a matrix-relative 1e-9. The base sweep is then solved
here with the code of the regular reproduction test and must match the variant of its own
mesh. A missing sample, a failed study or a local mismatch is an error.
"""
import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'tests' / '_support'), str(ROOT / 'tests' / 'sipi')]

import numpy as np  # noqa: E402
import resolution_studies as support  # noqa: E402

MODULE = 'test_two_ground_linear_corner_face_line_study'
TEST = 'test_actual_scalar_sweep_refinement_and_complex_closed_forms'
PROPERTY = 'two_ground_linear_corner_face_scalar_study'
LEVELS = (32, 64, 128)
CRITERION = ('three sweep samples; for each, R, L and C0 at 32, 64 and 128 panels per edge with '
             'consecutive levels within rtol 0.01 (atol 0), and the closed-form characteristic '
             'impedance and propagation constant within rtol 1e-12 at every level')


def base_quantities(level, value):
    """The recorded base-level quantities: R, total L and C0 of the line, and the sample value."""
    return dict(R_ohm_per_m=level['R'], L_h_per_m=level['L'], C0_f_per_m=level['C0'],
                impedance_real_ohm=[value])


def mesh_identity(mesh):
    return dict(nodes_float64_le_sha256=mesh['nodes_float64_le_sha256'],
                triangles_int64_le_sha256=mesh['triangles_int64_le_sha256'])


def worst_ratio(levels):
    worst = 0.
    for key in ('R', 'L', 'C0'):
        for a, b in zip(levels, levels[1:]):
            a, b = np.asarray(a[key], dtype=float), np.asarray(b[key], dtype=float)
            worst = max(worst, float(np.max(abs(a - b) / (.01 * abs(b)))))
    return worst


def read(junit):
    found = []
    for item in junit:
        label, _, path = item.partition('=')
        if not label or not path:
            raise SystemExit(f'--junit expects LABEL=PATH, not {item!r}')
        for case in ET.parse(path).getroot().iter('testcase'):
            if case.get('classname', '').split('.')[-1] != MODULE or case.get('name') != TEST:
                continue
            if case.find('failure') is not None or case.find('error') is not None:
                raise SystemExit(f'{label}: the line study failed')
            for prop in case.iter('property'):
                if prop.get('name') == PROPERTY:
                    found.append((label, json.loads(prop.get('value')), float(case.get('time', 0) or 0)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--junit', nargs='+', required=True, metavar='PLATFORM/SUITE=XML')
    parser.add_argument('--source', required=True, help='where the study XML comes from (run, commit, date)')
    parser.add_argument('--output', type=Path, default=support.LINE_STUDY_RECORD)
    args = parser.parse_args(argv)
    copies = read(args.junit)
    if not copies:
        raise SystemExit('no line-study property in the given XML')
    rows = []
    for index in range(3):
        study, variants, given = {}, [], None
        for label, records, seconds in copies:
            if len(records) != 3:
                raise SystemExit(f'{label}: expected three samples')
            record = records[index]
            if [dict(level['panel'])['panels_per_edge'] for level in record['levels']] != list(LEVELS):
                raise SystemExit(f'{label}[{index}]: unexpected panel levels')
            if given is None:
                given = record['input']
            elif record['input'] != given:
                raise SystemExit(f'{label}[{index}]: a different sample input')
            study[label] = dict(passed=True, seconds_whole_test=seconds,
                                worst_difference_over_allowance=worst_ratio(record['levels']))
            values = base_quantities(record['levels'][0], record['value'])
            mesh = mesh_identity(record['levels'][0]['mesh'])
            same = [row for row in variants if row['dielectric_mesh'] == mesh]
            if same:
                errors = {key: support.matrix_relative(values[key], same[0]['quantities'][key]) for key in values}
                if max(errors.values()) > support.MATRIX_RELATIVE:
                    raise SystemExit(f'{label}[{index}]: same mesh, different values {errors}')
                same[0]['recorded_by'].append(label)
            else:
                variants.append(dict(dielectric_mesh=mesh, recorded_by=[label], quantities=values))
        text = json.dumps(given, sort_keys=True, separators=(',', ':'))
        rows.append(dict(index=index, input=given, input_sha256=hashlib.sha256(text.encode()).hexdigest(),
                         study=study, variants=variants))

    # The regular reproduction test's own base sweep, solved here.
    from test_two_ground_linear_corner_face_line_study import base_sweep
    for row, (values, mesh, input_json) in zip(rows, base_sweep()):
        if json.loads(input_json) != row['input']:
            raise SystemExit(f'sample {row["index"]}: the local input differs from the recorded one')
        own = [variant for variant in row['variants'] if variant['dielectric_mesh'] == mesh]
        if not own:
            raise SystemExit(f'sample {row["index"]}: no recorded variant has the local mesh {mesh}')
        errors = {key: support.matrix_relative(values[key], own[0]['quantities'][key]) for key in values}
        if max(errors.values()) > support.MATRIX_RELATIVE:
            raise SystemExit(f'sample {row["index"]}: local base sweep differs {errors}')
        own[0]['local_check_matrix_relative'] = max(errors.values())
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = dict(
        schema='sipi.linear-line-study-base/1',
        description=('Base sweep (32 panels per edge) of the dispatch-only linear corner-face line study, '
                     'reproduced by the regular suite. Recorded from the study XML; one variant per '
                     'dielectric mesh.'),
        module=MODULE, test=TEST, criterion=CRITERION, environment_variable=support.ENVIRONMENT,
        reproduction_matrix_relative=support.MATRIX_RELATIVE, quantities=sorted(rows[0]['variants'][0]['quantities']),
        study_source=args.source,
        generated_utc=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        product_commit=commit, local_check=dict(platform=platform.platform(), python=platform.python_version()),
        command=('PYTHONPATH=src python tests/sipi/reference_data/resolution_studies/'
                 'generate_linear_line_study_base.py --junit <platform>/<suite>=<xml> ... --source "<run>"'),
        rows=rows)
    args.output.write_text(json.dumps(data, indent=1, sort_keys=False) + '\n', encoding='utf-8')
    print(f'{len(rows)} samples, {sum(len(r["variants"]) for r in rows)} variants, written to {args.output}')


if __name__ == '__main__':
    sys.exit(main())
