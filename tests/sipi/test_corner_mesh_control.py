# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit corner targets preserve geometry, defaults and saved contracts."""
import json
import numpy as np
import pytest
from scipy.constants import epsilon_0
from scipy.sparse.linalg import spsolve
from crosscheck import require_tool
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.polygons import PolygonTrace, DielectricRegion
import sipi.crosssection as api

OPTIONS = dict(edge_size=1e-5, far_size=.0002, grade=.15)


def section(kind, width=.008):
    trace = Trace('signal', 0, .0006, .0008, .0004,
                  top_width=.0003 if kind == 'taper' else None)
    if kind in ('polygon', 'region'):
        trace = PolygonTrace('signal', np.array([
            [-.3,.8],[.3,.8],[.2,1.2],[0,1.2],[0,1.05],[-.3,1.05]])*.001)
    regions = []
    if kind == 'region':
        regions = [DielectricRegion('local', np.array([
            [-.6,.7],[.6,.7],[.6,1.4],[-.6,1.4]])*.001, 4.)]
    return CrossSection([Layer('dielectric', .002, 4.)], [trace], width,
                        top='ground', dielectric_regions=regions)


@pytest.mark.parametrize('bad', [True, False, 0., -1., float('nan'), float('inf'),
                                '1e-6', 1e-6j, [1e-6], 2e-5])
def test_invalid_corner_target_rejected_before_mesher(bad, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('invalid target reached the mesher')
    monkeypatch.setattr(api, 'generate', forbidden)
    with pytest.raises(ValueError, match='corner_size'):
        section('rectangle').mesh(**OPTIONS, corner_size=bad)


def test_resolved_settings_preserve_default_keys_and_explicit_target():
    cs = section('rectangle')
    default = cs.mesh_settings()
    assert set(default) == {'edge_size', 'far_size', 'grade', 'min_angle'}
    assert cs.mesh_settings(corner_size=None) == default
    requested = cs.mesh_settings(corner_size=default['edge_size']/2)
    assert requested == dict(default, corner_size=default['edge_size']/2)
    assert cs.mesh_settings(**requested) == requested
    with pytest.raises(ValueError, match='corner_size'):
        cs.mesh_settings(corner_size=default['edge_size']*2)


@pytest.mark.parametrize('kind', ['rectangle', 'taper', 'polygon', 'region'])
def test_omitted_and_equal_corner_preserve_actual_mesh(kind, record_property):
    cs = section(kind)
    fields = [cs.mesh(**OPTIONS), cs.mesh(**OPTIONS, corner_size=None),
              cs.mesh(**OPTIONS, corner_size=OPTIONS['edge_size'])]
    original = fields[0]
    for other in fields[1:]:
        for key in ('nodes', 'triangles', 'regions'):
            np.testing.assert_array_equal(getattr(original.mesh, key), getattr(other.mesh, key))
        np.testing.assert_array_equal(original.eps_r, other.eps_r)
        np.testing.assert_array_equal(original.ground, other.ground)
        np.testing.assert_array_equal(original.signals['signal'], other.signals['signal'])
    record_property('default_corner', json.dumps(dict(kind=kind, nodes=original.mesh.num_nodes,
        triangles=original.mesh.num_triangles, C0=original.line_parameters().C0.tolist())))


def test_corner_and_face_targets_are_independent(monkeypatch):
    cs = section('rectangle')
    class Observed(Exception): pass
    def observe(*args, **kw):
        size = kw['size_fn']
        np.testing.assert_allclose(size([-.0003,0],[.0008,.0008]),
                                   [2.5e-6,3*OPTIONS['edge_size']], rtol=1e-14, atol=0)
        assert kw['candidate_order'] == 'stable'
        raise Observed
    monkeypatch.setattr(api, 'generate', observe)
    with pytest.raises(Observed):
        cs.mesh(**OPTIONS, corner_size=2.5e-6)


@pytest.mark.parametrize('kind', ['rectangle', 'taper', 'polygon', 'region'])
def test_saved_documents_keep_original_strict_mesh_contract(kind):
    doc = CrossSectionDocument(section(kind), mesh=OPTIONS)
    assert CrossSectionDocument.loads(doc.dumps()).dumps() == doc.dumps()
    raw = doc.to_dict()
    raw['mesh']['corner_size'] = 2.5e-6
    with pytest.raises(ValueError, match='unknown'):
        CrossSectionDocument.from_dict(raw)
    with pytest.raises(ValueError, match='unknown'):
        CrossSectionDocument(section(kind), mesh=dict(OPTIONS, corner_size=2.5e-6))


def independent_capacitance(field):
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    mesh = sk.MeshTri(field.mesh.nodes.T.copy(), field.mesh.triangles.T.copy())
    basis = sk.Basis(mesh, sk.ElementTriP2(), intorder=4)
    boundary = mesh.boundary_facets()
    groups = [basis.get_dofs(facets=boundary[np.isin(mesh.facets[:,boundary], ids).all(axis=0)]).all()
              for ids in (field.signals['signal'], field.ground)]
    fixed = np.concatenate(groups)
    assert len(fixed) == len(np.unique(fixed))
    @sk.BilinearForm
    def stiffness(u, v, w): return dot(grad(u), grad(v))
    matrix = stiffness.assemble(basis).tocsc()
    free = np.setdiff1d(np.arange(basis.N), fixed)
    potential = np.zeros(basis.N); potential[groups[0]] = 1.
    potential[free] = spsolve(matrix[free][:,free], -matrix[free][:,fixed]@potential[fixed])
    reaction = matrix@potential
    charge = epsilon_0*reaction[groups[0]].sum()
    assert abs(charge/(epsilon_0*(potential@reaction))-1) < 1e-10
    return charge


@pytest.mark.parametrize('kind', ['rectangle', 'taper', 'polygon', 'region'])
def test_explicit_corner_geometry_reference_mesh_and_outer(kind, record_property):
    cs = section(kind)
    coarse_options = dict(OPTIONS, corner_size=2.5e-6)
    fine_options = {key:value/2 for key,value in coarse_options.items()}
    fields = [cs.mesh(**coarse_options), cs.mesh(**fine_options),
              section(kind, width=.012).mesh(**fine_options)]
    results = [field.line_parameters() for field in fields]
    reference = independent_capacitance(fields[1])
    record_property('corner_physical', json.dumps(dict(kind=kind,
        meshes=[dict(nodes=f.mesh.num_nodes, triangles=f.mesh.num_triangles) for f in fields],
        C0=[p.C0.tolist() for p in results], reference_C0=reference,
        coarse=coarse_options, fine=fine_options)))
    for a,b in ((results[0].C0,results[1].C0),(results[1].C0,results[2].C0),
                (results[1].C0,reference)):
        assert np.all(abs(a-b) <= .005*np.maximum(abs(a),abs(b)))
    trace = cs.traces[0]
    corners = trace.corners()
    area = abs(np.sum(corners[:,0]*np.roll(corners[:,1],-1)-corners[:,1]*np.roll(corners[:,0],-1)))/2
    for field, result, width in zip(fields, results, (.008,.008,.012)):
        assert field.mesh.areas().sum() == pytest.approx(width*.002-area, rel=1e-12)
        np.testing.assert_allclose(result.C, 4*result.C0, rtol=1e-9, atol=0)
        assert np.all(field.eps_r == 4.)
