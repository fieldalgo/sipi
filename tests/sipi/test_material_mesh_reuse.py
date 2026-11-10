# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Search-local mesh reuse preserves material evaluation and refinement."""
from types import SimpleNamespace

import numpy as np
import pytest

import sipi.dielectric as dielectric
import sipi.impedance_material as material
from sipi import CrossSection, CrossSectionDocument, seek_impedance
from sipi.dielectric import (ConstantDielectric, DebyeDielectric,
                             PrincipalAxisDielectric, TabulatedDielectric)
from sipi.templates import stripline, coupled_stripline

F = 1e8
MESH = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)


def document(quantity):
    p = dict(width=.3e-3, plane_spacing=1e-3, eps_r=1, box_width=.006)
    section = stripline(**p) if quantity == 'z0' else coupled_stripline(**p, gap=.3e-3)
    doc = CrossSectionDocument(section, mesh=MESH)
    if quantity == 'z_diff_forward':
        data = doc.to_dict()
        data['traces'][1]['width'] = .2e-3
        doc = CrossSectionDocument.from_dict(data)
    return doc


def models(value, kind):
    first = DebyeDielectric(2, [value], [F])
    if kind == 'scalar':
        first = ConstantDielectric(value, .01)
    elif kind in ('tensor', 'tilted'):
        first = PrincipalAxisDielectric(first, ConstantDielectric(value+1, .02),
                                       .3 if kind == 'tilted' else 0)
    return {'dielectric': first}


def assert_line_exact(a, b):
    assert a.names == b.names
    for name in ('C', 'C0', 'L', 'C_loss'):
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name))


@pytest.mark.parametrize('quantity,kind', [
    (q, k) for q in ('z0', 'z_diff', 'z_diff_forward')
    for k in ('scalar', 'debye', 'tensor', 'tilted')
    if not (q == 'z_diff' and k == 'tilted')])
def test_reused_mesh_recomputes_complex_material_at_each_frequency(quantity, kind, monkeypatch):
    doc = document(quantity)
    values = [material._material_input(f, models(v, kind))
              for f, v in ((F, 3), (2*F, 5))]
    expected = [material._analyze_material(doc, value, quantity) for value in values]
    mesh_calls, vacuum_calls = [], []
    original_mesh, original_cap = CrossSection.mesh, dielectric.capacitance_matrix

    def mesh(section, **options):
        mesh_calls.append(options)
        return original_mesh(section, **options)

    def capacitance(mesh, eps, *args):
        if np.ndim(eps) == 0:
            vacuum_calls.append(eps)
        return original_cap(mesh, eps, *args)

    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(dielectric, 'capacitance_matrix', capacitance)
    reuse = material._MaterialMeshReuse()
    actual = [material._analyze_material(doc, value, quantity, mesh_reuse=reuse)
              for value in values]
    for a, b in zip(actual, expected):
        assert_line_exact(a, b)
    assert len(mesh_calls) == 1 and vacuum_calls == [1.0]
    assert not np.array_equal(actual[0].C, actual[1].C)
    assert not np.array_equal(actual[0].C_loss, actual[1].C_loss)


@pytest.mark.parametrize('quantity', ['z0', 'z_diff', 'z_diff_forward'])
@pytest.mark.parametrize('kind', ['scalar', 'tensor'])
def test_real_material_goals_rebuild_refinement_and_isolate_each_search(quantity, kind, monkeypatch):
    doc = document(quantity)
    nominal = material._analyze_material(doc, material._material_input(F, models(4, kind)), quantity)
    target = nominal.even_odd()['z_diff'] if quantity == 'z_diff' else getattr(nominal, quantity)
    meshes, callbacks = [], []
    original_mesh = CrossSection.mesh

    def mesh(section, **options):
        meshes.append(dict(options))
        return original_mesh(section, **options)

    def model(value):
        callbacks.append(value)
        return models(value, kind)

    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    for index in range(2):
        result, line = seek_impedance(lambda value: doc.section, [2, 6], target,
            quantity=quantity, tolerance=1, mesh=MESH, frequency=F,
            material_factory=model, return_line=True)
        assert result.parameter == 4
        assert [row.stage for row in result.history] == ['search']*3+['refinement']
        assert abs(result.residual) <= 1 and abs(result.refined_residual) <= 1
        assert_line_exact(line, nominal)
        assert len(meshes) == 2*(index+1)
        assert meshes[-2] == MESH
        assert meshes[-1] == dict(edge_size=MESH['edge_size']/2,
                                 far_size=MESH['far_size']/2,
                                 grade=MESH['grade']/2, min_angle=28.)
    assert callbacks == [2., 6., 4.]*2


