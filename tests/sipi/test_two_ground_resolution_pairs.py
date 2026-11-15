# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Registered coupled geometries: finite axes and existing independent P4 data."""
import json
import numpy as np
import pytest
from sipi.constants import mu_0,epsilon_0
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_panel_line import TwoGroundPanelTransmissionLineDocument as Line
from sipi.two_ground_resolution import assess_two_ground_line_resolution
from test_two_ground_panel_line import document,independent_network
from test_two_ground_conductor import ROWS


@pytest.mark.parametrize('case',['box-8','pair-close','pair-asymmetric'])
def test_registered_pair_finite_axes_and_independent_references(case,record_property):
    base=document(case,False,panels=64);finer=dict(base.current_options,panels_per_edge=128,ground_modes=256);outer=[]
    for width,modes in ((.016,512),(.032,1024)):
        raw=base.to_dict();raw['cross_section']['box']['width']=width
        raw['panel']=dict(finer,ground_modes=modes)
        for key in ('edge_size','far_size','grade'):raw['cross_section']['mesh'][key]*=.5
        outer.append(Line.from_dict(raw))
    result=assess_two_ground_line_resolution(base,refined_panel_options=finer,outer_documents=outer,
        tolerances={key:ResolutionTolerance(.01,0.) for key in ('R','L_internal','L_external','C','G','C0')},
        refinement_factor=.5,max_solves=6)
    record=result.to_dict()
    # Preserve all obtained evidence before acceptance or independent comparisons.
    record_property('two_ground_pair_finite_resolution',json.dumps(record,sort_keys=True))
    assert result.completed and result.accepted
    assert len(result.evaluations)==len(result.comparisons)==6
    for row in result.evaluations:
        line=row.result;data=json.loads(row.input_json);c0=line.current_factors.C0
        np.testing.assert_allclose(line.C,4*np.broadcast_to(c0,line.C.shape),rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.G,2*np.pi*line.frequency[:,None,None]*.003*line.C,rtol=1e-12,atol=0)
        np.testing.assert_allclose(line.dielectric.L@c0,mu_0*epsilon_0*np.eye(2),rtol=1e-10,atol=1e-28)
        for i,f in enumerate(line.frequency):
            expected=independent_network(f,line.R[i],line.L[i],line.G[i],line.C[i],data['length_m'],data['reference_ohms'])
            np.testing.assert_allclose(line.network.s[i],expected,rtol=1e-10,atol=1e-12)
        assert line.current_record()['boundary_labels']==['signal:positive','signal:negative','reference:bottom','reference:top']
        assert line.mesh_record()['nodes']>0
    pairs=[(result.evaluations[3].result,next(row for row in ROWS if row['case']==case))]
    if case=='box-8':
        pairs.extend((result.evaluations[index].result,next(row for row in ROWS if row['case']==name)) for index,name in ((4,'box-16'),(5,'box-32')))
    for line,reference in pairs:
        # The 16/32 mm P4 entries are archived coarse references, not new
        # reference-convergence evidence. Preserve their existing tolerances.
        values=reference['reference']
        np.testing.assert_allclose(line.current_factors.C0,values['C0'],rtol=5e-4,atol=0)
        np.testing.assert_allclose(line.R,values['R'],rtol=.01,atol=0)
        np.testing.assert_allclose(line.conductor.L_internal,values['L_internal'],rtol=.01,atol=0)
