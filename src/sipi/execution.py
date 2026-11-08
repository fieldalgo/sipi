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
from .band import NetworkBandDocument, BandAssessment
from .length_design import LineLengthDesignDocument, LengthGoalError
from .ports3d_document import TEMPorts3DDocument
from .boundary_conductor import BoundaryConductorLoss
from .face_conductor import FaceConductorLoss
from .yield_assessment import ImpedanceYieldDocument
from .yield_design import YieldDesignDocument
from .dielectric_fit import DebyeFitDocument
from .line_goal_document import LineQuantityDesignDocument
from .line_goal import LineQuantityGoalError
from .line_study import LineQuantityStudyDocument
from .line_yield import LineQuantityYieldDocument
from .periodic_document import PeriodicNetworkDocument
from .periodic_circuit import PeriodicCircuitDocument
from .norton_circuit import NortonCircuitDocument
from .mixed_circuit import MixedCircuitDocument
from .periodic_mixed_circuit import PeriodicMixedCircuitDocument
from .periodic_norton_circuit import PeriodicNortonCircuitDocument
from .conductivity_profile_document import ConductivityProfileDocument
from .pair_design_document import PairImpedanceDesignDocument
from .pair_design import PairImpedanceGoalError
from .sampled_design_document import SampledImpedanceDesignDocument
from .sampled_design import SampledImpedanceGoalError
from .startup_document import LosslessStartupDocument
from .rlgc_startup_document import RLGCLadderDocument
from .coupled_startup_document import CoupledRLGCLadderDocument
from .coupled_boundary_startup_document import MixedBoundaryRLGCLadderDocument
from .coupled_capacitive_startup_document import CapacitiveRLGCLadderDocument

from .coupled_reactive_startup_document import ReactiveRLGCLadderDocument

from .startup_waves_document import StartupPortWavesDocument

from .norton_startup_document import NortonReactiveRLGCLadderDocument
from .mixed_startup_document import MixedSourceRLGCLadderDocument
from .debye_startup_document import DebyeRLGCLadderDocument

__all__ = ['saved_schemas', 'normalize_saved', 'execute_saved']

_REGISTRY = {
    **{f'sipi.cross-section/{v}': CrossSectionDocument for v in (1, 2, 3)},
    **{f'sipi.impedance-study/{v}': ImpedanceStudyDocument for v in (1, 2, 3, 4)},
    **{f'sipi.impedance-design/{v}': ImpedanceDesignDocument for v in (1, 2, 3)},
    'sipi.circular-aperture/1': ApertureDocument,
    'sipi.aperture-section/1': ApertureSectionDocument,
    'sipi.aperture-study/1': ApertureStudyDocument,
    'sipi.aperture-design/1': ApertureDesignDocument,
    **{f'sipi.transmission-line/{v}': TransmissionLineDocument for v in (1, 2, 3, 4, 5, 6)},
    'sipi.volume-line/1': VolumeLineDocument,
    'sipi.lumped-network/1': LumpedNetworkDocument,
    'sipi.network-assembly/1': NetworkAssemblyDocument,
    **{f'sipi.network-transforms/{v}': NetworkTransformDocument for v in (1, 2)},
    'sipi.circuit/1': CircuitDocument,
    'sipi.capacitance-3d/1': Capacitance3DDocument,
    'sipi.network-band/1': NetworkBandDocument,
    'sipi.line-length-design/1': LineLengthDesignDocument,
    'sipi.line-length-design/2': LineLengthDesignDocument,
    'sipi.tem-ports-3d/1': TEMPorts3DDocument,
    'sipi.impedance-yield/1': ImpedanceYieldDocument,
    'sipi.yield-design/1': YieldDesignDocument,
    'sipi.yield-design/2': YieldDesignDocument,
    'sipi.dielectric-fit/1': DebyeFitDocument,
    'sipi.line-quantity-design/1': LineQuantityDesignDocument,
    'sipi.line-quantity-design/2': LineQuantityDesignDocument,
    'sipi.line-quantity-study/1': LineQuantityStudyDocument,
    'sipi.line-quantity-study/2': LineQuantityStudyDocument,
    'sipi.line-quantity-yield/1': LineQuantityYieldDocument,
    'sipi.periodic-network/1': PeriodicNetworkDocument,
    'sipi.periodic-circuit/1': PeriodicCircuitDocument,
    'sipi.norton-circuit/1': NortonCircuitDocument,
    'sipi.mixed-circuit/1': MixedCircuitDocument,
    'sipi.periodic-mixed-circuit/1': PeriodicMixedCircuitDocument,
    'sipi.periodic-norton-circuit/1': PeriodicNortonCircuitDocument,
    'sipi.conductivity-profile/1': ConductivityProfileDocument,
    'sipi.pair-impedance-design/1': PairImpedanceDesignDocument,
    'sipi.pair-impedance-design/2': PairImpedanceDesignDocument,
    'sipi.sampled-impedance-design/1': SampledImpedanceDesignDocument,
    'sipi.lossless-startup/1': LosslessStartupDocument,
    'sipi.rlgc-startup/1': RLGCLadderDocument,
    'sipi.coupled-rlgc-startup/1': CoupledRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/2': MixedBoundaryRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/3': CapacitiveRLGCLadderDocument,
    'sipi.coupled-rlgc-startup/4': ReactiveRLGCLadderDocument,
    **{f'sipi.startup-port-waves/{v}': StartupPortWavesDocument for v in (1, 2, 3, 4)},
    'sipi.norton-rlgc-startup/1': NortonReactiveRLGCLadderDocument,
    'sipi.mixed-rlgc-startup/1': MixedSourceRLGCLadderDocument,
    'sipi.debye-rlgc-startup/1': DebyeRLGCLadderDocument,
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
            value=getattr(row, value), error_type=row.error_type, error=row.error,
            **({} if getattr(row, 'material_evaluation_json', None) is None else
               {'material_evaluation': json.loads(row.material_evaluation_json)}))
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


