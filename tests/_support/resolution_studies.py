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
identified by the SHA-256 of its nodes and triangles. A base line whose mesh equals a variant
must match it within 1e-9; a mesh matching no variant is compared with the closest variant
within MESH_VARIANT_RELATIVE. The path taken is written to the JUnit property
``resolution_study_reproduction``.
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
# A mesh matching no recorded variant is compared with the closest variant instead. The
# recorded platforms' base lines differ by at most 2.2e-5 between the two meshes (run
# 45965021952: 5.4e-6, 1.0e-6, 1.8e-6 and 2.2e-5 by case), so 1e-4 admits another valid
# triangulation of the same mesh settings while staying a hundred times below the 1% study
# criterion; a larger change still fails and needs the study rerun.
MESH_VARIANT_RELATIVE = 1e-4

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


def compare(module, index, result):
    """Compare a solved base line with the record; return (path, variant labels, errors).

    ``exact``: the dielectric mesh equals a recorded variant, and every quantity must agree
    within MATRIX_RELATIVE. ``tolerance``: no recorded variant has this mesh (for example a
    new runner image triangulates a cocircular tie another way); the closest variant must
    agree within MESH_VARIANT_RELATIVE instead of failing until the study is rerun.
    """
    case = recorded_case(module, index)
    values = quantities(result)
    mesh = mesh_identity(result)

    def errors(row):
        assert sorted(values) == sorted(row['quantities'])
        return {key: matrix_relative(values[key], row['quantities'][key]) for key in values}

    same = [row for row in case['variants'] if row['dielectric_mesh'] == mesh]
    if same:
        found = errors(same[0])
        assert max(found.values()) <= MATRIX_RELATIVE, found
        return 'exact', same[0]['recorded_by'], found
    rows = [(errors(row), row) for row in case['variants']]
    found, row = min(rows, key=lambda item: max(item[0].values()))
    assert max(found.values()) <= MESH_VARIANT_RELATIVE, (mesh, found)
    return 'tolerance', row['recorded_by'], found


def reproduce(module, index, document, record_property=None):
    """Solve the base line of a study and compare it with the record (see ``compare``)."""
    case = recorded_case(module, index)
    assert json.loads(document.dumps()) == case['base_input'], f'{module}[{index}]: base input changed'
    result = document.analyze()
    path, labels, found = compare(module, index, result)
    if record_property is not None:
        record_property('resolution_study_reproduction', json.dumps(dict(
            path=path, closest_variant=labels, dielectric_mesh=mesh_identity(result),
            matrix_relative=found), sort_keys=True))
    return path, found
