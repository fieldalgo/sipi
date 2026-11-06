# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal fixed-frequency material contract for real quasi-static impedance."""
from collections.abc import Mapping

import numpy as np

from .dielectric import (dielectric_to_dict, dielectric_from_dict, dispersive_line,
                         _material_samples)
from .document import _keys
from .network import _real
from .quasistatic import LineParameters


def _frequency(value):
    f = _real('frequency_hz', value)
    if f.ndim != 0 or f < 0:
        raise ValueError('frequency_hz must be a finite scalar >= 0')
    return float(f)


def _material_input(frequency, materials):
    if frequency is None and materials is None:
        return None
    if frequency is None or materials is None or not isinstance(materials, Mapping):
        raise ValueError('frequency and materials must be supplied together')
    return dict(frequency_hz=_frequency(frequency),
                materials={name:dielectric_to_dict(model) for name, model in materials.items()})


def _models(value):
    return {name:dielectric_from_dict(model) for name, model in value['materials'].items()}


def _validate_material_input(value, section, quantity):
    _keys(value, ('frequency_hz', 'materials'), where='material evaluation')
    frequency = _frequency(value['frequency_hz'])
    if not isinstance(value['materials'], dict):
        raise ValueError('materials must map region names to dielectric documents')
    models = _models(value)
    _, samples = _material_samples(section, [frequency], models)
    if quantity == 'z_diff':
        for eps in samples.values():
            if eps.ndim == 3:
                scale = max(np.max(abs(eps.real)), np.max(abs(eps.imag)))
                if np.any(abs(eps[:, 0, 1]/scale) > 1e-12):
                    raise ValueError('z_diff requires diagonal transverse tensors; tilted axes can break pair symmetry')
    return _material_input(frequency, models)


def _analyze_material(document, value, quantity):
    """Keep vacuum L and Re(C_complex); this is not lossy characteristic Z."""
    value = _validate_material_input(value, document.section, quantity)
    sweep = dispersive_line(document.section, [value['frequency_hz']],
                            materials=_models(value), **document.mesh_options)
    return LineParameters(sweep.names, sweep.C[0], sweep.C0, sweep.L, -sweep.C_complex[0].imag)


def _is_material_parameter(name):
    # All supported templates use these names for scalar constitutive inputs.
    return 'eps_r' in name or 'tan_delta' in name
