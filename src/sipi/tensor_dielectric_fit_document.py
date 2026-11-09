# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict saved inputs for fixed-pole, fixed-orientation tensor fitting."""
import json
from .tensor_dielectric_fit import _tensor_fit_inputs,fit_tensor_debye
from .circuit_document import _json_copy
from .document import _keys,_unique_object

__all__ = ['TensorDebyeFitDocument']


class TensorDebyeFitDocument:
    """Save fitting inputs without SVD, optimization or field work.

    Parsing retains original reciprocal tensor samples and validates their
    bounded 2x2 positive-real/PSD-loss requirements. Numerical identifiability,
    condition and optimality are checked only during analyze. Completion and
    sampled-error acceptance remain separate; above-limit candidates retain
    every input and residual rather than becoming execution failures.
    """
    def __init__(self,frequency,*,eps_real,eps_loss,relaxation_hz,angles_rad,
                 eps_inf_angle_rad=0.0,max_error,weights=None):
        f,real,loss,basis,w,limit=_tensor_fit_inputs(frequency,eps_real,eps_loss,
            relaxation_hz,angles_rad,eps_inf_angle_rad,max_error,weights)
        self._data=dict(schema='sipi.tensor-dielectric-fit/1',frequency_hz=f.tolist(),
            eps_real=real.tolist(),eps_loss=loss.tolist(),relaxation_hz=list(basis.relaxation_hz),
            angles_rad=list(basis.angles_rad),eps_inf_angle_rad=basis.eps_inf_angle_rad,
            weights=w.tolist(),max_error=limit)

    @classmethod
    def from_dict(cls,data):
        data=_json_copy(data)
        _keys(data,('schema','frequency_hz','eps_real','eps_loss','relaxation_hz',
                   'angles_rad','eps_inf_angle_rad','weights','max_error'),where='tensor dielectric fit')
        if data['schema']!='sipi.tensor-dielectric-fit/1':
            raise ValueError('unsupported tensor dielectric-fit schema')
        if data['weights'] is None:
            raise ValueError('saved weights must explicitly match every frequency')
        return cls(data['frequency_hz'],eps_real=data['eps_real'],eps_loss=data['eps_loss'],
            relaxation_hz=data['relaxation_hz'],angles_rad=data['angles_rad'],
            eps_inf_angle_rad=data['eps_inf_angle_rad'],weights=data['weights'],max_error=data['max_error'])

    @classmethod
    def loads(cls,text):
        def reject(value):raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data=self.to_dict()
        return fit_tensor_debye(data['frequency_hz'],eps_real=data['eps_real'],eps_loss=data['eps_loss'],
            relaxation_hz=data['relaxation_hz'],angles_rad=data['angles_rad'],
            eps_inf_angle_rad=data['eps_inf_angle_rad'],weights=data['weights'],max_error=data['max_error'])
