# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Initially unenergized, uniform lossless scalar line with resistive ends."""
from dataclasses import dataclass

import numpy as np

from .network import _real, _scalar
from .sampling import _integer

__all__ = ['LosslessLineResponse', 'lossless_line_response']


def _times(name, value):
    out = _real(name, value)
    if out.ndim != 1 or not len(out) or np.any(out < 0) or np.any(np.diff(out) <= 0):
        raise ValueError(name+' must be nonempty strictly increasing times >= 0 seconds')
    return out


def _boundary(resistance, impedance):
    scale = max(resistance, impedance)
    r, z = resistance/scale, impedance/scale
    total = r+z
    return (r-z)/total, z/total, 2*(r/total), (1/total)/scale


def _drive(time, knots, values, shift):
    """Explicit shifted PWL knots, with zero prehistory and final-value hold."""
    out = np.zeros_like(time)
    if float(knots[0])+shift > time[-1]:
        return out
    with np.errstate(over='ignore', invalid='ignore'):
        shifted = knots+shift
    if not np.all(np.isfinite(shifted)) or np.any(np.diff(shifted) <= 0):
        raise ValueError('shifted source knots exceed finite time resolution')
    active = time >= shifted[0]
    query = time[active]
    index = np.searchsorted(shifted, query, side='right')-1
    result = values[index].copy()
    middle = index < len(shifted)-1
    left = index[middle]
    weight = (query[middle]-shifted[left])/(shifted[left+1]-shifted[left])
    # Convex blending avoids overflow in a subtraction of opposite voltages.
    result[middle] = (1-weight)*values[left]+weight*values[left+1]
    out[active] = result
    return out


@dataclass(frozen=True)
class LosslessLineResponse:
    """Copied read-only source/load samples; both port currents enter the line.

    Forward/backward voltages travel in the +z/-z direction respectively at
    each port. Stable boundary equations evaluate currents independently of
    cancellation in those waves. ``terms`` counts forward delay-series terms,
    not reflections at both ports or time samples.
    """
    time: np.ndarray
    source_times: np.ndarray
    source_voltages: np.ndarray
    z0_ohm: float
    delay_s: float
    source_resistance: float
    load_resistance: float | None
    max_terms: int
    terms: int
    drive_voltage: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    forward_voltage: np.ndarray
    backward_voltage: np.ndarray

    def __post_init__(self):
        for name in ('time', 'source_times', 'source_voltages', 'drive_voltage',
                     'voltage', 'current', 'forward_voltage', 'backward_voltage'):
            a = np.array(getattr(self, name), dtype=float, copy=True)
            if not np.all(np.isfinite(a)):
                raise ValueError('startup output must remain finite')
            a.setflags(write=False)
            object.__setattr__(self, name, a)

    @property
    def port_names(self):
        return ('source', 'load')

    def to_dict(self):
        return dict(scope='initially-unenergized-lossless-scalar-line',
            time_s=self.time.tolist(), port_names=list(self.port_names),
            input=dict(source_times_s=self.source_times.tolist(),
                source_voltages_v=self.source_voltages.tolist(), z0_ohm=self.z0_ohm,
                delay_s=self.delay_s, source_resistance_ohm=self.source_resistance,
                load_resistance_ohm=self.load_resistance, max_terms=self.max_terms),
            terms=self.terms, drive_voltage_v=self.drive_voltage.tolist(),
            voltage_v=self.voltage.tolist(), current_into_line_a=self.current.tolist(),
            forward_voltage_v=self.forward_voltage.tolist(), backward_voltage_v=self.backward_voltage.tolist())


