# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Write finite-resolution-studies.json from study JUnit XML and a local base solve.

Run from the repository root with the JUnit XML of study runs (each labelled by platform and
suite), for example the source and installed partitions of a Validate run or the artifacts of
the dispatch-only ``resolution-studies`` job (``SIPI_RESOLUTION_STUDIES=1``)::

    PYTHONPATH=src python tests/sipi/reference_data/resolution_studies/generate_finite_resolution_studies.py \\
        --junit ubuntu-latest/source=<source.xml> macos-15/source=<source.xml> ... --source "<run>"

For every study case the XML property ``corner_face_finite_resolution`` holds the six
evaluations and comparisons. The record keeps the study outcome of each labelled run and the
base evaluation (the first of the six) once per distinct dielectric mesh; copies with the same
mesh must agree within a matrix-relative 1e-9. The base line is then solved here with the code
the regular reproduction tests use (``tests/_support/resolution_studies.py``) and must match
the recorded variant of its own mesh. A study case missing from the XML, a failed or
unaccepted study, or a local mismatch is an error.
"""
import argparse
import datetime
import hashlib
import importlib
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

PROPERTY = 'corner_face_finite_resolution'
CRITERION = ('six complete lines (base, volume, panel, joint, outer:0, outer:1); every comparison '
             'requires |b - a| <= 0.01 max(|a|, |b|) for each R, L_internal, L_external, C, G and C0 '
             'entry at every frequency; four current solves (exact base/volume and panel/joint reuse)')
MODULES = {
    'test_two_ground_harmonic_three_active_corner_face_resolution':
        ('test_actual_layered_three_signal_finite_comparisons', [0]),
    'test_two_ground_harmonic_guard_corner_face_resolution':
        ('test_actual_layered_two_signals_and_guard_finite_comparisons', [0]),
    'test_two_ground_linear_corner_face_resolution':
        ('test_actual_layered_one_and_two_signal_finite_comparisons', [0, 1]),
}


def worst_ratio(comparison):
    worst = 0.
    for key, difference in comparison['differences'].items():
        difference, allowance = np.asarray(difference), np.asarray(comparison['allowances'][key])
        ratio = np.divide(difference, allowance, out=np.where(difference == 0, 0., np.inf), where=allowance != 0)
        worst = max(worst, float(np.max(ratio)))
    return worst


def read(junit):
    found = {}
    for item in junit:
        label, _, path = item.partition('=')
        if not label or not path:
            raise SystemExit(f'--junit expects LABEL=PATH, not {item!r}')
        for case in ET.parse(path).getroot().iter('testcase'):
            module = case.get('classname', '').split('.')[-1]
            name, _, parameter = case.get('name', '').partition('[')
            if module not in MODULES or name != MODULES[module][0]:
                continue
            index = int(parameter.rstrip(']'))
            for prop in case.iter('property'):
                if prop.get('name') == PROPERTY:
                    found.setdefault((module, index), []).append(
                        (label, json.loads(prop.get('value')), float(case.get('time', 0) or 0)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--junit', nargs='+', required=True, metavar='LABEL=PATH')
    parser.add_argument('--source', required=True, help='where the study runs happened')
    args = parser.parse_args(argv)
    found = read(args.junit)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.strip()
    record = dict(
        schema='sipi.finite-resolution-studies/1',
        description=('Base-line values and outcomes of the corner-face finite-resolution studies; '
                     'see tests/_support/resolution_studies.py.'),
        environment_variable=support.ENVIRONMENT, reproduction_matrix_relative=support.MATRIX_RELATIVE,
        quantities=sorted(support._SI.values()), study_source=args.source,
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        product_commit=commit,
        local_check=dict(python=platform.python_version(), numpy=np.__version__, os=platform.platform()),
        command=('PYTHONPATH=src python tests/sipi/reference_data/resolution_studies/'
                 'generate_finite_resolution_studies.py --junit <LABEL=study JUnit XML> ... --source <run>'),
        modules={})
    for module_name, (test, indices) in MODULES.items():
        module = importlib.import_module(module_name)
        cases = []
        for index in indices:
            runs = found.get((module_name, index))
            if not runs:
                raise SystemExit(f'{module_name}[{index}]: no {PROPERTY!r} in the JUnit XML')
            variants, outcomes, base_input = [], {}, None
            for label, study, seconds in runs:
                if not (study['completed'] and study['accepted'] and len(study['evaluations']) == 6):
                    raise SystemExit(f'{module_name}[{index}] {label}: the study did not complete and accept')
                outcomes[label] = dict(completed=True, accepted=True, seconds=round(seconds, 1),
                    worst_difference_over_allowance={row['stage']: worst_ratio(row) for row in study['comparisons']})
                base = study['evaluations'][0]
                if base['stage'] != 'base':
                    raise SystemExit(f'{module_name}[{index}] {label}: the first evaluation is not the base line')
                if base_input is None:
                    base_input = base['input']
                elif base['input'] != base_input:
                    raise SystemExit(f'{module_name}[{index}] {label}: a different base input')
                mesh = {key: base['dielectric_mesh'][key] for key in
                        ('nodes_float64_le_sha256', 'triangles_int64_le_sha256')}
                same = [row for row in variants if row['dielectric_mesh'] == mesh]
                if same:
                    for key, value in base['quantities'].items():
                        error = support.matrix_relative(value, same[0]['quantities'][key])
                        if error > support.MATRIX_RELATIVE:
                            raise SystemExit(f'{module_name}[{index}] {label}: {key} differs by {error:.1e} '
                                             'on the same mesh')
                    same[0]['recorded_by'].append(label)
                else:
                    variants.append(dict(dielectric_mesh=mesh, recorded_by=[label], quantities=base['quantities']))
            document = module.inputs(index)[0]
            if json.loads(document.dumps()) != base_input:
                raise SystemExit(f'{module_name}[{index}]: the test inputs no longer give the studied base line')
            result = document.analyze()
            mesh = support.mesh_identity(result)
            local = [row for row in variants if row['dielectric_mesh'] == mesh]
            if not local:
                raise SystemExit(f'{module_name}[{index}]: the local mesh {mesh} matches no studied variant')
            errors = {key: support.matrix_relative(value, local[0]['quantities'][key])
                      for key, value in support.quantities(result).items()}
            if max(errors.values()) > support.MATRIX_RELATIVE:
                raise SystemExit(f'{module_name}[{index}]: the local base line differs: {errors}')
            local[0]['local_check_matrix_relative'] = max(errors.values())
            cases.append(dict(index=index, base_input=base_input,
                              base_input_sha256=hashlib.sha256(document.dumps().encode()).hexdigest(),
                              study=outcomes, variants=variants))
        record['modules'][module_name] = dict(test=test, criterion=CRITERION, cases=cases)
    output = Path(support.RECORD)
    output.write_text(json.dumps(record, indent=1, sort_keys=False) + '\n', encoding='utf-8')
    print(f'wrote {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
