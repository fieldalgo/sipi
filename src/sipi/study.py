# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reproducible impedance studies; no resampling or removal of failed rows."""
from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from itertools import product
import json
from types import MappingProxyType

import numpy as np

from . import templates
from .sampling import _numbers, _scalar, _integer, _copy, _validate_sampling, _sample_values
from .document import CrossSectionDocument, _keys, _unique_object
from .impedance_material import (_material_input, _validate_material_input,
                                 _analyze_material, _is_material_parameter,
                                 _material_bindings, _sample_material, _MaterialMeshReuse)

__all__ = ['ImpedanceStudyDocument', 'StudyRow', 'ImpedanceStudy']

_TEMPLATES = {name: getattr(templates, name) for name in
              ('microstrip', 'stripline', 'coupled_microstrip', 'asymmetric_coupled_microstrip', 'grounded_coplanar',
               'asymmetric_coupled_stripline',
               'asymmetric_coupled_layered_stripline',
               'asymmetric_coupled_layered_coplanar_stripline',
               'asymmetric_coupled_grounded_coplanar',
               'asymmetric_coupled_unbacked_coplanar',
               'asymmetric_coupled_coated_grounded_coplanar',
               'asymmetric_coupled_coated_unbacked_coplanar',
               'asymmetric_coupled_coated_microstrip',
               'asymmetric_coupled_conformal_coated_microstrip',
               'asymmetric_coupled_conformal_coated_grounded_coplanar',
               'asymmetric_coupled_conformal_coated_unbacked_coplanar',
               'asymmetric_coupled_coplanar_stripline',
               'coated_microstrip', 'offset_stripline', 'coupled_stripline', 'broadside_stripline',
               'coupled_grounded_coplanar', 'layered_stripline', 'coupled_layered_stripline',
               'layered_broadside_stripline',
               'coplanar_stripline', 'coupled_coplanar_stripline',
               'layered_coplanar_stripline', 'coupled_layered_coplanar_stripline',
               'coupled_coated_microstrip', 'coated_grounded_coplanar',
               'coupled_coated_grounded_coplanar', 'unbacked_coplanar',
               'coupled_unbacked_coplanar', 'coated_unbacked_coplanar',
               'coupled_coated_unbacked_coplanar', 'conformal_coated_microstrip',
               'coupled_conformal_coated_microstrip', 'conformal_coated_grounded_coplanar',
               'coupled_conformal_coated_grounded_coplanar', 'conformal_coated_unbacked_coplanar',
               'coupled_conformal_coated_unbacked_coplanar')}
_ASYMMETRIC_HORIZONTAL_PAIRS = frozenset(('asymmetric_coupled_microstrip', 'asymmetric_coupled_stripline',
                                        'asymmetric_coupled_layered_stripline',
               'asymmetric_coupled_layered_coplanar_stripline',
                                        'asymmetric_coupled_grounded_coplanar',
                                        'asymmetric_coupled_unbacked_coplanar',
                                        'asymmetric_coupled_coated_grounded_coplanar',
               'asymmetric_coupled_coated_unbacked_coplanar',
               'asymmetric_coupled_coated_microstrip',
               'asymmetric_coupled_conformal_coated_microstrip',
               'asymmetric_coupled_conformal_coated_grounded_coplanar',
               'asymmetric_coupled_conformal_coated_unbacked_coplanar',
                                        'asymmetric_coupled_coplanar_stripline'))
_DIFFERENTIAL = frozenset(('coupled_microstrip', 'coupled_stripline', 'broadside_stripline',
                         'coupled_layered_coplanar_stripline',
                         'coupled_coplanar_stripline',
                         'coupled_grounded_coplanar', 'coupled_layered_stripline', 'coupled_coated_microstrip',
                         'coupled_coated_grounded_coplanar', 'coupled_unbacked_coplanar',
                         'coupled_coated_unbacked_coplanar', 'coupled_conformal_coated_microstrip',
                         'coupled_conformal_coated_grounded_coplanar', 'coupled_conformal_coated_unbacked_coplanar'))
