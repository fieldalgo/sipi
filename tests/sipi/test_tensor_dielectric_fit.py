# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent tensor fit references, analytic active sets and retained failures."""
from pathlib import Path
from dataclasses import FrozenInstanceError
import json
import numpy as np
import pytest
import sipi.tensor_dielectric_fit as implementation
from sipi.tensor_dielectric_fit import fit_tensor_debye
from sipi.dielectric import TensorDebyeDielectric,dielectric_from_dict
from crosscheck import require_tool,Stopwatch,make_record,observable,emit
from importlib import metadata

REFERENCE=json.loads((Path(__file__).parent/'reference_data'/'tensor_fit'/'reference.json').read_text())
F=np.array(REFERENCE['frequency_hz']);POLES=np.array(REFERENCE['relaxation_hz'])
ANGLES=np.array(REFERENCE['angles_rad']);HIGH=REFERENCE['eps_inf_angle_rad']


def fit(**changes):
    args=dict(eps_real=np.array(REFERENCE['exact_real']),eps_loss=np.array(REFERENCE['exact_loss']),
        relaxation_hz=POLES.copy(),angles_rad=ANGLES.copy(),eps_inf_angle_rad=HIGH,max_error=1e-9)
    args.update(changes)
    return fit_tensor_debye(F,**args)


def rotation(angle):
    c,s=np.cos(angle),np.sin(angle);return np.array([[c,-s],[s,c]])


def rational(f,high,strengths,poles,angles,high_angle):
    q=rotation(high_angle);base=q@np.diag(high)@q.T
    matrices=[rotation(t)@np.diag(d)@rotation(t).T for d,t in zip(strengths,angles)]
    return np.array([base.astype(complex)+sum(a/(1+1j*x/p) for a,p in zip(matrices,poles)) for x in f])


def coefficients(result):return np.r_[np.array(result.model.eps_inf)-1,np.array(result.model.strengths).ravel()]


@pytest.mark.parametrize('high,strengths',[
 ([2,3],[[4,0],[.25,3]]),([1,3],[[0,.5],[.25,0]]),([1,1],[[0,0],[0,0]]),([2,2],[[4,4],[.5,.5]])])
def test_independent_rational_coefficients_heldout_and_passivity(high,strengths):
    eps=rational(F,high,strengths,POLES,ANGLES,HIGH)
    actual=fit(eps_real=eps.real,eps_loss=-eps.imag)
    np.testing.assert_allclose(coefficients(actual),np.r_[np.array(high)-1,np.array(strengths).ravel()],rtol=0,atol=1e-9)
    np.testing.assert_allclose(actual.predicted,eps,rtol=0,atol=1e-10)
    heldout=np.geomspace(3e5,7e12,29)
    np.testing.assert_allclose(actual.model.permittivity(heldout),rational(heldout,high,strengths,POLES,ANGLES,HIGH),rtol=0,atol=1e-9)
    assert actual.accepted and actual.scaled_kkt_error<=1e-10 and actual.condition<=1e10
    samples=actual.model.permittivity(np.r_[0.,np.geomspace(1e-10,1e30,101)])
    assert np.linalg.eigvalsh(samples.real).min()>=1-1e-12*np.max(abs(samples.real))
    assert np.linalg.eigvalsh(-samples.imag).min()>=-1e-12*np.max(abs(samples.imag))
    restored=dielectric_from_dict(actual.to_dict()['model'])
    np.testing.assert_array_equal(restored.permittivity(F),actual.predicted)


def active_set(f,real,loss):
    # Two independent scalar normal equations; enumerate all feasible boundaries.
    r=1/(1+f*f);l=f/(1+f*f);y=real-1
    aa,ab,bb=len(f),sum(r),sum(r*r+l*l);ay,by=sum(y),sum(r*y+l*loss)
    determinant=aa*bb-ab*ab
    interior=np.array([(ay*bb-ab*by)/determinant,(aa*by-ab*ay)/determinant])
    candidates=[np.array([max(ay/aa,0),0]),np.array([0,max(by/bb,0)]),np.zeros(2)]
    if np.all(interior>=0):candidates.append(interior)
    return min(candidates,key=lambda x:sum((x[0]+r*x[1]-y)**2+(l*x[1]-loss)**2))


