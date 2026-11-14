# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Actual coated pair search, separate finite domains and independent networks."""
import json
import numpy as np
import pytest
from scipy.linalg import expm
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
from sipi.network import rlgc_network
from test_layered_metal import transfer

MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def factory(width, gap, *, box=.024, air=.010):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=gap, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, box_width=box, air_height=air)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9],
        materials={}, length=0., conductor=dict(kind='surface-boundaries',
            conductors={t.name:material() for t in section.traces}, reference=material(),
            ground_thickness=35e-6), schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, schema='sipi.panel-transmission-line/2')


def snapshot(line):
    return dict(input=json.loads(line.input_json),
        quantities={key:getattr(line,key).tolist() for key in ('R','L','C','G')},
        L_internal=line.conductor.L_internal.tolist(), C0=line.current_factors.C0.tolist(),
        parts=line.current_factors.parts.tolist(), current_integrals=line.current_factors.current_integrals.tolist())


@pytest.fixture(scope='module')
def searched():
    # Start outside the target tolerances; a preselected fixture is not a search.
    return seek_panel_forward_pair_impedances(factory, [[.4e-3,.9e-3],[.2e-3,.6e-3]],
        [110.,40.], tolerances=[.25,.125], initial=[.7e-3,.35e-3], max_evaluations=64)


def independent(line):
    characteristic_errors, scattering_errors = [], []
    network = rlgc_network(line.frequency, R=line.R, L=line.L, C=line.C, G=line.G,
                          length=.02, z_ref=50., names=line.names)
    for i, frequency in enumerate(line.frequency):
        omega = 2*np.pi*frequency
        z, y = line.R[i]+1j*omega*line.L[i], line.G[i]+1j*omega*line.C[i]
        generator = np.block([[np.zeros((2,2)),z],[y,np.zeros((2,2))]])
        roots, vectors = np.linalg.eig(expm(generator*.003))
        v = vectors[:,abs(roots)>1]
        assert v.shape == (4,2)
        expected = np.linalg.solve(v[2:].T,v[:2].T).T
        characteristic_errors.append(float(abs(line.characteristic().z_characteristic[i]-expected).max()/abs(expected).max()))
        # Independent wave equations from the full nonzero-length transfer matrix.
        t = expm(generator*.02); a,b,c,d = t[:2,:2],t[:2,2:],t[2:,:2],t[2:,2:]
        eye = np.eye(2)
        expected_s = np.linalg.solve(np.block([[eye,-a-b/50],[-eye,-50*c-d]]),
                                     np.block([[-eye,a-b/50],[-eye,50*c-d]]))
        scattering_errors.append(float(abs(network.s[i]-expected_s).max()))
        np.testing.assert_allclose(line.R[i]+1j*omega*line.conductor.L_internal[i],
                                   transfer(frequency)*line.current_factors.total, rtol=1e-10)
    assert max(characteristic_errors)<1e-10 and max(scattering_errors)<1e-10
    np.testing.assert_allclose(network.s,network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.linalg.svd(network.s,compute_uv=False).max()<=1+1e-10
    return dict(characteristic_errors=characteristic_errors, scattering_errors=scattering_errors)


def test_actual_search_and_all_independent_refinements(searched, record_property):
    goal = searched
    record_property('coated_pair_search', json.dumps(goal.to_dict(),allow_nan=False))
    assert np.any(abs(np.array(goal.history[0].impedances)-goal.targets)>goal.tolerances)
    assert 4<len(goal.history)<=64
    assert [r.evaluation.stage for r in goal.refinements] == [
        'volume-refinement','panel-refinement','joint-refinement']
    results = [goal.result]+[r.result for r in goal.refinements]
    # Preserve all matrices before checking gates, including a failed case.
    record_property('coated_pair_fields',json.dumps([snapshot(r) for r in results],allow_nan=False))
    values = np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic[0]).real for r in results])
    assert np.all(abs(values-goal.targets)<=goal.tolerances)
    assert np.all(abs(values[1:]-values[0])/abs(values[0])<=.005)
    for index in (1,2):assert np.all(abs(values[3]-values[index])/abs(values[index])<=.005)
    for row in goal.history:
        data = json.loads(row.input_json)
        assert data['schema']=='sipi.panel-transmission-line/2'
        assert data['line']['schema']=='sipi.transmission-line/7'
        assert data['line']['conductor']==factory(*goal.parameters).to_dict()['line']['conductor']
    record_property('coated_pair_independent',json.dumps([independent(r) for r in results]))


def test_selected_finite_outer_gates_at_three_frequencies(searched, record_property):
    results = []
    for box,air,modes in ((.024,.010,512),(.036,.015,768),(.048,.020,1024)):
        raw = factory(*searched.parameters,box=box,air=air).to_dict()
        raw['line']['cross_section']['mesh'] = searched.refinements[-1].document.line.cross_section.mesh_options
        raw['panel'] = dict(searched.refinements[-1].document.panel_options,ground_modes=modes)
        raw['line']['frequency_hz'] = [1e9,2e9,4e9]
        results.append(PanelTransmissionLineDocument.from_dict(raw).analyze())
    values = np.array([np.diagonal(r.characteristic().mixed_mode().z_characteristic,axis1=1,axis2=2).real for r in results])
    changes = abs(np.diff(values,axis=0))
    record_property('coated_pair_outer',json.dumps(dict(values=values.tolist(),changes=changes.tolist(),
        fields=[snapshot(r) for r in results]),allow_nan=False))
    # These are finite-domain diagonal gates, not relative accuracy of small R12.
    assert np.all(changes[:,:,0]<=1e-4*values[0,:,0])
    assert np.all(changes[1,:,1]<changes[0,:,1])
    record_property('coated_pair_outer_independent',json.dumps([independent(r) for r in results]))
