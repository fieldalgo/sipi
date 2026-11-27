# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Opt-in gate and stored record of the corner-face finite-resolution studies.

Each study test solves six complete lines (base, finer dielectric mesh, finer panels, both,
and two wider outer boxes) and requires every R, internal and external L, C, G and C0 entry
at every frequency of each comparison to agree within 1% of the larger magnitude. One study
takes 6 to 60 minutes on one CI runner, so the studies run only with
``SIPI_RESOLUTION_STUDIES=1``, as the dispatch-only job ``resolution-studies`` of
validate.yml (input ``resolution_studies=true``) does, and are marked ``slow``; otherwise
they are not defined. The regular suite instead solves each study's base line, the first
of the six, and requires it to reproduce the values recorded with the study in
``tests/sipi/reference_data/resolution_studies/finite-resolution-studies.json`` within a
matrix-relative 1e-9. The 1% study criteria are unchanged and are re-checked whenever that
job runs.

The dielectric mesher may pick another valid triangulation at exact cocircular ties on some
platforms (macOS in the recorded runs), so the record keeps one variant per dielectric mesh,
identified by the SHA-256 of its nodes and triangles; the base line must match the variant
of its own mesh.
"""
import json
import os
from pathlib import Path

import numpy as np

from sipi.line_resolution_document import _SI
from sipi.line_resolution import _metric

ENVIRONMENT = 'SIPI_RESOLUTION_STUDIES'
RECORD = (Path(__file__).resolve().parents[1] / 'sipi' / 'reference_data' / 'resolution_studies'
          / 'finite-resolution-studies.json')
MATRIX_RELATIVE = 1e-9

# Without the variable the study tests are not defined at all, so they are neither collected
# nor skipped: the installed run treats a skip as a failure and deselects nothing.
ENABLED = os.environ.get(ENVIRONMENT) == '1'


def quantities(result):
    """The six SI quantity arrays of a line, exactly as the study record stores them."""
    return {_SI[key]: np.asarray(_metric(result, key), dtype=float) for key in _SI}


def mesh_identity(result):
    record = result.mesh_record()
    return dict(nodes_float64_le_sha256=record['nodes_float64_le_sha256'],
                triangles_int64_le_sha256=record['triangles_int64_le_sha256'])


def matrix_relative(value, reference):
    """Largest entry difference relative to the largest reference entry."""
    value, reference = np.asarray(value, dtype=float), np.asarray(reference, dtype=float)
    assert value.shape == reference.shape and np.isfinite(value).all()
    scale = float(np.max(abs(reference)))
    assert scale > 0
    return float(np.max(abs(value - reference))) / scale


def recorded_case(module, index):
    data = json.loads(RECORD.read_text(encoding='utf-8'))
    return next(case for case in data['modules'][module]['cases'] if case['index'] == index)


def reproduce(module, index, document):
    """Solve the base line of a study and require the recorded variant of its own mesh."""
    case = recorded_case(module, index)
    assert json.loads(document.dumps()) == case['base_input'], f'{module}[{index}]: base input changed'
    result = document.analyze()
    mesh = mesh_identity(result)
    variants = [row for row in case['variants'] if row['dielectric_mesh'] == mesh]
    assert variants, (f'{module}[{index}]: dielectric mesh {mesh} matches no recorded variant; '
                      'run the study (SIPI_RESOLUTION_STUDIES=1) and regenerate the record')
    values = quantities(result)
    assert sorted(values) == sorted(variants[0]['quantities'])
    errors = {key: matrix_relative(values[key], variants[0]['quantities'][key]) for key in values}
    assert max(errors.values()) <= MATRIX_RELATIVE, errors
    return errors