def _startup_input(time, *, source_times, source_voltages, z0_ohm, delay_s,
                   source_resistance, load_resistance, max_terms=10000):
    """Shared unmeshed/uninterpolated validation and horizon term preflight."""
    time = _times('time', time)
    knots = _times('source_times', source_times)
    values = _real('source_voltages', source_voltages)
    if values.shape != knots.shape:
        raise ValueError('source_voltages needs one real value per source time')
    z = _scalar('z0_ohm', z0_ohm)
    delay = _scalar('delay_s', delay_s)
    rs = _scalar('source_resistance', source_resistance, zero=True)
    rl = None if load_resistance is None else _scalar('load_resistance', load_resistance, zero=True)
    budget = _integer(max_terms, 1, 10000)
    gs, gain, hs, invs = _boundary(rs, z)
    gl, _, hl, invl = (1., 0., 2., 0.) if rl is None else _boundary(rl, z)
    if not np.all(np.isfinite([gs, gain, hs, invs, gl, hl, invl])):
        raise ValueError('resistance scales exceed finite current resolution')
    reflection = gs*gl
    terms = 0
    if time[-1] >= knots[0]:
        if reflection == 0:
            terms = 1
        else:
            for n in range(budget+1):
                shift = (2*n)*delay
                if float(knots[0])+shift > time[-1]:
                    break
                if n == budget:
                    raise ValueError('required delay terms exceed max_terms before waveform evaluation')
                terms += 1
    data = dict(time=time, source_times=knots, source_voltages=values,
        z0_ohm=z, delay_s=delay, source_resistance=rs, load_resistance=rl,
        max_terms=budget)
    return data, (gain, hs, invs, gl, hl, invl, reflection), terms


def lossless_line_response(time, *, source_times, source_voltages, z0_ohm, delay_s,
                           source_resistance, load_resistance, max_terms=10000):
    """Exact finite delay sum for an initially unenergized scalar lossless line.

    All times are seconds, voltages volts and resistances ohms. Z0 and one-way
    delay are positive. The source is finite nonnegative Thevenin resistance;
    the load is finite nonnegative resistance, or None for an explicit open.
    Source knots are real PWL samples: zero before the first knot, hold the
    last value afterwards. One knot permits an explicit step. Times must be
    nonnegative and strictly increasing; a single output sample is allowed.

    Sum every potentially active forward round-trip term up to the requested
    horizon, including zero-valued terms, with no geometric-tail truncation.
    The integer max_terms (1..10000) is checked before waveform evaluation.
    An exactly zero round-trip coefficient needs at most one forward term,
    but still retains the returning load wave. The budget is not a runtime
    or memory guarantee. Unresolved shifted knots/nonfinite results raise.

    Both currents point into the line. This API has explicit zero initial
    energy, no periodic extension, and no reactive load, loss, dispersion,
    multiconductor coupling or conversion from arbitrary frequency samples.
    """
    data, coefficients, terms = _startup_input(time, source_times=source_times,
        source_voltages=source_voltages, z0_ohm=z0_ohm, delay_s=delay_s,
        source_resistance=source_resistance, load_resistance=load_resistance,
        max_terms=max_terms)
    time, knots, values = (data[k] for k in ('time', 'source_times', 'source_voltages'))
    z, delay, rs, rl, budget = (data[k] for k in
        ('z0_ohm', 'delay_s', 'source_resistance', 'load_resistance', 'max_terms'))
    gain, hs, invs, gl, hl, invl, reflection = coefficients
    drive = _drive(time, knots, values, 0.)
    outgoing = np.zeros_like(time); returning = np.zeros_like(time); incident = np.zeros_like(time)
    weight = gain
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        for n in range(terms):
            outgoing += weight*_drive(time, knots, values, (2*n)*delay)
            returning += gl*weight*_drive(time, knots, values, (2*n+2)*delay)
            incident += weight*_drive(time, knots, values, (2*n+1)*delay)
            weight *= reflection
        # Stable port equations retain tiny finite-load current when gl rounds
        # to one, and avoid subtracting almost equal forward/backward waves.
        voltage = np.column_stack((gain*drive+hs*returning, hl*incident))
        current = np.column_stack((invs*(drive-2*returning), -2*(invl*incident)))
        forward = np.column_stack((outgoing, incident))
        backward = np.column_stack((returning, gl*incident))
    return LosslessLineResponse(time, knots, values, z, delay, rs, rl, budget, terms,
                                drive, voltage, current, forward, backward)
