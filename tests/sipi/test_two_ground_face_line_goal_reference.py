# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Scalar endpoint checks at explicitly registered finite-box resolution."""
import json
import numpy as np
import pytest
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument as Line



# Frozen from the registered 58-ohm direct search; this test never reruns search.
# Source JUnit SHA256: de7222d2c755476cf36fb38c25ae35f003a0efd0f7e4f51cf165cb5d5fec5791
SELECTED = {'conductors': {'signal': {'bottom': {'conductivity': 58000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}, 'left': {'conductivity': 21000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}, 'right': {'conductivity': 45000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}, 'top': {'conductivity': 35000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}}}, 'cross_section': {'box': {'bottom': 'ground', 'sides': 'open', 'top': 'ground', 'width': 0.008}, 'layers': [{'eps_r': 4.0, 'name': 'dielectric', 'tan_delta': 0.003, 'thickness': 0.002}], 'length_unit': 'm', 'mesh': {'edge_size': 5e-06, 'far_size': 0.0001, 'grade': 0.05, 'min_angle': 28.0}, 'schema': 'sipi.cross-section/1', 'traces': [{'ground': False, 'name': 'signal', 'thickness': 5e-05, 'width': 0.000590625, 'x': 0.0, 'y': 0.0007}]}, 'frequency_hz': [2000000000.0], 'ground_thickness_m': 3.5e-05, 'length_m': 0.0, 'materials': {}, 'panel': {'ground_modes': 128, 'interpolation_degree': 16, 'panels_per_edge': 128}, 'reference': {'bottom': {'conductivity': 58000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}, 'conductors': {}, 'kind': 'surfaces', 'sides': None, 'top': {'conductivity': 21000000.0, 'relative_permeability': 1.0, 'roughness': {'kind': 'smooth'}}}, 'reference_ohms': 50.0, 'schema': 'sipi.two-ground-face-panel-transmission-line/1'}


def test_selected_goal_separate_mesh_outer_and_complex_quantities(record_property):
    selected = json.loads(json.dumps(SELECTED))
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
    record_property('face_scalar_goal_finite_selection', json.dumps(rows, sort_keys=True))
    for earlier, later in zip(rows, rows[1:]):
        for key in ('R','L','C0','impedance','attenuation'):
            np.testing.assert_allclose(later['values'][key], earlier['values'][key], rtol=.01, atol=0)
