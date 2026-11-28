# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit dual-cell currents, independent weak reactions and field comparisons."""
import json

import numpy as np
import pytest
from scipy.sparse.linalg import splu
from galerkin import Mesh, rectangle_mesh, annulus_mesh

from sipi import coupled_microstrip, CrossSection
from sipi.constants import epsilon_0, mu_0
from sipi.conductor import surface_current_factors
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.dual_cell_conductor import (DualCellCurrentFactors, dual_cell_surface_current_factors,
                                     dual_cell_conductor_loss_by_boundary)
from sipi.panel_conductor import panel_surface_current_factors
from test_layered_metal import LAYERS, transfer
from crosscheck import require_tool

# v1 results fixed: these checks were recorded with the v1 default template
# boxes (sipi.templates.box_rule, 2026-11-28); values and tolerances are unchanged.
from sipi._template_registry import _pinned_v1
coupled_microstrip = _pinned_v1(coupled_microstrip)

MESH = dict(edge_size=5e-6, far_size=.2e-3, grade=.1)


def relative(a, b):
    return float(abs(np.asarray(a)-b).max()/abs(np.asarray(b)).max())


def independent(mesh, signals, ground):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
    basis = sk.Basis(m, sk.ElementTriP1()); facets = m.boundary_facets()
    boundaries = [facets[np.isin(m.facets[:, facets], nodes).all(axis=0)]
                  for nodes in [*signals.values(), ground]]
    groups = [basis.get_dofs(facets=b).all() for b in boundaries]
    fixed = np.unique(np.concatenate(groups)); free = np.setdiff1d(np.arange(basis.N), fixed)
    @sk.BilinearForm
    def stiffness(u, v, w): return dot(grad(u), grad(v))
    k = stiffness.assemble(basis).tocsc(); v = np.zeros((basis.N, len(signals)))
    for i, ids in enumerate(groups[:-1]): v[ids, i] = 1.
    factor = splu(k[free][:, free].tocsc())
    v[free] = factor.solve(-(k[free][:, fixed]@v[fixed])); del factor
    reaction = k@v; c0 = epsilon_0*(v.T@reaction); inverse = np.linalg.inv(c0)
    parts, currents = [], []
    for boundary, ids in zip(boundaries, groups):
        edges = m.facets[:, boundary]
        length = np.linalg.norm(m.p[:, edges[1]]-m.p[:, edges[0]], axis=0)
        weight = np.zeros(basis.N)
        np.add.at(weight, edges.ravel(), np.tile(length/2, 2))
        j = epsilon_0*reaction[ids]@inverse
        parts.append(j.T@(j/weight[ids, None])); currents.append(j.sum(axis=0))
    return c0, np.array(parts), np.array(currents)


def test_parallel_plate_exact_power_and_algebraic_conservation():
    mesh = rectangle_mesh(.002, .001, 8, 4)
    result = dual_cell_surface_current_factors(mesh, {'signal':mesh.boundary['top']}, mesh.boundary['bottom'])
    assert isinstance(result, DualCellCurrentFactors)
    np.testing.assert_allclose(result.parts[:,0,0], [500.,500.], rtol=1e-10)
    np.testing.assert_allclose(result.current_integrals, [[1.],[-1.]], atol=1e-10, rtol=0)
    for values in (result.parts, result.C0, result.current_integrals): assert not values.flags.writeable


def test_coax_polygon_limit_matches_independent_closed_form(record_property):
    a, b = .5e-3, 2e-3; exact = (1/a+1/b)/(2*np.pi); errors = []
    for nr, nt in [(8,32),(16,64),(32,128),(64,256)]:
        mesh = annulus_mesh(a,b,nr,nt)
        result = dual_cell_surface_current_factors(mesh, {'inner':mesh.boundary['inner']}, mesh.boundary['outer'])
        errors.append(float(abs(result.total[0,0]/exact-1)))
        assert result.current_error < 1e-10
    record_property('dual_cell_coax_errors', json.dumps(errors))
    assert all(b<a for a,b in zip(errors,errors[1:])) and errors[-1] < .001


@pytest.fixture(scope='module')
def pcb():
    section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                                 thickness=.05e-3, eps_r=4)
    rows = []
    for factor in (1., .5):
        field = section.mesh(**{k:v*factor for k,v in MESH.items()})
        result = dual_cell_surface_current_factors(field.mesh, field.signals, field.ground)
        rows.append((field, result))
    return section, rows


def test_independent_p1_reactions_preserve_the_original_vacuum_basis(pcb, record_property):
    errors = []
    for field, result in pcb[1]:
        ref = independent(field.mesh, field.signals, field.ground)
        errors.extend(relative(a,b) for a,b in zip((result.C0,result.parts,result.current_integrals),ref))
        gradient = surface_current_factors(field.mesh, field.signals, field.ground)
        np.testing.assert_array_equal(result.C0,gradient.C0)
        np.testing.assert_allclose(result.current_integrals, np.vstack((np.eye(2),-np.ones((1,2)))), rtol=0,atol=1e-10)
        for part in result.parts: assert np.linalg.eigvalsh(part).min() >= -1e-12*abs(part).max()
    record_property('independent_weak_current_error', max(errors))
    assert max(errors) < 1e-10


