# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Same-boundary quadratic reference; PCB differences are observations only."""
from importlib import metadata
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pytest
from galerkin import annulus_mesh, rectangle_mesh
from sipi import coupled_microstrip
from sipi.conductor import surface_current_factors
from quadratic_conductor import quadratic_surface_factors
from crosscheck import Stopwatch, emit, make_record, observable, relative_difference


def _record_vacuum_mesh(field, factor, record_property):
    """Opt-in snapshot of the actual solve inputs, without remeshing or pickle."""
    destination = os.environ.get('SIPI_NUMERICAL_MESH_OUTPUT')
    if destination is None:
        return
    output = Path(destination)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f'paired-surface-{factor:g}.npz'
    arrays = dict(nodes=field.mesh.nodes, triangles=field.mesh.triangles,
                  ground=field.ground, signal_names=np.asarray(list(field.signals)))
    arrays.update({f'signal_{i}': nodes for i, nodes in enumerate(field.signals.values())})
    # An explicit output directory must be fresh: never replace a failed run.
    with path.open('xb') as stream:
        np.savez_compressed(stream, **arrays)
    record_property('vacuum_mesh_snapshot', json.dumps(dict(
        file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        nodes=int(field.mesh.num_nodes), triangles=int(field.mesh.num_triangles),
        scope='vacuum surface-current inputs; no dielectric or remeshing')))


def test_quadratic_reference_parallel_plate_exact_parts_and_charge():
    width, height = .002, .001
    mesh = rectangle_mesh(width, height, 8, 4)
    r = quadratic_surface_factors(mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom'])
    np.testing.assert_allclose(r['parts'][:, 0, 0], [1/width, 1/width], rtol=1e-10, atol=0)
    np.testing.assert_allclose(r['current_integrals'], [[1], [-1]], rtol=1e-10, atol=0)


def test_quadratic_reference_coax_geometry_limit(record_property):
    a, b = .001, .002
    expected = np.array([1/(2*np.pi*a), 1/(2*np.pi*b)])
    records = []
    for radial, angular in [(8, 64), (16, 128)]:
        mesh = annulus_mesh(a, b, radial, angular)
        r = quadratic_surface_factors(mesh, {'inner': mesh.boundary['inner']}, mesh.boundary['outer'])
        error = float(np.max(abs(r['parts'][:, 0, 0]/expected-1)))
        records.append(dict(radial=radial, angular=angular, parts=r['parts'].tolist(),
                            relative_error=error, current_error=r['current_error']))
    record_property('quadratic_coax', json.dumps(records))
    assert records[-1]['relative_error'] < .01


@pytest.mark.parametrize('factor', [1., .5], ids=['coarse', 'fine'])
def test_coupled_surface_against_same_boundary_quadratic_reference(factor, record_property):
    section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                                 thickness=.05e-3, eps_r=4)
    options = {k: v*factor for k, v in dict(edge_size=5e-6, far_size=.2e-3, grade=.1).items()}
    field = section.mesh(**options)
    _record_vacuum_mesh(field, factor, record_property)
    clock = Stopwatch()
    with clock('openphysics'):
        ours = surface_current_factors(field.mesh, field.signals, field.ground)
    with clock('reference'):
        reference = quadratic_surface_factors(field.mesh, field.signals, field.ground)
    observations = [observable('C0', 'F/m', 'relative difference', relative_difference(ours.C0, reference['C0']))]
    for i, name in enumerate([*ours.names, 'reference']):
        observations.append(observable(name+' boundary Q', '1/m', 'relative difference',
                                       relative_difference(ours.parts[i], reference['parts'][i])))
    record = make_record(case=f'paired-surface-p1-p2-{factor:g}', physics='PEC vacuum surface-current dual',
        api='sipi.surface_current_factors', discretization='P1 boundary normal derivative',
        tool='scikit-fem', tool_discretization='P2 potential and fourth-order facet quadrature',
        matched=['same nodes, triangles and finite copper boundaries',
                 'two signal voltage bases, bottom plane grounded, top/sides insulated',
                 'independent vacuum energy C0 and unit-current normalization'],
        not_matched=['different field interpolation; differences are report-only',
                     'no measured board, roughness calibration or inferred error bound'],
        observables=observations, stopwatch=clock,
        analytical_acceptance='independent P2 plane/coax anchors; original P1 mesh/flux gates remain separate')
    record['openphysics'].update(distribution='sipi', version=metadata.version('sipi'))
    emit(record)
    # Preserve small mutual entries and flux diagnostics instead of hiding
    # them behind a matrix norm dominated by the diagonal.
    record_property('boundary_current_comparison', json.dumps(dict(
        mesh=section.mesh_settings(**options), nodes=int(field.mesh.num_nodes),
        p1=dict(parts=ours.parts.tolist(), current_integrals=ours.current_integrals.tolist(),
                C0=ours.C0.tolist(), current_error=ours.current_error),
        p2={k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in reference.items()})))