def _norton_circuit(result):
    r = result.response
    return dict(coverage='sampled-frequency-boundary',
        power_convention='dc-weight-one-positive-peak',
        source_network=_network(result.source_network), network=_network(result.network),
        response=dict(source_current_a=_array(r.source_currents),
            termination_admittance_s=_array(r.termination_admittances),
            incident_sqrt_w=_array(r.a), reflected_sqrt_w=_array(r.b),
            voltage_v=_array(r.voltage), current_a=_array(r.current),
            condition_number=_array(r.condition_number), kcl_residual=_array(r.kcl_residual),
            wave_residual=_array(r.wave_residual)),
        frequency_power_w={name:_array(getattr(r, attribute)) for name,attribute in
            [('network','network_power'), ('terminations','termination_power'), ('sources','source_power')]})


def _mixed_response(r):
    return dict(kinds=list(r.kinds), source_voltage_v=_array(r.source_voltages),
        series_impedance_ohms=_array(r.series_impedances),
        source_current_a=_array(r.source_currents), shunt_admittance_s=_array(r.shunt_admittances),
        incident_sqrt_w=_array(r.a), reflected_sqrt_w=_array(r.b),
        voltage_v=_array(r.voltage), current_a=_array(r.current),
        condition_number=_array(r.condition_number), boundary_residual=_array(r.boundary_residual),
        wave_residual=_array(r.wave_residual))


def _mixed_circuit(result):
    r = result.response
    return dict(coverage='sampled-frequency-boundary',
        power_convention='dc-weight-one-positive-peak',
        source_network=_network(result.source_network), network=_network(result.network),
        response=_mixed_response(r),
        frequency_power_w={name:_array(getattr(r, attribute)) for name,attribute in
            [('network','network_power'), ('terminations','termination_power'), ('sources','source_power')]})


def _periodic_time(r):
    return dict(time_s=_array(r.time), period_s=r.period, dt_s=r.dt,
        incident_sqrt_w=_array(r.incident), reflected_sqrt_w=_array(r.reflected),
        voltage_v=_array(r.voltage), current_a=_array(r.current))


