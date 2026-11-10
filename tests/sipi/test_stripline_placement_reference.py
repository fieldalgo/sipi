# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent thin horizontal strips between infinite Dirichlet planes.

Constant-charge midpoint collocation, analytic logarithmic self integral.
This research reference does not use a SIPI mesh or field operator.
"""
import numpy as np
from scipy.constants import epsilon_0, c
from scipy.special import roots_legendre
from scipy.linalg import solve


def parallel_plane_capacitance(widths, centres, *, spacing, height, eps_r=1., panels=160, quadrature=16):
    if not 0 < height < spacing or eps_r <= 0:
        raise ValueError('Uniform material and a height strictly between planes required.')
    edges=[x-.5*w*np.cos(np.linspace(0,np.pi,panels+1)) for w,x in zip(widths,centres)]
    left=np.concatenate([e[:-1] for e in edges]);right=np.concatenate([e[1:] for e in edges])
    length=right-left;mid=(right+left)/2
    nodes,weights=roots_legendre(quadrature)
    sample=mid[:,None]+length[:,None]*nodes/2
    dx=mid[:,None,None]-sample[None,:,:];q=dx/spacing
    # cosh(pi*q)-1 = 2*sinh(pi*q/2)^2 avoids cancellation near zero.
    regular=np.log1p(np.sin(np.pi*height/spacing)**2/np.sinh(np.pi*q/2)**2)+2*np.log(abs(q))
    def primitive(x):
        out=np.zeros_like(x);use=x!=0
        out[use]=x[use]*(np.log(abs(x[use])/spacing)-1)
        return out
    singular=-2*(primitive(mid[:,None]-left)-primitive(mid[:,None]-right))/length
    matrix=(regular@weights/2+singular)/(4*np.pi*epsilon_0*eps_r)
    rhs=np.repeat(np.eye(len(widths)),panels,axis=0)
    charges=solve(matrix,rhs,assume_a='gen')
    return np.stack([charges[i*panels:(i+1)*panels].sum(axis=0) for i in range(len(widths))])


def reference_modes(matrix, eps_r=1.):
    velocity=c/np.sqrt(eps_r)
    if len(matrix)==1:return dict(z0=1/(velocity*matrix[0,0]))
    even=1/(velocity*(matrix[0,0]+matrix[0,1]));odd=1/(velocity*(matrix[0,0]-matrix[0,1]))
    return dict(z_even=even,z_odd=odd,z_diff=2*odd,z_common=even/2)


# The reference has an infinite lateral domain; production checks below use
# finite insulated side walls and explicitly enlarge that domain.
PARAMS = dict(width=.3e-3, gap=.3e-3, plane_spacing=1e-3, trace_height=.3e-3,
              eps_r=4., box_width=6e-3, thickness=0.)
COARSE = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
FINE = dict(edge_size=2.5e-6, far_size=.0625e-3, grade=.075)


def pair_reference(panels=160, quadrature=16):
    return parallel_plane_capacitance([.3e-3, .3e-3], [-.3e-3, .3e-3],
        spacing=1e-3, height=.3e-3, eps_r=4., panels=panels, quadrature=quadrature)


def test_reference_elliptic_limit_panel_quadrature_and_reflection():
    from scipy.special import ellipk
    from scipy.constants import mu_0
    k = np.tanh(np.pi * .3 / 2)
    exact = np.sqrt(mu_0 / epsilon_0) / 4 * ellipk(1-k*k) / ellipk(k*k)
    single = parallel_plane_capacitance([.3e-3], [0], spacing=1e-3, height=.5e-3)
    assert abs(reference_modes(single)['z0'] / exact - 1) < .003
    coarse, fine = pair_reference(80), pair_reference(160)
    for key, value in reference_modes(fine, 4).items():
        assert abs(reference_modes(coarse, 4)[key] / value - 1) < .003
    np.testing.assert_allclose(fine, fine.T, rtol=1e-9)
    assert np.linalg.eigvalsh(fine).min() > 0
    for quadrature in (8, 24):
        error = np.max(abs(pair_reference(quadrature=quadrature)-fine)) / np.max(abs(fine))
        assert error < 1e-7
    mirrored = parallel_plane_capacitance([.3e-3, .3e-3], [-.3e-3, .3e-3],
        spacing=1e-3, height=.7e-3, eps_r=4.)
    np.testing.assert_allclose(mirrored, fine, rtol=1e-12)


def test_offset_pair_mesh_domain_reference_and_vertical_reflection():
    from sipi.templates import coupled_stripline
    coarse = coupled_stripline(**PARAMS).analyze(**COARSE)
    fine = coupled_stripline(**PARAMS).analyze(**FINE)
    wide = coupled_stripline(**{**PARAMS, 'box_width': .012}).analyze(**FINE)
    mirror = coupled_stripline(**{**PARAMS, 'trace_height': .7e-3}).analyze(**FINE)
    ref = pair_reference(); modes = reference_modes(ref, 4)
    for other, limit in [(coarse, .01), (wide, .005), (mirror, .005)]:
        assert np.max(abs(other.C-fine.C)) / np.max(abs(fine.C)) < limit
        for key in modes: assert abs(other.even_odd()[key]/fine.even_odd()[key]-1) < limit
    assert np.max(abs(fine.C-ref)) / np.max(abs(ref)) < .02
    for key, value in modes.items(): assert abs(fine.even_odd()[key]/value-1) < .02
    print('parallel-plane reference', modes, 'fine', fine.even_odd())


def test_independent_finite_metal_complex_and_vacuum_assembly():
    from crosscheck import require_tool, Stopwatch, make_record, observable, emit
    from importlib.metadata import version
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    from sipi.templates import coupled_stripline
    clock = Stopwatch()
    with clock('openphysics'):
        m = coupled_stripline(**{**PARAMS, 'thickness': 35e-6, 'tan_delta': .02}).mesh(**COARSE)
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
    record = make_record(case='offset-stripline-placement-pair', physics='uniform lossy electrostatics',
        api='sipi.templates.coupled_stripline', discretization='conforming P1, explicit bottom-face height and finite rectangular copper',
        tool='scikit-fem', tool_discretization='independent complex/vacuum P1 assembly and Dirichlet energy',
        matched=['same mesh, epsilon4/loss tangent.02, grounded top/bottom, insulated side walls'],
        not_matched=['no measured PCB material or three-dimensional transition'],
        observables=[observable(name, 'F/m', 'max normalized matrix difference', error, 1e-10)
                     for name, error in zip(['C', 'C_loss', 'C0'], errors)],
        analytical_acceptance='separate thin-strip parallel-plane Green panels and elliptic-integral limit; mesh/domain/reflection gates',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi', version=version('sipi')); emit(record)
    assert max(errors) < 1e-10
