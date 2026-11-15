# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Frozen selected geometry: separate finite-frequency, panel and outer checks."""
from pathlib import Path
import json
import numpy as np
from scipy.linalg import sqrtm
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Document


def test_selected_geometry_has_separate_panel_and_finite_outer_gates(record_property):
    source = json.loads((Path(__file__).parent/'data/two_ground/face_goal_selected.json').read_text())
    observations = []
    values = []
    a = np.array([[1., -1.], [.5, .5]])
    for width, panels in ((.008, 128), (.008, 256), (.016, 256), (.032, 256)):
        raw = json.loads(json.dumps(source['input']))
        raw['frequency_hz'] = [1e9, 3e9, 10e9]
        raw['cross_section']['box']['width'] = width
        raw['panel']['panels_per_edge'] = panels
        for key in ('edge_size', 'far_size', 'grade'):
            raw['cross_section']['mesh'][key] /= 2
        doc = Document.from_dict(raw)
        line = doc.analyze()
        actual = np.diagonal(line.characteristic().mixed_mode().z_characteristic, axis1=1, axis2=2).real
        independent = []
        for i, frequency in enumerate(line.frequency):
            omega = 2*np.pi*frequency
            z = line.R[i] + 1j*omega*line.L[i]
            y = line.G[i] + 1j*omega*line.C[i]
            gamma = np.asarray(sqrtm(z@y), dtype=complex)
            characteristic = np.linalg.solve(gamma, z)
            independent.append(np.diag(a@characteristic@a.T).real)
        np.testing.assert_allclose(actual, independent, rtol=1e-10, atol=0)
        values.append(actual)
        observations.append(dict(input=raw, impedances=actual.tolist(),
            R=line.R.tolist(), L=line.L.tolist(), C=line.C.tolist(), G=line.G.tolist(),
            current=line.current_record(), mesh=line.mesh_record()))
    changes = [np.abs(values[1]/values[0]-1),
               np.abs(values[2]/values[1]-1), np.abs(values[3]/values[2]-1)]
    record_property('face_goal_finite_reference', json.dumps(dict(
        observations=observations, relative_changes=[x.tolist() for x in changes]), sort_keys=True))
    assert all(np.all(x <= .01) for x in changes)