def _periodic(result):
    h = result.impulse
    return dict(coverage='sampled-periodic-steady-state', network=_network(result.network),
        source_network=_network(result.source_network),
        response=_periodic_time(result.response),
        impulse=None if h is None else dict(lag_s=_array(h.lag), weights=_array(h.weights)))


def _periodic_circuit(result):
    solution = result.solution
    frequency = solution.frequency_solution
    powers = {key:_array(getattr(frequency, attr)) for key,attr in
              [('network','network_power'), ('terminations','termination_power'), ('sources','source_power')]}
    with np.errstate(over='ignore', invalid='ignore'):
        mean = {key:_array(np.sum(value)) for key,value in powers.items()}
    return dict(coverage='sampled-periodic-steady-state', network=_network(result.network),
        source_network=_network(result.source_network), response=_periodic_time(solution.response),
        source_voltage_v=_array(solution.source_voltages),
        termination_voltage_v=_array(solution.termination_voltages),
        harmonics=dict(convention='dc-mean-positive-peak',
            source_voltage_v=_array(frequency.source_voltages), termination_ohms=_array(frequency.terminations),
            incident_sqrt_w=_array(frequency.a), reflected_sqrt_w=_array(frequency.b),
            voltage_v=_array(frequency.voltage), current_a=_array(frequency.current),
            condition_number=_array(frequency.condition_number),
            kvl_residual=_array(frequency.kvl_residual), wave_residual=_array(frequency.wave_residual),
            frequency_power_w=powers), mean_power_w=mean)


def _periodic_norton_circuit(result):
    solution = result.solution
    frequency = solution.frequency_solution
    powers = {key:_array(getattr(frequency, attr)) for key,attr in
              [('network','network_power'), ('terminations','termination_power'), ('sources','source_power')]}
    with np.errstate(over='ignore', invalid='ignore'):
        mean = {key:_array(np.sum(value)) for key,value in powers.items()}
    return dict(coverage='sampled-periodic-steady-state', network=_network(result.network),
        source_network=_network(result.source_network), response=_periodic_time(solution.response),
        source_current_a=_array(solution.source_currents),
        termination_current_a=_array(solution.termination_currents),
        harmonics=dict(convention='dc-mean-positive-peak',
            source_current_a=_array(frequency.source_currents), termination_admittance_s=_array(frequency.termination_admittances),
            incident_sqrt_w=_array(frequency.a), reflected_sqrt_w=_array(frequency.b),
            voltage_v=_array(frequency.voltage), current_a=_array(frequency.current),
            condition_number=_array(frequency.condition_number),
            kcl_residual=_array(frequency.kcl_residual), wave_residual=_array(frequency.wave_residual),
            frequency_power_w=powers), mean_power_w=mean)


def _periodic_mixed_circuit(result):
    solution = result.solution
    frequency = solution.frequency_solution
    powers = {key:_array(getattr(frequency, attr)) for key,attr in
              [('network','network_power'), ('terminations','termination_power'), ('sources','source_power')]}
    with np.errstate(over='ignore', invalid='ignore'):
        mean = {key:_array(np.sum(value)) for key,value in powers.items()}
    harmonics = _mixed_response(frequency)
    harmonics.update(convention='dc-mean-positive-peak', frequency_power_w=powers)
    return dict(coverage='sampled-periodic-steady-state', network=_network(result.network),
        source_network=_network(result.source_network), response=_periodic_time(solution.response),
        source_voltage_v=_array(solution.source_voltages), source_current_a=_array(solution.source_currents),
        termination_voltage_v=_array(solution.termination_voltages),
        termination_current_a=_array(solution.termination_currents),
        harmonics=harmonics, mean_power_w=mean)


