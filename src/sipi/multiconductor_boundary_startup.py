# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Three/four-signal constant RLGC circuits with explicit ideal/open/short ends."""
from dataclasses import dataclass
import json
import numpy as np
from scipy.signal import lsim
from .network import _real, _scalar
from .sampling import _integer
from .multiconductor_startup import _multiconductor_input
from .psd_multiconductor_debye_startup import _psd_multiconductor_matrix
from .coupled_startup import _quadratic
from .rlgc_startup import RLGCLadderResponse

__all__ = ['MixedBoundaryMulticonductorRLGCLadderResponse', 'multiconductor_boundary_ladder_response']


@dataclass(frozen=True)
class MixedBoundaryMulticonductorRLGCLadderResponse:
    """Copied/read-only states, with near signals followed by far signals.

    Both terminal currents enter the line; segment currents point toward far.
    This independent class does not implicitly enter two/four-port wave APIs.
    """
    input_json: str
    time: np.ndarray
    source_voltages: np.ndarray
    node_voltage: np.ndarray
    segment_current: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    energy: np.ndarray
    energy_rate: np.ndarray
    series_loss: np.ndarray
    shunt_loss: np.ndarray
    line_power: np.ndarray
    source_power: np.ndarray
    source_resistor_loss: np.ndarray
    load_resistor_loss: np.ndarray
    power_balance_relative_error: float

    total_power_balance_relative_error: float

    __post_init__ = RLGCLadderResponse.__post_init__
    inputs = RLGCLadderResponse.inputs

    @property
    def port_names(self):
        return tuple(f'{end}_{j}' for end in ('near', 'far')
                     for j in range(self.inputs['signals']))

    def to_dict(self, *, include_states=False):
        out = RLGCLadderResponse.to_dict(self, include_states=include_states)
        out['scope'] = 'finite-passive-multiconductor-mixed-boundary-rlgc-startup'
        out['total_power_balance_relative_error'] = self.total_power_balance_relative_error
        return out


def _multiconductor_boundary_input(time, source_voltages, *, signals, R, L, G, C,
        length, cells, source_resistance, load_resistance):
    signals = _integer(signals, 3, 4)
    r = _psd_multiconductor_matrix('R', R, signals)
    g = _psd_multiconductor_matrix('G', G, signals)
    zero = np.zeros((signals, signals)); ones = np.ones(signals)
    data = _multiconductor_input(time, source_voltages, signals=signals,
        R=zero, L=L, G=zero, C=C, length=length, cells=cells,
        source_resistance=ones, load_resistance=ones)
    time, drive, signals, _, l, _, c, length, n, _, _ = data
    rs = _real('source_resistance', source_resistance)
    raw_load = np.asarray(load_resistance, dtype=object)
    if rs.shape != (signals,) or np.any(rs < 0) or raw_load.shape != (signals,):
        raise ValueError('source/load resistances need signals entries; sources finite nonnegative')
    rl = tuple(None if x is None else _scalar('load_resistance', x, zero=True) for x in raw_load)
    return time, drive, signals, r, l, g, c, length, n, rs, rl