def test_matched_panel_observation_and_refinement_keep_small_mutual_entries(pcb, record_property):
    panel = panel_surface_current_factors(pcb[0], panels_per_edge=256, ground_modes=512, interpolation_degree=16)
    rows = []
    for _, result in pcb[1]:
        rows.append(dict(total=result.total.tolist(),parts=result.parts.tolist(),
            total_error=relative(result.total,panel.total),
            part_errors=[relative(a,b) for a,b in zip(result.parts,panel.parts)]))
    record_property('dual_cell_matched_panel', json.dumps(dict(rows=rows,panel_total=panel.total.tolist(),panel_parts=panel.parts.tolist())))
    assert rows[1]['total_error'] < rows[0]['total_error'] and rows[1]['total_error'] <= .02
    assert all(a<b for a,b in zip(rows[1]['part_errors'],rows[0]['part_errors']))
    assert max(rows[1]['part_errors']) <= .03


@pytest.mark.parametrize('scale,reflect,reverse', [(1e-3,False,False),(1e3,False,False),(1.,True,False),(1.,False,True)])
def test_scale_reflection_and_signal_permutation(pcb, scale, reflect, reverse):
    field, original = pcb[1][0]
    nodes = field.mesh.nodes.copy()*scale; triangles = field.mesh.triangles.copy()
    if reflect:
        nodes[:,0] *= -1; triangles = triangles[:,[0,2,1]]
    items = list(field.signals.items())
    if reverse: items.reverse()
    actual = dual_cell_surface_current_factors(Mesh(nodes,triangles,{}), dict(items), field.ground)
    expected = original.parts[[1,0,2],::-1,::-1] if reverse else original.parts
    np.testing.assert_allclose(actual.parts*scale,expected,rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(actual.C0,original.C0[::-1,::-1] if reverse else original.C0,rtol=1e-10)


def test_layered_boundary_wrapper_uses_one_mesh_and_independent_surface_law(pcb, monkeypatch):
    section = pcb[0]; calls = []; original = CrossSection.mesh
    def mesh(self, **options): calls.append(options); return original(self, **options)
    monkeypatch.setattr(CrossSection,'mesh',mesh)
    f = np.array([1e9,4e9]); metals = {'positive':LayeredSurfaceMetal(58e6,coatings=LAYERS),'negative':SurfaceMetal(35e6)}
    result = dual_cell_conductor_loss_by_boundary(section,f,conductors=metals,
        reference=SurfaceMetal(58e6),ground_thickness=35e-6,**MESH)
    assert calls == [MESH] and isinstance(result.factors,DualCellCurrentFactors)
    zs = np.array([[transfer(x),np.sqrt(2j*np.pi*x*mu_0/35e6),np.sqrt(2j*np.pi*x*mu_0/58e6)] for x in f])
    expected = np.einsum('fb,bij->fij',zs,result.factors.parts)
    np.testing.assert_allclose(result.R+2j*np.pi*f[:,None,None]*result.L_internal,expected,rtol=1e-10)
    np.testing.assert_allclose(result.resistance_parts.sum(axis=1),result.R,rtol=1e-12)


@pytest.mark.parametrize('where', ['signal','reference'])
def test_real_skin_core_rejection_precedes_mesh(where, monkeypatch):
    monkeypatch.setattr(CrossSection,'mesh',lambda *a,**k:pytest.fail('invalid core reached mesh'))
    section = coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=1e-3,
                                 thickness=12e-6 if where=='signal' else 35e-6,eps_r=4)
    plain,coated = SurfaceMetal(58e6),LayeredSurfaceMetal(58e6,coatings=LAYERS)
    label = 'signal positive' if where=='signal' else 'reference'
    with pytest.raises(ValueError,match=label+': .*skin depth'):
        dual_cell_conductor_loss_by_boundary(section,[1e9],
            conductors={'positive':coated if where=='signal' else plain,'negative':plain},
            reference=coated if where=='reference' else plain,
            ground_thickness=12e-6 if where=='reference' else 35e-6)


@pytest.mark.parametrize('kind', ['empty','overlap','incomplete'])
def test_boundary_admission_matches_original_gradient_contract(kind):
    mesh = rectangle_mesh(.002,.001,8,4); signal=mesh.boundary['top']; ground=mesh.boundary['bottom']
    signals = {'signal':signal}
    if kind=='empty': signals={}
    if kind=='overlap': ground=signal
    if kind=='incomplete': signals={'signal':signal[[0,-1]]}
    for method in (dual_cell_surface_current_factors,surface_current_factors):
        with pytest.raises(ValueError): method(mesh,signals,ground)
