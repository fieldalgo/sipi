# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Nonnegative tensor relaxation fits at explicit fixed poles and orientations."""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import nnls
from sipi.dielectric import TensorDebyeDielectric, dielectric_to_dict
from sipi.network import _frequencies, _real, _scalar

__all__ = ['TensorDebyeFit', 'fit_tensor_debye']


@dataclass(frozen=True)
class TensorDebyeFit:
    """Retained sampled tensor fit; acceptance uses a Frobenius error limit.

    Residual is model minus eps_real-j*eps_loss. A completed fit can be above
    its limit. Neither completion nor acceptance establishes measured material
    validity, an unsampled-band bound or inferred pole/orientation uniqueness.
    """
    model: TensorDebyeDielectric
    frequency: np.ndarray
    eps_real: np.ndarray
    eps_loss: np.ndarray
    weights: np.ndarray
    predicted: np.ndarray
    residual: np.ndarray
    condition: float
    scaled_kkt_error: float
    maximum_error: float
    weighted_rms_error: float
    error_limit: float

    def __post_init__(self):
        if type(self.model) is not TensorDebyeDielectric:
            raise ValueError('fitted model must be a TensorDebyeDielectric')
        shape=np.asarray(self.frequency).shape
        if len(shape)!=1 or not 2<=shape[0]<=10000:
            raise ValueError('fit requires 2..10000 frequencies')
        for name in ('frequency','eps_real','eps_loss','weights','predicted','residual'):
            value=np.array(getattr(self,name),dtype=complex if name in ('predicted','residual') else float,copy=True)
            expected=shape if name in ('frequency','weights') else (*shape,2,2)
            if value.shape!=expected or not np.all(np.isfinite(value)):
                raise ValueError(f'{name} must have its finite frequency/tensor shape')
            value.flags.writeable=False;object.__setattr__(self,name,value)
        for name in ('condition','scaled_kkt_error','maximum_error','weighted_rms_error','error_limit'):
            value=_scalar(name,getattr(self,name),zero=name!='error_limit')
            object.__setattr__(self,name,value)

    @property
    def accepted(self):
        return self.maximum_error<=self.error_limit

    def to_dict(self):
        def complex_values(value):return dict(real=value.real.tolist(),imag=value.imag.tolist())
        return dict(scope='fixed-pole-fixed-orientation-sampled-tensor-fit',model=dielectric_to_dict(self.model),
            frequency_hz=self.frequency.tolist(),eps_real=self.eps_real.tolist(),eps_loss=self.eps_loss.tolist(),
            weights=self.weights.tolist(),predicted=complex_values(self.predicted),residual=complex_values(self.residual),
            condition=self.condition,scaled_kkt_error=self.scaled_kkt_error,maximum_error=self.maximum_error,
            weighted_rms_error=self.weighted_rms_error,error_limit=self.error_limit,accepted=self.accepted)


def _tensor_fit_inputs(frequency,eps_real,eps_loss,relaxation_hz,angles_rad,eps_inf_angle_rad,max_error,weights):
    """Admit immutable numeric data without optimization, SVD or fields."""
    f=_frequencies(frequency)
    if not 2<=len(f)<=10000:
        raise ValueError('fit requires 2..10000 frequencies')
    poles=_real('relaxation_hz',relaxation_hz)
    if (poles.ndim!=1 or not 1<=len(poles)<=16 or np.any(poles<=0)
            or np.any(np.diff(poles)<=0)):
        raise ValueError('fit requires 1..16 distinct increasing positive poles')
    basis_model=TensorDebyeDielectric([1,1],np.zeros((len(poles),2)),poles,angles_rad,eps_inf_angle_rad)
    real,loss=_real('eps_real',eps_real),_real('eps_loss',eps_loss)
    for name,value in [('eps_real',real),('eps_loss',loss)]:
        if value.shape!=(len(f),2,2):
            raise ValueError(f'{name} must have shape (frequencies,2,2)')
        scale=np.max(abs(value),axis=(1,2))
        normal=value/np.where(scale>0,scale,1)[:,None,None]
        if np.any(np.max(abs(normal-normal.swapaxes(-1,-2)),axis=(1,2))>1e-12):
            raise ValueError(f'{name} must be reciprocal within relative 1e-12')
        # Symmetrize only the validation expression; original entries remain
        # unchanged in the objective and in every output/residual.
        eigen=np.linalg.eigvalsh(.5*value+.5*value.swapaxes(-1,-2))
        if not np.all(np.isfinite(eigen)):
            raise ValueError(f'{name} has unrepresentable eigenvalues')
        if name=='eps_real':
            if np.any(eigen<=0) or np.any(eigen<1-1e-12*scale[:,None]):
                raise ValueError('real tensor eigenvalues must be >=1 within roundoff')
        elif np.any(eigen < -1e-12*scale[:,None]):
            raise ValueError('loss tensor must be positive semidefinite within roundoff')
    w=np.ones(len(f)) if weights is None else _real('weights',weights)
    if w.shape!=f.shape or np.any(w<=0):
        raise ValueError('weights must match every frequency and be positive')
    limit=_scalar('max_error',max_error)
    return f,real,loss,basis_model,w,limit


