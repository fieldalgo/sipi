# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal fixed-frequency material contract for real quasi-static impedance."""
from collections.abc import Mapping
from copy import deepcopy

import numpy as np

from .dielectric import (dielectric_to_dict, dielectric_from_dict, dispersive_line,
                         _material_samples, _dispersive_from_mesh)
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


class _MaterialMeshReuse:
    """One call's last exact input mesh and vacuum capacitance, never a global cache."""

    def __init__(self):
        self._key = None
        self._meshed = None
        self._c0 = None

    def evaluate(self, document, frequency, samples):
        key = document.dumps()
        if key != self._key:
            # Release the old mesh before building a changed/refined one.
            self._key, self._meshed, self._c0 = None, None, None
            meshed = document.section.mesh(**document.mesh_options)
            self._key, self._meshed = key, meshed
        sweep = _dispersive_from_mesh(self._meshed, frequency, samples, c0=self._c0)
        self._c0 = sweep.C0
        return sweep


def _analyze_material(document, value, quantity, *, mesh_reuse=None):
    """Keep vacuum L and Re(C_complex); this is not lossy characteristic Z."""
    value = _validate_material_input(value, document.section, quantity)
    if mesh_reuse is None:
        sweep = dispersive_line(document.section, [value['frequency_hz']],
                                materials=_models(value), **document.mesh_options)
    else:
        # Material validation/sampling is repeated even when geometry is reused.
        frequency, samples = _material_samples(document.section,
            [value['frequency_hz']], _models(value))
        sweep = mesh_reuse.evaluate(document, frequency, samples)
    return LineParameters(sweep.names, sweep.C[0], sweep.C0, sweep.L, -sweep.C_complex[0].imag)


def _is_material_parameter(name):
    # All supported templates use these names for scalar constitutive inputs.
    return 'eps_r' in name or 'tan_delta' in name


def _material_leaf(evaluation, binding):
    """Resolve an explicit numeric leaf below a canonical model's parameters."""
    _keys(binding, ('region', 'path'), where='material variable')
    region, path = binding['region'], binding['path']
    if not isinstance(region, str) or region not in evaluation['materials']:
        raise ValueError('material variable must name an overridden region')
    if not isinstance(path, list) or not path:
        raise ValueError('material variable path must be a nonempty list')
    node = evaluation['materials'][region]['parameters']
    for key in path:
        parent = node
        if isinstance(parent, dict) and isinstance(key, str) and key in parent:
            node = parent[key]
        elif isinstance(parent, list) and type(key) is int and 0 <= key < len(parent):
            node = parent[key]
        else:
            raise ValueError('material variable path does not select an existing field')
    if type(node) not in (int, float) or not np.isfinite(node):
        raise ValueError('material variable must select a finite numeric leaf')
    return parent, path[-1]


def _material_bindings(bindings, evaluation, geometry_names):
    if evaluation is None or not isinstance(bindings, dict) or not 1 <= len(bindings) <= 8:
        raise ValueError('material_variables needs 1 to 8 bindings and material evaluation')
    targets = set()
    for alias, binding in bindings.items():
        if not isinstance(alias, str) or not alias.strip() or alias in geometry_names:
            raise ValueError('material aliases must be nonempty and distinct from template parameters')
        _material_leaf(evaluation, binding)
        target = (binding['region'], tuple(binding['path']))
        if target in targets:
            raise ValueError('material variables must select distinct targets')
        targets.add(target)
    return deepcopy(bindings)


def _sample_material(data, values):
    evaluation = deepcopy(data.get('material_evaluation'))
    bindings = data.get('material_variables', {})
    for variable, value in zip(data['sampling']['variables'], values):
        if variable['name'] in bindings:
            parent, key = _material_leaf(evaluation, bindings[variable['name']])
            parent[key] = float(value)
    return evaluation