_HORIZONTAL_PAIRS = frozenset(('coupled_microstrip', 'coupled_stripline', 'coupled_grounded_coplanar',
                             'coupled_layered_coplanar_stripline',
                             'coupled_coplanar_stripline',
                             'coupled_layered_stripline', 'coupled_coated_microstrip',
                             'coupled_coated_grounded_coplanar', 'coupled_unbacked_coplanar',
                             'coupled_coated_unbacked_coplanar', 'coupled_conformal_coated_microstrip',
                             'coupled_conformal_coated_grounded_coplanar', 'coupled_conformal_coated_unbacked_coplanar'))


def _parameters(data, values):
    params = dict(data['parameters'])
    params.update((v['name'], float(value)) for v, value in zip(data['sampling']['variables'], values)
                  if v['name'] not in data.get('material_variables', {}))
    if data['fixed_pitch_m'] is not None:
        half_widths = (params['left_width']/2+params['right_width']/2
                       if data['template'] in _ASYMMETRIC_HORIZONTAL_PAIRS else params['width'])
        params['gap'] = data['fixed_pitch_m']-half_widths
    spacing = data.get('fixed_plane_spacing_m')
    if spacing is not None:
        names = {v['name'] for v in data['sampling']['variables']}
        independent = 'lower_height' if 'lower_height' in names else 'upper_height'
        derived = 'upper_height' if independent == 'lower_height' else 'lower_height'
        params[derived] = spacing-params[independent]
    return params


@dataclass(frozen=True)
class StudyRow:
    index: int
    parameters: object
    document: CrossSectionDocument | None
    impedance: float | None
    error_type: str | None
    error: str | None
    material_evaluation_json: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))

    @property
    def complete(self):
        return self.error is None


@dataclass(frozen=True)
class ImpedanceStudy:
    input_json: str
    quantity: str
    rows: tuple[StudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))

    @property
    def failed(self):
        return sum(not row.complete for row in self.rows)