@pytest.mark.parametrize('change', [
    'width', 'position', 'default_eps', 'default_loss', 'layer_name',
    'trace_name', 'signal_order', 'box_width', 'boundary', 'edge', 'grade'])
def test_every_changed_document_evicts_mesh_and_vacuum_before_rebuilding(change, monkeypatch):
    doc = document('z_diff')
    data = doc.to_dict()
    if change == 'width': data['traces'][0]['width'] *= .9
    elif change == 'position': data['traces'][0]['x'] -= .01e-3
    elif change == 'default_eps': data['layers'][0]['eps_r'] = 3
    elif change == 'default_loss': data['layers'][0]['tan_delta'] = .01
    elif change == 'layer_name': data['layers'][0]['name'] = 'renamed'
    elif change == 'trace_name': data['traces'][0]['name'] = 'renamed'
    elif change == 'signal_order': data['traces'].reverse()
    elif change == 'box_width': data['box']['width'] *= 2
    elif change == 'boundary': data['box']['sides'] = 'ground'
    elif change == 'edge': data['mesh']['edge_size'] /= 2
    elif change == 'grade': data['mesh']['grade'] /= 2
    changed = CrossSectionDocument.from_dict(data)
    reuse = material._MaterialMeshReuse()
    calls, seen = [], []

    def mesh(section, **options):
        assert reuse._meshed is reuse._c0 is reuse._key is None
        calls.append(object())
        return calls[-1]

    def sweep(meshed, frequency, samples, *, c0):
        seen.append((meshed, c0))
        return SimpleNamespace(C0=np.eye(2))

    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(material, '_dispersive_from_mesh', sweep)
    first = reuse.evaluate(doc, [F], {})
    reuse.evaluate(CrossSectionDocument.loads(doc.dumps()), [F], {})
    reuse.evaluate(changed, [F], {})
    reuse.evaluate(doc, [F], {})  # One entry: the original is no longer retained.
    assert len(calls) == 3
    assert seen[0][0] is seen[1][0] is calls[0]
    assert seen[1][1] is first.C0
    assert all(seen[i][1] is None for i in (0, 2, 3))


@pytest.mark.parametrize('invalid', ['unknown_region', 'frequency', 'table_range', 'tilted_pair'])
def test_cache_hit_does_not_bypass_material_rejection(invalid, monkeypatch):
    doc = document('z_diff')
    reuse = material._MaterialMeshReuse()
    good = material._material_input(F, models(4, 'scalar'))
    material._analyze_material(doc, good, 'z_diff', mesh_reuse=reuse)
    value = material._material_input(F, models(4, 'scalar'))
    if invalid == 'unknown_region': value['materials']['unknown'] = value['materials'].pop('dielectric')
    elif invalid == 'frequency': value['frequency_hz'] = float('nan')
    elif invalid == 'table_range':
        value = material._material_input(F, {
            'dielectric': TabulatedDielectric([2*F, 3*F], [3, 4], [.01, .02])})
    else: value = material._material_input(F, models(4, 'tilted'))

    def forbidden(*args, **kwargs):
        pytest.fail('invalid cached material reached field or mesh evaluation')

    monkeypatch.setattr(CrossSection, 'mesh', forbidden)
    monkeypatch.setattr(material, '_dispersive_from_mesh', forbidden)
    with pytest.raises(ValueError):
        material._analyze_material(doc, value, 'z_diff', mesh_reuse=reuse)


def test_failed_changed_mesh_discards_old_entry_and_preserves_exception(monkeypatch):
    doc = document('z0')
    changed = CrossSectionDocument(doc.section, mesh={**MESH, 'edge_size': MESH['edge_size']/2})
    reuse = material._MaterialMeshReuse()
    calls = []
    cause = RuntimeError('injected mesher failure')

    def mesh(section, **options):
        calls.append(options)
        if len(calls) == 2: raise cause
        return object()

    monkeypatch.setattr(CrossSection, 'mesh', mesh)
    monkeypatch.setattr(material, '_dispersive_from_mesh',
                        lambda *args, **kwargs: SimpleNamespace(C0=np.eye(1)))
    reuse.evaluate(doc, [F], {})
    with pytest.raises(RuntimeError) as caught:
        reuse.evaluate(changed, [F], {})
    assert caught.value is cause
    assert reuse._key is reuse._meshed is reuse._c0 is None
    reuse.evaluate(doc, [F], {})
    assert len(calls) == 3