def scalar_case(name,f):
    if name=='interior':return 2+3/(1+f*f),3*f/(1+f*f)
    if name=='constant':return np.array([2,2.5,3,3.5]),np.zeros(4)
    if name=='baseline':return np.ones(4),np.array([0,.2,1,.3])
    return np.ones(4),np.zeros(4)


@pytest.mark.parametrize('a',['interior','constant','baseline','zero'])
@pytest.mark.parametrize('b',['interior','constant','baseline','zero'])
def test_rotated_common_axis_analytic_boundary_enumeration(a,b):
    f=np.array([0.,.1,1.,10.]);angle=.37;q=rotation(angle)
    r1,l1=scalar_case(a,f);r2,l2=scalar_case(b,f)
    real=np.array([q@np.diag(x)@q.T for x in zip(r1,r2)])
    loss=np.array([q@np.diag(x)@q.T for x in zip(l1,l2)])
    first,second=active_set(f,r1,l1),active_set(f,r2,l2)
    actual=fit_tensor_debye(f,eps_real=real,eps_loss=loss,relaxation_hz=[1],angles_rad=[angle],eps_inf_angle_rad=angle,max_error=1e-8)
    np.testing.assert_allclose(coefficients(actual),[first[0],second[0],first[1],second[1]],rtol=0,atol=1e-10)
    if a in ('constant','baseline') or b in ('constant','baseline'):assert not actual.accepted