def fit_tensor_debye(frequency,*,eps_real,eps_loss,relaxation_hz,angles_rad,
                     eps_inf_angle_rad=0.0,max_error,weights=None):
    """Fit PSD strengths with fixed 1..16 poles and explicit real directions.

    Every frequency contributes all four real and four loss tensor entries to
    the weighted Frobenius objective; original samples are never clipped or
    averaged. Frequencies are 2..10000 increasing nonnegative Hz, poles are
    increasing positive Hz, and angles are radians from transverse global x.
    Nonnegative coefficients encode two high-frequency increments above one
    and two principal residue strengths per pole. Weights are positive per
    frequency and multiplying all weights by one factor leaves the fit intact.

    Require full design rank and condition<=1e10; NNLS cap is 10*unknown_count,
    with scaled KKT residual<=1e-10 and no retry. A finite accepted tensor model
    must result. max_error is a positive absolute per-frequency Frobenius limit,
    independent of objective weights. Above-limit fits retain all samples with
    accepted=False. No pole/angle search, continuous-band bound, uncertainty or
    measured-material validity is inferred. This operation performs no fields.
    """
    f,real,loss,base,w,limit=_tensor_fit_inputs(frequency,eps_real,eps_loss,
        relaxation_hz,angles_rad,eps_inf_angle_rad,max_error,weights)
    poles=np.array(base.relaxation_hz);n=2*(len(poles)+1)
    def projectors(angle):
        c,s=np.cos(angle),np.sin(angle);u=np.array([c,s]);v=np.array([-s,c])
        return (np.outer(u,u),np.outer(v,v))
    columns=[np.broadcast_to(p,(len(f),2,2)).astype(complex) for p in projectors(base.eps_inf_angle_rad)]
    for pole,angle in zip(poles,base.angles_rad):
        scale=np.maximum(f,pole);a,b=pole/scale,f/scale
        response=(a*a-1j*a*b)/(a*a+b*b)
        columns.extend(response[:,None,None]*p for p in projectors(angle))
    basis=np.stack(columns,axis=-1);rw=np.sqrt(w)/np.sqrt(np.max(w))
    matrix=np.concatenate([(basis.real*rw[:,None,None,None]).reshape(-1,n),
                           (-basis.imag*rw[:,None,None,None]).reshape(-1,n)])
    singular=np.linalg.svd(matrix,compute_uv=False)
    if len(singular)<n or singular[-1]<=0 or singular[-1]<singular[0]/1e10:
        raise ValueError('tensor fixed-basis design requires full rank and condition<=1e10')
    condition=float(singular[0]/singular[-1])
    if condition>1e10:raise ValueError('tensor fixed-basis condition exceeds 1e10')
    target_real=real-np.eye(2);amplitude=max(1.,float(np.max(abs(target_real))),float(np.max(abs(loss))))
    rhs=np.r_[((target_real/amplitude)*rw[:,None,None]).ravel(),((loss/amplitude)*rw[:,None,None]).ravel()]
    coef,_=nnls(matrix,rhs,maxiter=10*n)
    if not np.all(np.isfinite(coef)) or np.any(coef<0):
        raise RuntimeError('NNLS returned invalid nonnegative tensor coefficients')
    difference=matrix@coef-rhs;gradient=matrix.T@difference
    normalized=gradient/max(1.,float(singular[0]*np.linalg.norm(difference)))
    kkt=max(float(np.max(np.maximum(-normalized,0))),
            float(np.max(abs(coef*normalized)))/max(1.,float(np.max(coef))))
    if not np.isfinite(kkt) or kkt>1e-10:
        raise RuntimeError('tensor NNLS optimality residual exceeds 1e-10')
    with np.errstate(over='ignore',invalid='ignore'):
        coef=coef*amplitude
        model=TensorDebyeDielectric(1+coef[:2],coef[2:].reshape(-1,2),poles,base.angles_rad,base.eps_inf_angle_rad)
        predicted=model.permittivity(f);residual=predicted-(real-1j*loss)
    if not np.all(np.isfinite(residual)):
        raise RuntimeError('tensor fit residual is not representable')
    residual_scale=max(1.,float(np.max(abs(residual))))
    normalized_residual=residual/residual_scale
    with np.errstate(over='ignore',invalid='ignore'):
        maximum=residual_scale*float(np.max(np.linalg.norm(normalized_residual,axis=(1,2))))
        rms=residual_scale*float(np.linalg.norm(normalized_residual*rw[:,None,None])/np.linalg.norm(rw))
    if not np.isfinite(maximum) or not np.isfinite(rms):
        raise RuntimeError('tensor fit error metric is not representable')
    return TensorDebyeFit(model,f,real,loss,w,predicted,residual,condition,kkt,maximum,rms,limit)
