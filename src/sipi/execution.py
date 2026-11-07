# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transport-independent execution of saved engine documents.

No file, network, process or browser operations occur here. Callers own process
isolation, cancellation and resource limits; an input-byte/sample budget alone
does not bound a field solve's memory or time.
"""
from __future__ import annotations

import json
import math

import numpy as np

from .document import CrossSectionDocument, _unique_object
from .study import ImpedanceStudyDocument
from .design_document import ImpedanceDesignDocument
from .design import GoalSeekError
from .aperture import ApertureDocument
from .aperture_section import ApertureSectionDocument
from .aperture_study import ApertureStudyDocument, ApertureDesignDocument, CapacitanceGoalError
from .line_model import TransmissionLineDocument
from .volume_line import VolumeLineDocument
from .lumped import LumpedNetworkDocument
from .assembly_document import NetworkAssemblyDocument
from .network_document import NetworkTransformDocument
from .circuit_document import CircuitDocument
from .modes import ModeTrackingError
from .capacitance3d_document import Capacitance3DDocument

__all__ = ['saved_schemas', 'normalize_saved', 'execute_saved']

_REGISTRY = {
    **{f'sipi.cross-section/{v}': CrossSectionDocument for v in (1, 2, 3)},
    **{f'sipi.impedance-study/{v}': ImpedanceStudyDocument for v in (1, 2, 3)},
    **{f'sipi.impedance-design/{v}': ImpedanceDesignDocument for v in (1, 2)},
    'sipi.circular-aperture/1': ApertureDocument,
    'sipi.aperture-section/1': ApertureSectionDocument,
    'sipi.aperture-study/1': ApertureStudyDocument,
    'sipi.aperture-design/1': ApertureDesignDocument,
    **{f'sipi.transmission-line/{v}': TransmissionLineDocument for v in (1, 2)},
    'sipi.volume-line/1': VolumeLineDocument,
    'sipi.lumped-network/1': LumpedNetworkDocument,
    'sipi.network-assembly/1': NetworkAssemblyDocument,
    **{f'sipi.network-transforms/{v}': NetworkTransformDocument for v in (1, 2)},
    'sipi.circuit/1': CircuitDocument,
    'sipi.capacitance-3d/1': Capacitance3DDocument,
}


def saved_schemas():
    """Return supported input schema names, independent of their ordering."""
    return tuple(sorted(_REGISTRY))


def _integer(name, value, minimum, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, int) or value < minimum
            or (maximum is not None and value > maximum)):
        raise ValueError(f'{name} must be an integer >= {minimum}'
                         + ('' if maximum is None else f' and <= {maximum}'))
    return value


def _reject_number(value):
    raise ValueError(f'nonfinite JSON number: {value}')


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        _reject_number(value)
    return result


def _load(text, max_input_bytes):
    limit = _integer('max_input_bytes', max_input_bytes, 1)
    if not isinstance(text, str):
        raise TypeError('saved input must be JSON text')
    if len(text.encode('utf-8')) > limit:
        raise ValueError('saved input exceeds max_input_bytes')
    data = json.loads(text, object_pairs_hook=_unique_object,
                      parse_constant=_reject_number, parse_float=_float)
    if not isinstance(data, dict) or not isinstance(data.get('schema'), str):
        raise ValueError('saved input must be an object with a schema string')
    cls = _REGISTRY.get(data['schema'])
    if cls is None:
        raise ValueError(f'unsupported saved schema: {data["schema"]!r}')
    return cls.from_dict(data)


def normalize_saved(text, *, max_input_bytes=262144):
    """Validate and return the existing document's canonical JSON.

    Parsing never performs a field solve. Some network validators do small
    algebraic calculations. No new input schema or default mesh is introduced.
    """
    return _load(text, max_input_bytes).dumps()


def _array(value):
    data = np.asarray(value)
    if not np.all(np.isfinite(data)):
        raise ValueError('execution result contains nonfinite numbers')
    if np.iscomplexobj(data):
        return dict(real=data.real.tolist(), imag=data.imag.tolist())
    return data.tolist()


def _network(network):
    return dict(frequency_hz=_array(network.frequency), port_names=list(network.port_names),
                basis=network.basis, reference_ohms=_array(network.z_ref), s=_array(network.s))


def _history(history, value):
    return [dict(parameter=row.parameter, value=getattr(row, value), stage=row.stage) for row in history]


def _study(result, value, unit):
    return dict(quantity=result.quantity, unit=unit, failed=result.failed,
        summary=None if result.summary is None else dict(result.summary),
        rows=[dict(index=row.index, parameters=dict(row.parameters),
            document=None if row.document is None else row.document.to_dict(),
            value=getattr(row, value), error_type=row.error_type, error=row.error)
            for row in result.rows])


def _design(result, value, unit):
    out = dict(quantity=result.quantity, unit=unit, parameter=result.parameter,
        target=result.target, value=getattr(result, value),
        refined_value=getattr(result, 'refined_'+value), residual=result.residual,
        refined_residual=result.refined_residual, document=result.document.to_dict(),
        history=_history(result.history, value))
    if value == 'impedance':
        out['material_evaluation'] = (None if result.material_evaluation_json is None
                                      else json.loads(result.material_evaluation_json))
    return out


def _diagnostics(result, requested):
    out = {}
    for name in requested:
        try:
            value = getattr(result, name)()
        except ValueError as exc:
            # Diagnostic rejection must not erase the already extracted RLGC/S.
            error = dict(type=type(exc).__name__, message=str(exc))
            if isinstance(exc, ModeTrackingError):
                error.update(index=exc.index, frequency_hz=exc.frequency)
            out[name] = dict(status='failed', error=error)
            continue
        keys = (('gamma_voltage', 'z_characteristic', 'y_characteristic') if name == 'characteristic'
                else ('gamma', 'voltage', 'current', 'alpha_conductor', 'alpha_dielectric',
                      'overlap', 'assignment_gap'))
        out[name] = dict(status='complete', **{key: _array(getattr(value, key)) for key in keys})
    return out


def _circuit(result):
    response = result.response
    out = dict(network=_network(result.network), response={key: _array(getattr(response, key))
        for key in ('source_voltages', 'terminations', 'a', 'b', 'voltage', 'current',
                    'condition_number', 'kvl_residual', 'wave_residual', 'network_power')},
        crosstalk=None)
    if result.crosstalk is not None:
        c = result.crosstalk
        out['crosstalk'] = dict(aggressor=c.aggressor, near_victim=c.near_victim,
            far_victim=c.far_victim, next_ratio=_array(c.next_ratio), fext_ratio=_array(c.fext_ratio))
    return out


def execute_saved(text, *, max_input_bytes=262144, max_evaluations=128, diagnostics=()):
    """Run a strict saved document and return a finite sipi.execution/1 dict.

    Study sample counts and saved goal budgets must not exceed max_evaluations
    (2..10000); goals keep their original budget, never silently clamp it.
    diagnostics may contain 'characteristic' and/or 'modes', only for top-level
    transmission/volume lines. A failed diagnostic preserves the base output.
    Failed goals return status='failed' with completed history; malformed input
    and other solver failures raise their original exceptions. Study failures
    remain rows with status='incomplete', without a partial summary.
    """
    budget = _integer('max_evaluations', max_evaluations, 2, 10000)
    if (not isinstance(diagnostics, (tuple, list))
            or any(not isinstance(x, str) or x not in ('characteristic', 'modes') for x in diagnostics)
            or len(set(diagnostics)) != len(diagnostics)):
        raise ValueError('diagnostics must contain unique characteristic/modes selections')
    doc = _load(text, max_input_bytes)
    data = doc.to_dict()
    if diagnostics and not isinstance(doc, (TransmissionLineDocument, VolumeLineDocument)):
        raise ValueError('diagnostics require a top-level transmission-line or volume-line')
    out = dict(schema='sipi.execution/1', input=data, status='complete', result=None, error=None)
    if isinstance(doc, (ImpedanceDesignDocument, ApertureDesignDocument)):
        if data['max_evaluations'] > budget:
            raise ValueError('saved goal budget exceeds max_evaluations before any solve')
        value, unit = ('impedance', 'ohm') if isinstance(doc, ImpedanceDesignDocument) else ('capacitance', 'F/m')
        try:
            out['result'] = _design(doc.solve(), value, unit)
        except (GoalSeekError, CapacitanceGoalError) as exc:
            out.update(status='failed', error=dict(type=type(exc).__name__, message=str(exc),
                unit=unit, history=_history(exc.history, value), parameter=getattr(exc, 'parameter', None)))
    elif isinstance(doc, (ImpedanceStudyDocument, ApertureStudyDocument)):
        result = doc.analyze(max_evaluations=budget)
        value, unit = ('impedance', 'ohm') if isinstance(doc, ImpedanceStudyDocument) else ('capacitance', 'F/m')
        out['result'] = _study(result, value, unit)
        if result.failed:
            out['status'] = 'incomplete'
    else:
        result = doc.analyze()
        if isinstance(doc, CrossSectionDocument):
            out['result'] = dict(names=list(result.names), C_f_per_m=_array(result.C),
                C0_f_per_m=_array(result.C0), C_loss_f_per_m=_array(result.C_loss),
                L_h_per_m=_array(result.L))
            if len(result.names) == 1:
                out['result'].update(z0_ohm=result.z0, eps_eff=result.eps_eff, delay_s_per_m=result.delay)
        elif isinstance(doc, (ApertureDocument, ApertureSectionDocument)):
            names = ['signal'] if isinstance(doc, ApertureDocument) else list(doc.section.names)
            out['result'] = dict(names=names, capacitance_f_per_m=_array(result))
        elif isinstance(doc, Capacitance3DDocument):
            out['result'] = dict(model='bounded-static-3d', names=list(result.names),
                capacitance_f=_array(result.C), energy_capacitance_f=_array(result.energy_C),
                ground_charge_c_at_unit_voltage=_array(result.ground_charge),
                mesh=dict(nodes=len(result.potentials), tetrahedra=result.num_tets),
                consistency={key: getattr(result, key) for key in
                    ('free_residual_relative', 'charge_balance_relative',
                     'energy_charge_relative', 'symmetry_relative')})
        elif isinstance(doc, (TransmissionLineDocument, VolumeLineDocument)):
            out['result'] = dict(names=list(result.names), frequency_hz=_array(result.frequency),
                R_ohm_per_m=_array(result.R), L_h_per_m=_array(result.L),
                G_s_per_m=_array(result.G), C_f_per_m=_array(result.C),
                network=_network(result.network), diagnostics=_diagnostics(result, diagnostics))
        elif isinstance(doc, CircuitDocument):
            out['result'] = _circuit(result)
        elif isinstance(doc, LumpedNetworkDocument):
            out['result'] = dict(network=_network(result))
        elif isinstance(doc, NetworkAssemblyDocument):
            out['result'] = dict(network=_network(result.network),
                                source_networks=[_network(n) for n in result.source_networks])
        elif isinstance(doc, NetworkTransformDocument):
            out['result'] = dict(network=_network(result.network), source_network=_network(result.source_network),
                                fixture_networks=[_network(n) for n in result.fixture_networks])
        else:  # Every registry addition needs an explicit output contract.
            raise TypeError('saved schema has no execution serializer')
    # Also check scalar metadata/history, and detach every mutable value.
    return json.loads(json.dumps(out, ensure_ascii=False, allow_nan=False))