class ImpedanceStudyDocument:
    """Strict impedance-study/1 through /4, with resolved nominal mesh settings.

    Sampling is separate from expensive FEM evaluation. Normal samples are
    unbounded: invalid physical inputs remain failed rows, never resampled.
    Fixed horizontal pitch applies to edge-coupled microstrip, stripline (including layered) and
    coplanar pairs. Outer coplanar grounds retain ground_gap, not position.
    The broadside gap is vertical and is never derived from horizontal pitch.
    Version 2 adds fixed total plane spacing for the two-dielectric stripline
    and buried coplanar templates;
    exactly one layer height is sampled and the other is derived.
    Version 3 adds fixed-frequency scalar/principal-axis material overrides;
    only geometry variables are sampled. Its full input_json is required to
    replay a row: the row's document contains geometry, not these overrides.
    Version 4 adds explicit aliases bound to numeric material-model leaves.
    Sampling can combine geometry and material variables; each row preserves
    its actual material_evaluation_json, including invalid sampled values.
    """
    def __init__(self, template, parameters, *, sampling, quantity, mesh=None, fixed_pitch_m=None,
                 fixed_plane_spacing_m=None, frequency=None, materials=None, material_variables=None):
        data = dict(schema='sipi.impedance-study/1', template=template,
            parameters=parameters, sampling=sampling, quantity=quantity,
            mesh={} if mesh is None else mesh, fixed_pitch_m=fixed_pitch_m)
        if fixed_plane_spacing_m is not None:
            data.update(schema='sipi.impedance-study/2', fixed_plane_spacing_m=fixed_plane_spacing_m)
        evaluation = _material_input(frequency, materials)
        if evaluation is not None:
            data.update(schema='sipi.impedance-study/3', fixed_plane_spacing_m=fixed_plane_spacing_m,
                        material_evaluation=evaluation)
        if material_variables is not None:
            data.update(schema='sipi.impedance-study/4', fixed_plane_spacing_m=fixed_plane_spacing_m,
                        material_evaluation=evaluation, material_variables=material_variables)
        self._data = self._validate(data)

    @staticmethod
    def _validate(data):
        data = _copy(data)
        if not isinstance(data, dict):
            raise ValueError('impedance study must be an object')
        if data.get('schema') not in ('sipi.impedance-study/1', 'sipi.impedance-study/2', 'sipi.impedance-study/3', 'sipi.impedance-study/4'):
            raise ValueError('unsupported impedance-study schema')
        fields = ['schema', 'template', 'parameters', 'sampling', 'quantity', 'mesh', 'fixed_pitch_m']
        if data['schema'] in ('sipi.impedance-study/2', 'sipi.impedance-study/3', 'sipi.impedance-study/4'):
            fields.append('fixed_plane_spacing_m')
        if data['schema'] in ('sipi.impedance-study/3', 'sipi.impedance-study/4'):
            fields.append('material_evaluation')
        if data['schema'] == 'sipi.impedance-study/4':
            fields.append('material_variables')
        _keys(data, fields, where='impedance study')
        template = data['template']
        if not isinstance(template, str) or template not in _TEMPLATES:
            raise ValueError('unsupported study template')
        factory = _TEMPLATES[template]
        if not isinstance(data['parameters'], dict):
            raise ValueError('parameters must be a template argument object')
        try:
            bound = signature(factory).bind(**data['parameters'])
        except TypeError as exc:
            raise ValueError('unknown or missing template parameters') from exc
        bound.apply_defaults()
        parameters = {k: None if v is None else _scalar(v) for k, v in bound.arguments.items()}
        section = factory(**parameters)
        if not isinstance(data['mesh'], dict):
            raise ValueError('mesh must be an object')
        doc = CrossSectionDocument(section, mesh=data['mesh'])
        mesh = section.mesh_settings(**doc.mesh_options)
        allowed = (('z_diff_forward',) if template in _ASYMMETRIC_HORIZONTAL_PAIRS or template == 'layered_broadside_stripline' else
                   ('z_diff', 'z_diff_forward') if template in _DIFFERENTIAL else ('z0',))
        quantity = data['quantity']
        if not isinstance(quantity, str) or quantity not in allowed:
            raise ValueError('this template requires quantity='+' or '.join(allowed))
        evaluation = (_validate_material_input(data['material_evaluation'], section, quantity)
                      if data['schema'] in ('sipi.impedance-study/3', 'sipi.impedance-study/4') else None)
        forbidden = {name for name in parameters if _is_material_parameter(name)} if evaluation is not None else ()
        bindings = (_material_bindings(data['material_variables'], evaluation, parameters)
                    if data['schema'] == 'sipi.impedance-study/4' else {})
        sampling = _validate_sampling(data['sampling'], set(parameters) | set(bindings), forbidden=forbidden)
        if not set(bindings) <= {v['name'] for v in sampling['variables']}:
            raise ValueError('every material binding must be sampled')
        kind, variables = sampling['kind'], sampling['variables']
        names = [v['name'] for v in variables]
        pitch = data['fixed_pitch_m']
        if pitch is not None:
            pitch = _scalar(pitch, positive=True)
            if template in _ASYMMETRIC_HORIZONTAL_PAIRS:
                if not {'left_width', 'right_width'}.intersection(names) or 'gap' in names:
                    raise ValueError('fixed pitch requires left_width or right_width sampling, '
                                     'without gap sampling')
                nominal_width = parameters['left_width']/2+parameters['right_width']/2
            else:
                if template not in _HORIZONTAL_PAIRS or 'width' not in names or 'gap' in names:
                    raise ValueError('fixed pitch requires an edge-coupled pair with '
                                     'width sampling, without gap sampling')
                nominal_width = parameters['width']
            if abs(nominal_width+parameters['gap']-pitch) > 1e-12*pitch:
                raise ValueError('nominal width (mean for unequal pairs) + gap must equal fixed pitch')
        canonical = dict(schema=data['schema'], template=template, parameters=parameters,
                         quantity=quantity, mesh=mesh, sampling=sampling, fixed_pitch_m=pitch)
        if bindings:
            canonical['material_variables'] = bindings
        if evaluation is not None:
            canonical['material_evaluation'] = evaluation
        if data['schema'] in ('sipi.impedance-study/2', 'sipi.impedance-study/3', 'sipi.impedance-study/4'):
            spacing = data['fixed_plane_spacing_m']
            if spacing is not None:
                spacing = _scalar(spacing, positive=True)
                if (template not in ('layered_stripline', 'coupled_layered_stripline',
                                     'asymmetric_coupled_layered_stripline',
               'asymmetric_coupled_layered_coplanar_stripline',
                                     'layered_coplanar_stripline', 'coupled_layered_coplanar_stripline')
                        or len({'lower_height', 'upper_height'} & set(names)) != 1):
                    raise ValueError('fixed plane spacing requires a layered stripline '
                                     'and exactly one sampled layer height')
                if abs(parameters['lower_height']+parameters['upper_height']-spacing) > 1e-12*spacing:
                    raise ValueError('nominal lower_height + upper_height must equal fixed plane spacing')
            canonical['fixed_plane_spacing_m'] = spacing
        # Check the requested finite bounds before any solves. This does not
        # establish worst-case impedance or validate an unbounded normal domain.
        if kind != 'normal':
            bounds = [(v['lower'], v['upper']) for v in variables]
            for corner in product(*bounds):
                corner_section = factory(**_parameters(canonical, corner))
                if bindings:
                    _validate_material_input(_sample_material(canonical, corner), corner_section, quantity)
        return canonical

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def samples(self):
        """Read-only (samples, independent variables), in listed variable order."""
        return _sample_values(self._data['sampling'])

    def sample_parameters(self):
        """Fresh full template arguments per sample, including any derived gap."""
        return [_parameters(self._data, row) for row in self.samples()]

    def sample_material_evaluations(self):
        """Detached actual material inputs per row; invalid normal values remain.

        Returns None entries for legacy studies without material overrides.
        Physical validation takes place during analyze(), not by resampling.
        """
        return [_sample_material(self._data, row) for row in self.samples()]

    def analyze(self, *, max_evaluations=128):
        """Evaluate every planned sample, retaining errors; no partial statistics.

        max_evaluations is a caller's explicit budget, checked before any solve.
        Explicit-material rows may reuse the last exact document's mesh and
        vacuum capacitance within this call. Every material is evaluated again;
        changed geometry is remeshed. No per-row convergence is inferred.
        """
        budget = _integer(max_evaluations, 2, 10000)
        parameters = self.sample_parameters()
        if len(parameters) > budget:
            raise ValueError('sample count exceeds max_evaluations before any solve')
        data, rows = self._data, []
        samples = self.samples()
        material_mesh = _MaterialMeshReuse()
        for i, values in enumerate(parameters):
            doc = None
            evaluation = _sample_material(data, samples[i])
            saved = (None if data['schema'] != 'sipi.impedance-study/4' else
                     json.dumps(evaluation, sort_keys=True, allow_nan=False))
            try:
                section = _TEMPLATES[data['template']](**values)
                doc = CrossSectionDocument(section, mesh=data['mesh'])
                line = (doc.analyze() if evaluation is None
                        else _analyze_material(doc, evaluation, data['quantity'],
                                               mesh_reuse=material_mesh))
                value = float(line.even_odd()['z_diff'] if data['quantity'] == 'z_diff'
                              else getattr(line, data['quantity']))
                if not np.isfinite(value) or value <= 0:
                    raise ValueError('solver returned a nonpositive or nonfinite impedance')
                rows.append(StudyRow(i, values, doc, value, None, None, saved))
            except Exception as exc:
                rows.append(StudyRow(i, values, doc, None, type(exc).__name__, str(exc), saved))
        summary = None
        if all(row.complete for row in rows):
            z = np.array([row.impedance for row in rows])
            summary = dict(minimum=float(z.min()), maximum=float(z.max()), mean=float(z.mean()),
                           sample_std=float(z.std(ddof=1)), p05=float(np.quantile(z, .05, method='linear')),
                           p95=float(np.quantile(z, .95, method='linear')))
        return ImpedanceStudy(self.dumps(), data['quantity'], tuple(rows), summary)