def multiconductor_boundary_ladder_response(time, source_voltages, *, signals,
        R, L, G, C, length, cells, source_resistance, load_resistance):
    """Propagate a separate constant three/four-signal circuit with mixed ends.

    Exactly symmetric real PSD R/G and SPD L/C (eigenvalue ratio>1e-12),
    signals3/4,cells1..128,uniform2..10000time rows starting0 andzero-first
    PWL voltages(times,signals). Rs>=0 finite with0ideal voltage;load entries
    None=open,0=short,positivefinite=resistive. Both vectors are explicit.
    No negative eigenvalue clipping, symmetry repair or hidden rank threshold.

    Full mutual half-end C/G remains in the mass matrix. Fixed-voltage
    elimination and a free-state transform remove derivative forcing before
    lsim; right source slopes (final0) reconstruct ideal/short terminal current.
    Near N then far N currents all enter the line. Line and source balances
    retain relative1e-10 checks. This finite circuit needs input-specific
    spatial/source/time qualification; no external reactance, dispersion,
    current source, field extraction, saved or wave admission is inferred.
    """
    time, drive, signals, r, l, g, c, length, n, rs, rl = _multiconductor_boundary_input(
        time, source_voltages, signals=signals, R=R, L=L, G=G, C=C,
        length=length, cells=cells, source_resistance=source_resistance,
        load_resistance=load_resistance)
    dx = length/n; weights = np.ones(n+1); weights[[0,-1]] = .5
    nv = signals*(n+1); size = signals*(2*n+1)
    with np.errstate(over='ignore',invalid='ignore',divide='ignore',under='ignore'):
        cap = c*dx*.5; ind = l*dx
        slope = np.vstack((np.diff(drive,axis=0)/np.diff(time)[:,None],np.zeros(signals)))
    if (dx <= 0 or not np.all(np.isfinite(np.r_[cap.ravel(),ind.ravel(),slope.ravel()]))
            or np.linalg.eigvalsh(cap)[0] <= 0 or np.linalg.eigvalsh(ind)[0] <= 0):
        raise ValueError('cell matrices or source slopes exceed finite scales')
    mass = np.zeros((size,size)); stiffness = np.zeros_like(mass); b = np.zeros((size,signals))
    fixed = []; fixed_drive = []
    with np.errstate(over='ignore',invalid='ignore',divide='ignore',under='ignore'):
        for node in range(n+1):
            s = slice(signals*node,signals*(node+1))
            mass[s,s] = c*dx*weights[node]; stiffness[s,s] = -g*dx*weights[node]
            if node>0:stiffness[s,nv+signals*(node-1):nv+signals*node] = np.eye(signals)
            if node<n:stiffness[s,nv+signals*node:nv+signals*(node+1)] = -np.eye(signals)
        for j in range(signals):
            if rs[j]==0:
                fixed.append(j); fixed_drive.append(np.eye(signals)[j])
            else:
                stiffness[j,j] -= 1/rs[j]; b[j,j] = 1/rs[j]
            idx = signals*n+j
            if rl[j]==0:
                fixed.append(idx); fixed_drive.append(np.zeros(signals))
            elif rl[j] is not None:stiffness[idx,idx] -= 1/rl[j]
        for node in range(n):
            s = slice(nv+signals*node,nv+signals*(node+1))
            mass[s,s] = l*dx; stiffness[s,s] = -r*dx
            stiffness[s,signals*node:signals*(node+1)] = np.eye(signals)
            stiffness[s,signals*(node+1):signals*(node+2)] = -np.eye(signals)
    if not all(np.all(np.isfinite(x)) for x in (mass,stiffness,b)):
        raise ValueError('circuit coefficients exceed finite scales')
    free = np.array([i for i in range(size) if i not in fixed]); fixed = np.array(fixed,dtype=int)
    mapping = np.array(fixed_drive,dtype=float).reshape(len(fixed),signals)
    mf = mass[np.ix_(free,free)]
    try:
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            a = np.linalg.solve(mf,stiffness[np.ix_(free,free)])
            transform = np.linalg.solve(mf,mass[np.ix_(free,fixed)])
            beta = (np.linalg.solve(mf,b[free])
                +(np.linalg.solve(mf,stiffness[np.ix_(free,fixed)])-a@transform)@mapping)
    except np.linalg.LinAlgError as exc:
        raise ValueError('free circuit mass matrix is numerically singular') from exc
    if not all(np.all(np.isfinite(x)) for x in (a,transform,beta)):
        raise ValueError('reduced circuit coefficients exceed finite scales')
    _,_,z = lsim((a,beta,np.zeros((1,len(free))),np.zeros((1,signals))),drive,time,interp=True)
    z = np.asarray(z)
    if z.shape != (len(time),len(free)) or not np.all(np.isfinite(z)):
        raise ValueError('state propagation returned invalid shape or nonfinite values')
    with np.errstate(over='ignore',invalid='ignore',divide='ignore',under='ignore'):
        xp = drive@mapping.T; dp = slope@mapping.T
        x = np.zeros((len(time),size)); rhs = np.zeros_like(x)
        x[:,free] = z-xp@transform.T; x[:,fixed] = xp
        rhs[:,free] = z@a.T+drive@beta.T-dp@transform.T; rhs[:,fixed] = dp
        v = x[:,:nv].reshape(len(time),n+1,signals); i = x[:,nv:].reshape(len(time),n,signals)
        dv = rhs[:,:nv].reshape(v.shape); di = rhs[:,nv:].reshape(i.shape)
        voltage = v[:,[0,n],:].reshape(len(time),2*signals); current = np.zeros_like(voltage)
        near = (dv[:,0]@c.T+v[:,0]@g.T)*dx*.5+i[:,0]
        far = (dv[:,-1]@c.T+v[:,-1]@g.T)*dx*.5-i[:,-1]
        for j in range(signals):
            current[:,j] = near[:,j] if rs[j]==0 else (drive[:,j]-v[:,0,j])/rs[j]
            current[:,signals+j] = far[:,j] if rl[j]==0 else 0. if rl[j] is None else -v[:,-1,j]/rl[j]
        energy = .5*dx*(np.sum(_quadratic(v,c)*weights,axis=1)+np.sum(_quadratic(i,l),axis=1))
        rate = dx*(np.sum(np.einsum('tni,ij,tnj->tn',v,c,dv)*weights,axis=1)
            +np.sum(np.einsum('tni,ij,tnj->tn',i,l,di),axis=1))
        series = dx*np.sum(_quadratic(i,r),axis=1); shunt = dx*np.sum(_quadratic(v,g)*weights,axis=1)
        line_power = np.sum(voltage*current,axis=1)
        source_power = np.sum(drive*current[:,:signals],axis=1)
        source_loss = np.sum(rs*current[:,:signals]**2,axis=1); load_loss = np.zeros(len(time))
        for j in range(signals):
            if rl[j] is not None:load_loss += rl[j]*current[:,signals+j]**2
        residual = rate-line_power+series+shunt
        total_loss = series+shunt+source_loss+load_loss; total_residual = rate-source_power+total_loss
    if (not np.all(np.isfinite(np.r_[energy,rate,line_power,source_power,series,shunt,source_loss,load_loss,residual,total_loss,total_residual]))
            or any(np.any(x<0) for x in (energy,series,shunt,source_loss,load_loss))):
        raise ValueError('passive energy diagnostics exceed finite scales')
    scale = max(np.max(abs(rate)),np.max(abs(line_power)),np.max(abs(series+shunt)))
    error = float(np.max(abs(residual))/scale) if scale>0 else 0.
    total_scale = max(np.max(abs(rate)),np.max(abs(source_power)),np.max(abs(total_loss)))
    total_error = float(np.max(abs(total_residual))/total_scale) if total_scale>0 else 0.
    if not np.isfinite(error) or error>1e-10 or not np.isfinite(total_error) or total_error>1e-10:
        raise ValueError('finite circuit line/source power balance exceeds relative 1e-10')
    data = dict(time_s=time.tolist(),source_voltages_v=drive.tolist(),signals=signals,
        R_ohm_per_m=r.tolist(),L_h_per_m=l.tolist(),G_s_per_m=g.tolist(),C_f_per_m=c.tolist(),
        length_m=length,cells=n,source_resistance_ohm=rs.tolist(),load_resistance_ohm=list(rl))
    return MixedBoundaryMulticonductorRLGCLadderResponse(json.dumps(data,sort_keys=True,allow_nan=False),
        time,drive,v,i,voltage,current,energy,rate,series,shunt,line_power,source_power,
        source_loss,load_loss,error,total_error)
