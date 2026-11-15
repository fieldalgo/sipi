# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Recorded independent face-energy and smooth-loss comparisons."""
import json
from pathlib import Path
import numpy as np
import pytest
from sipi import CrossSection,Layer,Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals,ReferenceSurfaceMetals
from sipi.two_ground_face_conductor import two_ground_conductor_loss_by_face
ROWS=json.loads((Path(__file__).parent/'data/two_ground/face_registered.json').read_text())


def section(row,width=None):
    width=row['width'] if width is None else width
    traces=[]
    for i,polygon in enumerate(row['polygons']):
        p=np.asarray(polygon)-[row['width']/2,0.]
        traces.append(Trace('signal'+str(i),x=float((p[:,0].min()+p[:,0].max())/2),
            y=float(p[:,1].min()),width=float(np.ptp(p[:,0])),thickness=float(np.ptp(p[:,1]))))
    return CrossSection([Layer('uniform',row['height'],4.)],traces,width,top='ground')


def loss(row,count=256,width=None):
    sec=section(row,width)
    first=[SurfaceMetal(x) for x in (58e6,35e6,21e6,45e6)]
    metals={t.name:TraceFaceMetals(*(first if i==0 else first[::-1])) for i,t in enumerate(sec.traces)}
    plane=SurfaceMetal(45e6)
    return two_ground_conductor_loss_by_face(sec,row['frequency_hz'],conductors=metals,
        reference=ReferenceSurfaceMetals(plane,plane,None,{}),ground_thickness=35e-6,
        panels_per_edge=count,ground_modes=256,interpolation_degree=row['degree'])


def change(a,b):
    d=abs(a-b);scale=np.maximum(abs(a),abs(b))
    return np.divide(d,scale,out=np.zeros_like(d),where=scale!=0)


@pytest.mark.parametrize('row',ROWS,ids=[x['case'] for x in ROWS])
def test_actual_faces_and_three_frequency_losses_against_independent_energy(row,record_property):
    results=[loss(row,count) for count in (64,128,256)]
    last=results[-1];n=len(last.factors.names)
    order=np.array([4*i+edge for i in range(n) for edge in (0,2,3,1)])
    for ref in row['reference_levels'].values():
        np.testing.assert_allclose(last.factors.C0,ref['C0'],rtol=5e-4,atol=0)
        for parts in ref['face_parts']:
            np.testing.assert_allclose(last.factors.parts[:4*n],np.asarray(parts)[order],rtol=.02,atol=0)
    for key in ('R','L_internal'):
        observed=getattr(last,key)
        np.testing.assert_allclose(observed,row['weighted_loss']['panels']['256'][key],rtol=1e-10,atol=0)
        for level in ('coarse','medium'):
            for extension in row['weighted_loss']['references'][level][key]:
                np.testing.assert_allclose(observed,extension,rtol=.02,atol=0)
        assert np.max(change(getattr(results[1],key),observed))<=.01
    assert np.max(change(results[1].factors.parts[:4*n],last.factors.parts[:4*n]))<=.01
    record_property('face_independent',json.dumps(dict(case=row['case'],R=last.R.tolist(),L_internal=last.L_internal.tolist(),faces=last.factors.parts.tolist(),source='stored independent P2 volume energy; not rerun'),sort_keys=True))


@pytest.mark.parametrize('row',ROWS,ids=[x['case'] for x in ROWS])
def test_actual_face_loss_finite_outer_comparisons(row):
    results=[loss(row,width=w*.001) for w in (8,16,32)]
    for a,b in zip(results,results[1:]):
        for key in ('R','L_internal'):
            assert np.max(change(getattr(a,key),getattr(b,key)))<=.01
        assert np.max(change(a.factors.parts[:4*len(a.factors.names)],b.factors.parts[:4*len(b.factors.names)]))<=.01