def test_independent_bvls_full_frobenius_and_above_limit_preservation():
    require_tool('scipy')
    from scipy.optimize import lsq_linear
    real=np.array(REFERENCE['noisy_real']);loss=np.array(REFERENCE['noisy_loss']);w=np.array(REFERENCE['weights'])
    clock=Stopwatch()
    with clock('openphysics'):actual=fit(eps_real=real,eps_loss=loss,weights=w,max_error=1e-5)
    # Independently construct columns using direct complex rational division.
    columns=[]
    for d in ([1,0],[0,1]):
        q=rotation(HIGH);columns.append(np.broadcast_to(q@np.diag(d)@q.T,(len(F),2,2)).astype(complex))
    for p,t in zip(POLES,ANGLES):
        q=rotation(t)
        for d in ([1,0],[0,1]):columns.append(np.array([(q@np.diag(d)@q.T)/(1+1j*f/p) for f in F]))
    basis=np.stack(columns,axis=-1);rw=np.sqrt(w)[:,None,None,None]
    a=np.concatenate([(basis.real*rw).reshape(-1,6),(-basis.imag*rw).reshape(-1,6)])
    b=np.r_[((real-np.eye(2))*np.sqrt(w)[:,None,None]).ravel(),(loss*np.sqrt(w)[:,None,None]).ravel()]
    with clock('reference'):ref=lsq_linear(a,b,bounds=(0,np.inf),method='bvls',tol=1e-14,max_iter=1000)
    assert ref.success
    np.testing.assert_allclose(ref.x,REFERENCE['reference_coefficients'],rtol=0,atol=1e-10)
    error=float(np.max(abs(coefficients(actual)-ref.x)))
    expected=np.eye(2)+np.einsum('fijp,p->fij',basis,ref.x)
    prediction=float(np.max(abs(actual.predicted-expected)))
    record=make_record(case='fixed-orientation-tensor-debye-fit',physics='passive reciprocal transverse tensor relaxation',
        api='sipi.tensor_dielectric_fit.fit_tensor_debye',discretization='stable fixed-basis nonnegative Frobenius least squares',
        tool='scipy',tool_discretization='independent rational basis and bounded variable least squares',
        matched=['fixed poles/orientations, original tensor samples, weights and nonnegative coefficient bounds'],
        not_matched=['both algorithms use SciPy primitives; separate analytic active-set cases apply','synthetic samples, no measured validity or continuous-band bound'],
        observables=[observable('coefficients','1','maximum absolute difference',error,1e-8),observable('tensor prediction','1','maximum absolute difference',prediction,1e-8)],
        analytical_acceptance='rotated independent one-pole boundary enumeration and synthetic held-out tensor recovery',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'));emit(record)
    assert max(error,prediction)<1e-8 and not actual.accepted
    np.testing.assert_array_equal(actual.eps_real,real);np.testing.assert_array_equal(actual.eps_loss,loss)
    np.testing.assert_array_equal(actual.residual,actual.predicted-(real-1j*loss))
    norms=np.linalg.norm(actual.residual,axis=(1,2))
    assert actual.maximum_error==pytest.approx(max(norms),rel=1e-12)
    assert actual.weighted_rms_error==pytest.approx(np.sqrt(sum(w*norms**2)/sum(w)),rel=1e-12)
    assert np.linalg.norm(a@coefficients(actual)-b)**2==pytest.approx(REFERENCE['reference_objective'],rel=1e-10)
    assert fit(eps_real=real,eps_loss=loss,weights=w,max_error=actual.maximum_error).accepted


def test_rotation_covariance_global_weight_scale_and_immutable_inputs():
    real=np.array(REFERENCE['exact_real']);loss=np.array(REFERENCE['exact_loss']);w=np.geomspace(1,100,len(F))
    actual=fit(eps_real=real,eps_loss=loss,weights=w)
    scaled=fit(eps_real=real,eps_loss=loss,weights=w*1e200)
    np.testing.assert_allclose(coefficients(actual),coefficients(scaled),rtol=0,atol=1e-9)
    angle=.73;q=rotation(angle)
    other=fit(eps_real=q@real@q.T,eps_loss=q@loss@q.T,weights=w,angles_rad=ANGLES+angle,eps_inf_angle_rad=HIGH+angle)
    np.testing.assert_allclose(other.predicted,q@actual.predicted@q.T,rtol=0,atol=1e-9)
    real[:]=0;loss[:]=0;w[:]=0
    np.testing.assert_array_equal(actual.eps_real,REFERENCE['exact_real'])
    for name in ('frequency','eps_real','eps_loss','weights','predicted','residual'):assert not getattr(actual,name).flags.writeable
    with pytest.raises(FrozenInstanceError):actual.maximum_error=0
    raw=actual.to_dict();json.dumps(raw,allow_nan=False);raw['model']['parameters']['strengths'][0][0]=-1
    assert actual.model.strengths[0][0]>=0


def test_original_antisymmetric_roundoff_retained_in_objective_and_error():
    real=np.array(REFERENCE['exact_real']);real[:,0,1]+=1e-13
    result=fit(eps_real=real,max_error=1e-15)
    np.testing.assert_array_equal(result.eps_real,real)
    np.testing.assert_array_equal(result.residual,result.predicted-(real-1j*np.array(REFERENCE['exact_loss'])))
    assert result.maximum_error>1e-14 and not result.accepted


def test_extreme_frequencies_and_no_field_work(monkeypatch):
    from sipi import CrossSection
    def forbidden(*a,**k):pytest.fail('fitting performed field work')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    f=np.array([0.,1e100,1e200,1e308]);p=[1e100,1e200]
    original=TensorDebyeDielectric([2,3],[[1,.5],[3,2]],p,ANGLES,HIGH);eps=original.permittivity(f)
    with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
        result=fit_tensor_debye(f,eps_real=eps.real,eps_loss=-eps.imag,relaxation_hz=p,angles_rad=ANGLES,eps_inf_angle_rad=HIGH,max_error=1e-8)
    assert result.accepted
    np.testing.assert_allclose(coefficients(result),[1,2,1,.5,3,2],rtol=0,atol=1e-8)


@pytest.mark.parametrize('kind',['few','many','duplicate_frequency','negative_frequency','boolean_frequency','infinite_frequency',
 'empty_poles','many_poles','duplicate_poles','negative_pole','boolean_pole','nan_pole','angle_shape','angle_boolean','angle_nonfinite','high_shape','high_boolean',
 'real_shape','loss_shape','real_boolean','loss_complex','real_infinite','loss_nan','real_asymmetric','loss_asymmetric','real_below_one','loss_indefinite',
 'weight_shape','weight_zero','weight_boolean','weight_infinite','limit_zero','limit_boolean','limit_infinite','rank','condition'])
def test_invalid_inputs_and_unidentifiable_basis_reject_before_optimizer(monkeypatch,kind):
    f=F.copy();args=dict(eps_real=np.array(REFERENCE['exact_real']),eps_loss=np.array(REFERENCE['exact_loss']),
        relaxation_hz=POLES.copy(),angles_rad=ANGLES.copy(),eps_inf_angle_rad=HIGH,weights=np.ones(len(F)),max_error=1e-9)
    if kind=='few':f=[1.]
    if kind=='many':f=np.arange(10001.)
    if kind=='duplicate_frequency':f[1]=f[0]
    if kind=='negative_frequency':f[0]=-1
    if kind=='boolean_frequency':f=[False,True]
    if kind=='infinite_frequency':f[-1]=np.inf
    if kind=='empty_poles':args['relaxation_hz']=[]
    if kind=='many_poles':args['relaxation_hz']=np.arange(1,18.)
    if kind=='duplicate_poles':args['relaxation_hz']=[1,1]
    if kind=='negative_pole':args['relaxation_hz']=[-1,1]
    if kind=='boolean_pole':args['relaxation_hz']=[True,2]
    if kind=='nan_pole':args['relaxation_hz']=[1,np.nan]
    if kind=='angle_shape':args['angles_rad']=[0]
    if kind=='angle_boolean':args['angles_rad']=[True,0]
    if kind=='angle_nonfinite':args['angles_rad']=[0,np.inf]
    if kind=='high_shape':args['eps_inf_angle_rad']=[0]
    if kind=='high_boolean':args['eps_inf_angle_rad']=False
    if kind=='real_shape':args['eps_real']=np.ones((len(f),2))
    if kind=='loss_shape':args['eps_loss']=np.zeros((2,2))
    if kind=='real_boolean':args['eps_real']=np.ones((len(f),2,2),dtype=bool)
    if kind=='loss_complex':args['eps_loss']=args['eps_loss'].astype(complex)
    if kind=='real_infinite':args['eps_real'][0,0,0]=np.inf
    if kind=='loss_nan':args['eps_loss'][0,0,0]=np.nan
    if kind=='real_asymmetric':args['eps_real'][1,0,1]+=.1
    if kind=='loss_asymmetric':args['eps_loss'][1,0,1]+=.1
    if kind=='real_below_one':args['eps_real'][0]=.9*np.eye(2)
    if kind=='loss_indefinite':args['eps_loss'][0]=np.diag([-1,1])
    if kind=='weight_shape':args['weights']=1.
    if kind=='weight_zero':args['weights'][0]=0
    if kind=='weight_boolean':args['weights']=[True]*len(f)
    if kind=='weight_infinite':args['weights'][0]=np.inf
    if kind=='limit_zero':args['max_error']=0
    if kind=='limit_boolean':args['max_error']=True
    if kind=='limit_infinite':args['max_error']=np.inf
    if kind=='rank':args.update(relaxation_hz=[1e-300,2e-300],angles_rad=[0,0])
    if kind=='condition':args.update(relaxation_hz=[1e9,1e9*(1+1e-12)],angles_rad=[0,0])
    def forbidden(*a,**k):pytest.fail('inadmissible input reached NNLS')
    monkeypatch.setattr(implementation,'nnls',forbidden)
    with pytest.raises(ValueError):fit_tensor_debye(f,**args)


@pytest.mark.parametrize('kind',['failure','negative','nonfinite','not_optimal'])
def test_optimizer_failure_never_becomes_accepted(monkeypatch,kind):
    def fake(matrix,rhs,*,maxiter):
        assert maxiter==10*matrix.shape[1]
        if kind=='failure':raise RuntimeError('optimizer failed')
        x=np.zeros(matrix.shape[1])
        if kind=='negative':x[0]=-1
        if kind=='nonfinite':x[0]=np.nan
        return x,0.
    monkeypatch.setattr(implementation,'nnls',fake)
    with pytest.raises(RuntimeError):fit()


def test_largest_declared_pole_count_recovers_independent_rational_tensor():
    poles=np.geomspace(1e1,1e16,16);f=np.r_[0.,np.geomspace(1,1e17,161)]
    angles=np.linspace(-.6,.7,16);strengths=np.column_stack([np.linspace(.1,.3,16),np.linspace(.4,.2,16)])
    expected=rational(f,[2,3],strengths,poles,angles,.31)
    result=fit_tensor_debye(f,eps_real=expected.real,eps_loss=-expected.imag,relaxation_hz=poles,
        angles_rad=angles,eps_inf_angle_rad=.31,max_error=1e-9)
    assert result.accepted and len(result.model.strengths)==16 and result.condition<=1e10
    np.testing.assert_allclose(result.model.strengths,strengths,rtol=0,atol=1e-9)
    np.testing.assert_allclose(result.predicted,expected,rtol=0,atol=1e-10)