def execute_saved(text, *, max_input_bytes=262144, max_evaluations=128, diagnostics=()):
    """Run a strict saved document and return a finite sipi.execution/1 dict.

    Study sample counts and saved goal budgets must not exceed max_evaluations
    (2..10000); goals keep their original budget, never silently clamp it.
    Sampled impedance goals count parameter batches, not internal frequency solves;
    their separate frequency count is capped at 64 by the saved input contract.
    Bounded TEM-port 3D counts one evaluation per frequency before field work.
    Conductivity profiles count frequencies before constitutive integration.
    Lossless startup counts required forward delay terms before waveforms,
    separately from its saved hard cap and output sample count.
    Scalar and two-signal finite RLGC startup count time samples before state propagation, retaining
    the separate explicit cell count and its hard bound.
    Dielectric fitting counts input frequencies before matrix/optimizer work;
    completed execution keeps the fit's accepted flag as a separate decision.
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
    if isinstance(doc, TEMPorts3DDocument) and len(data['frequency_hz']) > budget:
        raise ValueError('saved 3D frequency count exceeds max_evaluations before any field solve')
    if diagnostics and not isinstance(doc, (TransmissionLineDocument, VolumeLineDocument)):
        raise ValueError('diagnostics require a top-level transmission-line or volume-line')
    out = dict(schema='sipi.execution/1', input=data, status='complete', result=None, error=None)
    if isinstance(doc, (LosslessStartupDocument, RLGCLadderDocument, CoupledRLGCLadderDocument, MixedBoundaryRLGCLadderDocument, CapacitiveRLGCLadderDocument, ReactiveRLGCLadderDocument, StartupPortWavesDocument, NortonReactiveRLGCLadderDocument, MixedSourceRLGCLadderDocument, DebyeRLGCLadderDocument)):
        out['result'] = doc.analyze(max_evaluations=budget).to_dict()
    elif isinstance(doc, ConductivityProfileDocument):
        profile = doc.analyze(max_evaluations=budget)
        out['result'] = dict(frequency_hz=_array(profile.frequency),
            surface_impedance_ohms=_array(profile.impedance),
            skin_depth_m=_array(profile.skin_depth),
            reference_plane_m=profile.reference_plane_m, cutoff_rms=profile.cutoff_rms)
    elif isinstance(doc, DebyeFitDocument):
        if len(data['frequency_hz']) > budget:
            raise ValueError('saved fit frequency count exceeds max_evaluations before fitting')
        out['result'] = doc.analyze().to_dict()
    elif isinstance(doc, PeriodicNetworkDocument):
        out['result'] = _periodic(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, PeriodicCircuitDocument):
        out['result'] = _periodic_circuit(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, PeriodicNortonCircuitDocument):
        out['result'] = _periodic_norton_circuit(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, PeriodicMixedCircuitDocument):
        out['result'] = _periodic_mixed_circuit(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, MixedCircuitDocument):
        out['result'] = _mixed_circuit(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, NortonCircuitDocument):
        out['result'] = _norton_circuit(doc.analyze(max_evaluations=budget))
    elif isinstance(doc, (ImpedanceYieldDocument, YieldDesignDocument, LineQuantityYieldDocument)):
        result = doc.analyze(max_evaluations=budget)
        out['result'] = result.to_dict()
        if result.unresolved:
            out['status'] = 'incomplete'
    elif isinstance(doc, LineQuantityStudyDocument):
        result = doc.analyze(max_evaluations=budget)
        out['result'] = result.to_dict()
        if result.failed:
            out['status'] = 'incomplete'
    elif isinstance(doc, SampledImpedanceDesignDocument):
        if data['max_evaluations'] > budget:
            raise ValueError('saved goal batch budget exceeds max_evaluations before any solve')
        try:
            out['result'] = doc.solve().to_dict()
        except SampledImpedanceGoalError as exc:
            out.update(status='failed', error=dict(type=type(exc).__name__, message=str(exc),
                quantity=exc.quantity, frequencies_hz=list(exc.frequencies), unit='ohm',
                attempts=exc.attempts, stage=exc.stage, failed_parameters=exc.failed_parameters,
                cause_type=exc.cause_type, input=None if exc.input_json is None else json.loads(exc.input_json),
                material_sweep=None if exc.material_sweep_json is None else json.loads(exc.material_sweep_json),
                history=[row.to_dict() for row in exc.history]))
    elif isinstance(doc, PairImpedanceDesignDocument):
        if data['max_evaluations'] > budget:
            raise ValueError('saved goal budget exceeds max_evaluations before any solve')
        try:
            out['result'] = doc.solve().to_dict()
        except PairImpedanceGoalError as exc:
            out.update(status='failed', error=dict(type=type(exc).__name__, message=str(exc),
                quantities=['z_diff', 'z_common'], unit='ohm', attempts=exc.attempts,
                stage=exc.stage, failed_parameters=exc.failed_parameters, cause_type=exc.cause_type,
                input=None if exc.input_json is None else json.loads(exc.input_json),
                material_evaluation=(None if exc.material_evaluation_json is None
                                     else json.loads(exc.material_evaluation_json)),
                history=[row.to_dict() for row in exc.history]))
    elif isinstance(doc, LineQuantityDesignDocument):
        if data['max_evaluations'] > budget:
            raise ValueError('saved goal budget exceeds max_evaluations before any solve')
        try:
            out['result'] = doc.solve().to_dict()
        except LineQuantityGoalError as exc:
            out.update(status='failed', error=dict(type=type(exc).__name__, message=str(exc),
                quantity=exc.quantity, unit=exc.unit, attempts=exc.attempts, stage=exc.stage,
                failed_parameter=exc.failed_parameter, cause_type=exc.cause_type,
                input=None if exc.input_json is None else json.loads(exc.input_json),
                history=[row.to_dict() for row in exc.history]))
    elif isinstance(doc, LineLengthDesignDocument):
        if data['max_evaluations'] > budget:
            raise ValueError('saved goal budget exceeds max_evaluations before any solve')
        try:
            out['result'] = doc.solve().to_dict()
        except LengthGoalError as exc:
            out.update(status='failed', error=dict(type=type(exc).__name__, message=str(exc),
                failed_length_m=exc.failed_length_m, cause_type=exc.cause_type,
                history=[dict(length_m=row.length_m, passed=row.passed, minimum_margin=row.minimum_margin)
                         for row in exc.history]))
            if exc.source_evaluation is not None:
                out['error']['source_evaluation'] = exc.source_evaluation
    elif isinstance(doc, (ImpedanceDesignDocument, ApertureDesignDocument)):
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
        if isinstance(result, BandAssessment):
            out['result'] = result.to_dict()
        elif isinstance(doc, CrossSectionDocument):
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
        elif isinstance(doc, TEMPorts3DDocument):
            out['result'] = dict(model='bounded-homogeneous-3d-local-tem-admittance',
                network=_network(result.network), port_norm=_array(result.port_norm),
                mesh=dict(nodes=len(data['mesh']['nodes']), tetrahedra=result.num_tets, edges=result.num_edges),
                consistency={key: _array(getattr(result, key)) for key in
                    ('linear_residual', 'power_balance', 'reciprocity',
                     'projected_unitarity', 'unprojected_port_power')})
        elif isinstance(doc, (TransmissionLineDocument, VolumeLineDocument)):
            out['result'] = dict(names=list(result.names), frequency_hz=_array(result.frequency),
                R_ohm_per_m=_array(result.R), L_h_per_m=_array(result.L),
                G_s_per_m=_array(result.G), C_f_per_m=_array(result.C),
                network=_network(result.network), diagnostics=_diagnostics(result, diagnostics))
            if isinstance(doc, TransmissionLineDocument) and isinstance(result.conductor, (BoundaryConductorLoss, FaceConductorLoss)):
                loss = result.conductor
                out['result']['conductor_boundaries'] = dict(labels=list(loss.boundary_labels),
                    skin_depth_m=_array(loss.skin_depth), roughness_factor=_array(loss.roughness_factor),
                    surface_impedance_ohms=_array(loss.surface_impedance),
                    resistance_ohm_per_m=_array(loss.resistance_parts))
                if isinstance(loss, FaceConductorLoss):
                    out['result']['conductor_boundaries'].update(
                        surface_current_factors_per_m=_array(loss.factors.parts),
                        current_integrals=_array(loss.factors.current_integrals),
                        whole_boundary_current_integrals=_array(loss.factors.base.current_integrals),
                        current_flux_error=loss.factors.current_error)
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
