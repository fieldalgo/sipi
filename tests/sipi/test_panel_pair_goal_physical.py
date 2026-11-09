# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Physical panel-current goals and independent characteristic eigenspaces."""
import numpy as np
import pytest
from scipy import linalg
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
from test_pair_line_goal import document


@pytest.fixture(scope='module')
def physical_goal():
    return seek_panel_forward_pair_impedances(
        lambda w,g:PanelTransmissionLineDocument(document(w,g)),
        [[.4e-3,.9e-3],[.2e-3,.6e-3]],[110.,40.],tolerances=[.25,.125],
        initial=[.7e-3,.35e-3],max_evaluations=64)


def test_real_asymmetric_goal_and_independent_refinements(physical_goal):
    goal=physical_goal
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert np.all(abs(np.array(goal.impedances)-goal.targets)<=goal.tolerances)
    assert [r.evaluation.stage for r in goal.refinements]==['volume-refinement','panel-refinement','joint-refinement']
    for refined in goal.refinements:
        values=np.array(refined.evaluation.impedances)
        assert np.all(abs(values-goal.targets)<=goal.tolerances)
        assert np.all(abs(values/goal.impedances-1)<=.005)
        assert refined.result.input_json==refined.evaluation.input_json
    for refined in goal.refinements[:2]:
        assert np.all(abs(np.array(goal.refinements[-1].evaluation.impedances)/refined.evaluation.impedances-1)<=.005)
    for row,line in [(None,goal.result)]+[(r.evaluation,r.result) for r in goal.refinements]:
        omega=2*np.pi*line.frequency[0];Z=line.R[0]+1j*omega*line.L[0];Y=line.G[0]+1j*omega*line.C[0]
        scale=np.sqrt(abs(Z).max()/abs(Y).max())
        roots,vectors=linalg.eig(np.block([[np.zeros_like(Z),Z/scale],[scale*Y,np.zeros_like(Y)]]));mask=roots.imag>0
        assert np.count_nonzero(mask)==2 and np.all(roots[mask].real>=0)
        v=vectors[:,mask];expected=scale*v[:2]@np.linalg.inv(v[2:]);actual=line.characteristic().z_characteristic[0]
        np.testing.assert_allclose(actual,expected,rtol=1e-10,atol=1e-10)
        assert abs(line.characteristic().mixed_mode().z_characteristic[0,0,1])>.001
