# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Record existing convergence observations before an assertion can fail."""
import json
import platform
from importlib.metadata import version

import numpy as np
from sipi import CrossSectionDocument


def record_conductor_refinement(record_property, section, coarse, fine, coarse_mesh, fine_mesh):
    """Serialize already computed fields; do not solve, accept or alter a result."""
    samples = {}
    for name, result, options in [('coarse', coarse, coarse_mesh), ('fine', fine, fine_mesh)]:
        samples[name] = dict(
            mesh=section.mesh_settings(**options),
            frequency_hz=result.frequency.tolist(), R_ohm_per_m=result.R.tolist(),
            L_internal_h_per_m=result.L_internal.tolist(),
            C0_f_per_m=result.factors.C0.tolist(),
            current_integrals=result.factors.current_integrals.tolist(),
            current_error=result.factors.current_error,
            boundary_parts_per_m=result.factors.parts.tolist())
    payload = dict(
        schema='sipi.conductor-refinement-diagnostic/1',
        platform=platform.platform(), python=platform.python_version(),
        versions={name: version(name) for name in ('numpy', 'scipy', 'galerkin', 'meshine')},
        cross_section=CrossSectionDocument(section).to_dict(), samples=samples,
        relative_changes={name: float(np.max(abs(getattr(coarse, name)-getattr(fine, name)))
                                     / np.max(abs(getattr(fine, name))))
                          for name in ('R', 'L_internal')})
    record_property('conductor_refinement', json.dumps(payload, sort_keys=True, allow_nan=False))
