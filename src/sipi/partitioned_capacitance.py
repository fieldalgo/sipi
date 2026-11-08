# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Static capacitance for explicitly partitioned, prescribed-electrode domains."""
from .capacitance3d import Capacitance3D, _prepare_inputs, _extract_prepared

__all__ = ['extract_partitioned_capacitance_3d']


def extract_partitioned_capacitance_3d(mesh, *, eps_r=1., conductors, ground) -> Capacitance3D:
    """Extract total Maxwell C[F] across separated bounded dielectric domains.

    Every connected mesh component must touch a prescribed electrode. Every
    named signal must connect to global ground through the electrode/component
    incidence graph. Signal-only or ground-only components are allowed when
    those electrodes are referenced elsewhere; their fields are constant.
    This does not solve unknown floating-electrode voltages or identify aliases.
    The caller explicitly groups all nodes belonging to each physical electrode.

    Column j sets signal j to1V and all other signals/ground to0V. Positive real
    scalar/per-tet eps_r, disjoint nonempty electrode sets, conforming positive
    tetrahedra and detached-input checks are shared with extract_capacitance_3d.
    Unprescribed faces are insulating; geometry is explicitly bounded, not an
    automatic open boundary. Assembly, solve and raw energy/charge/Maxwell gates
    are identical. The original API still requires ground in every component.

    No per-length RLGC, return-current inductance, loss, radiation, propagation,
    measurement accuracy or automatic conductor meshing is inferred.
    """
    prepared = _prepare_inputs(mesh, eps_r, conductors, ground, require_component_ground=False)
    return _extract_prepared(*prepared)
