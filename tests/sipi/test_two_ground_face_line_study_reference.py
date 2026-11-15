# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Scalar endpoint checks at explicitly registered finite-box resolution."""
import json
import numpy as np
import pytest
from sipi.two_ground_face_input import _line_from_values
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line
from test_two_ground_face_line_study import document


@pytest.mark.parametrize('width', [.00055, .00065])
def test_scalar_endpoints_separate_mesh_outer_and_complex_quantities(width, record_property):
    source = document(physical=True).to_dict()
    selected = _line_from_values(source, [width]).to_dict()
    selected['panel'].update(panels_per_edge=256, ground_modes=256)
    rows = []
    for box, refined in ((.008, False), (.008, True), (.016, True), (.032, True)):
        raw = json.loads(json.dumps(selected))
        raw['cross_section']['box']['width'] = box
        if refined:
            for key in ('edge_size', 'far_size', 'grade'):
                raw['cross_section']['mesh'][key] /= 2
        line = Line.from_dict(raw).analyze()
        omega = 2*np.pi*line.frequency[0]
        z = line.R[0,0,0] + 1j*omega*line.L[0,0,0]
        y = line.G[0,0,0] + 1j*omega*line.C[0,0,0]
        actual = line.propagation()
        np.testing.assert_allclose(actual.z_characteristic[0,0], np.sqrt(z/y), rtol=1e-12, atol=0)
        np.testing.assert_allclose(actual.gamma[0,0], np.sqrt(z*y), rtol=1e-12, atol=0)
        values = dict(R=line.R, L=line.L, C0=line.current_factors.C0,
            impedance=np.array([actual.z_characteristic[0,0].real]),
            attenuation=np.array([actual.gamma[0,0].real]))
        rows.append(dict(input=raw, values={k:v.tolist() for k,v in values.items()},
                         current=line.current_record(), mesh=line.mesh_record()))
    record_property('face_scalar_finite_endpoints', json.dumps(rows, sort_keys=True))
    for earlier, later in zip(rows, rows[1:]):
        for key in ('R','L','C0','impedance','attenuation'):
            np.testing.assert_allclose(later['values'][key], earlier['values'][key], rtol=.01, atol=0)
