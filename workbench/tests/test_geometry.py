"""Shared adapter retains tapered/planar-coating geometry in every result."""
import json
from pathlib import Path
import sys

import pytest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from engine import execute
from sipi.templates import coated_microstrip
from sipi import GoalSeekError

PARAMETERS = dict(width=.5e-3, top_width=.4e-3, thickness=.1e-3,
                  substrate_height=1e-3, eps_r=4, coating_height=.2e-3,
                  coating_eps_r=3.5, coating_tan_delta=.01)
MESH = dict(edge_size=5e-6, far_size=.5e-3, grade=.2)


def test_coated_taper_roundtrip_matches_native_and_network():
    request = dict(action='analyze', template='coated_microstrip', parameters=PARAMETERS, mesh=MESH)
    result = execute(request)
    native = coated_microstrip(**PARAMETERS).analyze(**MESH)
    assert result['line']['C'] == native.C.tolist()
    doc = result['document']
    assert doc['schema'] == 'sipi.cross-section/2'
    assert doc['traces'][0]['top_width'] == .4e-3
    restored = execute(dict(action='analyze', document_text=json.dumps(doc)))
    assert restored['line'] == result['line']
    network = execute(dict(action='network', document=doc, network=dict(
        start_hz=1e6, stop_hz=1e9, points=3, length=.1, resistance=0, z_ref=50)))
    assert network['document'] == doc
    assert np.all(np.isfinite(network['network']['real']))
    assert '[Number of Ports] 2' in network['network']['touchstone']


@pytest.mark.parametrize('override', [dict(thickness=0), dict(coating_height=.05e-3), dict(top_width=-1)])
def test_geometry_errors_are_reported(override):
    with pytest.raises(ValueError):
        execute(dict(action='document', template='coated_microstrip', parameters={**PARAMETERS, **override}))


def test_target_width_keeps_top_width_and_verifies_tapered_design():
    # Choose the target on the independently refined mesh, then search across
    # it. This exercises the actual nonlinear geometry and final refinement.
    fine = {**MESH, 'edge_size': MESH['edge_size']/2,
            'far_size': MESH['far_size']/2, 'grade': MESH['grade']/2}
    target = coated_microstrip(**PARAMETERS).analyze(**fine).z0
    # The coarse design must fail its independent refinement rather than
    # reporting an unverified target. Tighten the mesh, keeping 0.1 ohm fixed.
    with pytest.raises(GoalSeekError, match='refined mesh misses target'):
        execute(dict(action='design', template='coated_microstrip',
            parameters=PARAMETERS, mesh=MESH,
            design=dict(bounds=[.45e-3, .55e-3], target=target, tolerance=.1)))
    tightened = {**MESH, 'edge_size': MESH['edge_size']/4,
                 'far_size': MESH['far_size']/4, 'grade': MESH['grade']/2}
    result = execute(dict(action='design', template='coated_microstrip',
        parameters=PARAMETERS, mesh=tightened,
        design=dict(bounds=[.45e-3, .55e-3], target=target, tolerance=.1)))
    assert result['document']['schema'] == 'sipi.cross-section/2'
    assert result['document']['traces'][0]['top_width'] == PARAMETERS['top_width']
    assert abs(result['design']['residual']) <= .1
    assert abs(result['design']['refined_residual']) <= .1
    assert result['document']['traces'][0]['width'] == result['design']['width']
