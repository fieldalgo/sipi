# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Registered diagonal manufacturing corners: mesh and finite outer sensitivity."""
import json
import numpy as np
import pytest
from sipi.two_ground_face_input import _line_from_values
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_pair_study import document


@pytest.mark.parametrize('parameters', [(.00043, .00028), (.00044, .00030)])
def test_diagonal_corners_keep_separate_mesh_and_outer_checks(parameters, record_property):
    source = document(physical=True).to_dict()
    selected = _line_from_values(source, parameters).to_dict()
    selected['panel']['panels_per_edge'] = 256
    rows = []
    for width, refined in ((.008, False), (.008, True), (.016, True), (.032, True)):
        raw = json.loads(json.dumps(selected))
        raw['cross_section']['box']['width'] = width
        if refined:
            for key in ('edge_size', 'far_size', 'grade'):
                raw['cross_section']['mesh'][key] /= 2
        result = Line.from_dict(raw).analyze()
        values = dict(R=result.R, L=result.L, C0=result.current_factors.C0,
            impedance=np.diagonal(result.characteristic().mixed_mode().z_characteristic,
                                  axis1=1, axis2=2).real)
        rows.append(dict(input=raw, values={k: v.tolist() for k, v in values.items()},
                         current=result.current_record(), mesh=result.mesh_record()))
    record_property('face_study_finite_corners', json.dumps(rows, sort_keys=True))
    for earlier, later in zip(rows, rows[1:]):
        for key in ('R', 'L', 'C0', 'impedance'):
            np.testing.assert_allclose(later['values'][key], earlier['values'][key],
                                       rtol=.01, atol=0)
