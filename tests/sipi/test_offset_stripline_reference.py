# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent limits and convergence for the explicit single buried trace."""
import numpy as np
from scipy.constants import epsilon_0
from test_stripline_placement_reference import parallel_plane_capacitance, reference_modes

# The reference has an infinite lateral domain; production checks below use
# finite insulated side walls and explicitly enlarge that domain.
PARAMS = dict(width=.3e-3, plane_spacing=1e-3, trace_height=.3e-3,
              eps_r=4., box_width=6e-3, thickness=0.)
COARSE = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
FINE = dict(edge_size=2.5e-6, far_size=.0625e-3, grade=.075)


def single_reference(panels=160, quadrature=16):
    return parallel_plane_capacitance([.3e-3], [0],
        spacing=1e-3, height=.3e-3, eps_r=4., panels=panels, quadrature=quadrature)


def test_reference_elliptic_limit_panel_quadrature_and_reflection():
    from scipy.special import ellipk
    from scipy.constants import mu_0
    k = np.tanh(np.pi * .3 / 2)
    exact = np.sqrt(mu_0 / epsilon_0) / 4 * ellipk(1-k*k) / ellipk(k*k)
    single = parallel_plane_capacitance([.3e-3], [0], spacing=1e-3, height=.5e-3)
    assert abs(reference_modes(single)['z0'] / exact - 1) < .003
    coarse, fine = single_reference(80), single_reference(160)
    for key, value in reference_modes(fine, 4).items():
        assert abs(reference_modes(coarse, 4)[key] / value - 1) < .003
    np.testing.assert_allclose(fine, fine.T, rtol=1e-9)
    assert np.linalg.eigvalsh(fine).min() > 0
    for quadrature in (8, 24):
        error = np.max(abs(single_reference(quadrature=quadrature)-fine)) / np.max(abs(fine))
        assert error < 1e-7
    mirrored = parallel_plane_capacitance([.3e-3], [0],
        spacing=1e-3, height=.7e-3, eps_r=4.)
    np.testing.assert_allclose(mirrored, fine, rtol=1e-12)


def test_offset_single_mesh_domain_reference_and_vertical_reflection():
    from sipi.templates import offset_stripline
    coarse = offset_stripline(**PARAMS).analyze(**COARSE)
    fine = offset_stripline(**PARAMS).analyze(**FINE)
    wide = offset_stripline(**{**PARAMS, 'box_width': .012}).analyze(**FINE)
    mirror = offset_stripline(**{**PARAMS, 'trace_height': .7e-3}).analyze(**FINE)
    ref = single_reference(); modes = reference_modes(ref, 4)
    for other, limit in [(coarse, .01), (wide, .005), (mirror, .005)]:
        assert np.max(abs(other.C-fine.C)) / np.max(abs(fine.C)) < limit
        for key in modes: assert abs({'z0': other.z0}[key]/{'z0': fine.z0}[key]-1) < limit
    assert np.max(abs(fine.C-ref)) / np.max(abs(ref)) < .02
    for key, value in modes.items(): assert abs({'z0': fine.z0}[key]/value-1) < .02
    print('parallel-plane reference', modes, 'fine', {'z0': fine.z0})


def test_independent_finite_metal_complex_and_vacuum_assembly():
    from crosscheck import require_tool, Stopwatch, make_record, observable, emit
    from importlib.metadata import version
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from sipi.templates import offset_stripline
    clock = Stopwatch()
    with clock('openphysics'):
        m = offset_stripline(**{**PARAMS, 'thickness': 35e-6, 'tan_delta': .02}).mesh(**COARSE)
        actual = m.line_parameters()
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T, m.mesh.triangles.T), skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u, v, w): return w.eps * dot(grad(u), grad(v))
        fixed = np.unique(np.concatenate([m.ground, *m.signals.values()])); values = []
        for eps in [m.eps_r * (1-1j*m.tan_delta), np.ones_like(m.eps_r)]:
            matrix = skfem.asm(form, basis, eps=eps[:, None]); potentials = []
            for nodes in m.signals.values():
                bc = np.zeros(basis.N, complex); bc[nodes] = 1
                potentials.append(skfem.solve(*skfem.condense(matrix, np.zeros(basis.N, complex), x=bc, D=fixed)))
            u = np.array(potentials).T; values.append(epsilon_0 * (u.T @ (matrix @ u)))
    errors = [float(np.max(abs(a-b)) / np.max(abs(b))) for a, b in
              [(actual.C, values[0].real), (actual.C_loss, -values[0].imag), (actual.C0, values[1].real)]]
    record = make_record(case='offset-stripline-single-form', physics='uniform lossy electrostatics',
        api='sipi.templates.offset_stripline', discretization='conforming P1, explicit bottom-face height and finite rectangular copper',
        tool='scikit-fem', tool_discretization='independent complex/vacuum P1 assembly and Dirichlet energy',
        matched=['same mesh, epsilon4/loss tangent.02, grounded top/bottom, insulated side walls'],
        not_matched=['no measured PCB material or three-dimensional transition'],
        observables=[observable(name, 'F/m', 'max normalized matrix difference', error, 1e-10)
                     for name, error in zip(['C', 'C_loss', 'C0'], errors)],
        analytical_acceptance='separate thin-strip parallel-plane Green panels and elliptic-integral limit; mesh/domain/reflection gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=version('sipi')); emit(record)
    assert max(errors) < 1e-10
