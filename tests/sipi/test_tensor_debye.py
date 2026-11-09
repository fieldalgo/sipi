# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent tensor relaxation identities and strict immutable inputs."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import copy
import json
import numpy as np
import pytest
from sipi.dielectric import (TensorDebyeDielectric,
    dielectric_to_dict as tensor_to_dict, dielectric_from_dict as tensor_from_dict)
from sipi.dielectric import DebyeDielectric, PrincipalAxisDielectric, dielectric_to_dict

F=np.array([0.,1e6,1e8,1e10,1e14])
PARAMS=dict(eps_inf=[2.,3.],strengths=[[4.,.5],[.25,3.]],
    relaxation_hz=[1e8,1e10],angles_rad=[0.,np.pi/4],eps_inf_angle_rad=0.)


def model(**changes):return TensorDebyeDielectric(**dict(PARAMS,**changes))


def rotation(angle):
    c,s=np.cos(angle),np.sin(angle)
    return np.array([[c,-s],[s,c]])


def test_independent_preregistered_rational_reference_and_noncommuting_frames():
    reference=json.loads((Path(__file__).parent/'reference_data'/'tensor_debye'/'reference.json').read_text())
    expected=np.array(reference['real'])+1j*np.array(reference['imag'])
    actual=model().permittivity(reference['frequency_hz'])
    np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-14)
    def comm(a,b):return np.linalg.norm(a@b-b@a)/(np.linalg.norm(a)*np.linalg.norm(b))
    assert max(comm(actual[i].real,actual[j].real) for i in range(3) for j in range(i))>1e-3
    assert max(comm(a.real,-a.imag) for a in actual)>1e-3


@pytest.mark.parametrize('angle',[0.,.4,np.pi/2,-.7])
def test_common_frame_reproduces_legacy_principal_debye(angle):
    actual=model(angles_rad=[angle,angle],eps_inf_angle_rad=angle)
    old=PrincipalAxisDielectric(DebyeDielectric(2,[4,.25],[1e8,1e10]),
        DebyeDielectric(3,[.5,3],[1e8,1e10]),angle)
    before=dielectric_to_dict(old)
    np.testing.assert_allclose(actual.permittivity(F),old.permittivity(F),rtol=1e-12,atol=1e-14)
    assert dielectric_to_dict(old)==before and before['schema']=='sipi.dielectric/2'
    with pytest.raises(ValueError):PrincipalAxisDielectric(actual,DebyeDielectric(2,[1],[1e8]))


def test_isotropic_limit_rotation_covariance_and_term_permutation():
    isotropic=model(eps_inf=[2,2],strengths=[[4,4],[.5,.5]],eps_inf_angle_rad=.6)
    expected=DebyeDielectric(2,[4,.5],[1e8,1e10]).permittivity(F)[:,None,None]*np.eye(2)
    np.testing.assert_allclose(isotropic.permittivity(F),expected,rtol=1e-12,atol=1e-14)
    original=model();angle=.73;q=rotation(angle)
    rotated=model(eps_inf_angle_rad=angle,angles_rad=np.array(PARAMS['angles_rad'])+angle)
    np.testing.assert_allclose(rotated.permittivity(F),q@original.permittivity(F)@q.T,rtol=1e-12,atol=1e-14)
    reversed_terms=model(strengths=PARAMS['strengths'][::-1],relaxation_hz=PARAMS['relaxation_hz'][::-1],angles_rad=PARAMS['angles_rad'][::-1])
    np.testing.assert_allclose(reversed_terms.permittivity(F),original.permittivity(F),rtol=1e-12,atol=1e-14)
    assert tensor_to_dict(reversed_terms)['parameters']['relaxation_hz']==[1e10,1e8]


def test_scalar_vector_shapes_dc_high_frequency_and_detached_output():
    m=model();samples=m.permittivity(F)
    assert samples.shape==(5,2,2) and m.permittivity(0.).shape==(2,2)
    np.testing.assert_array_equal(samples[2],m.permittivity(F[2]))
    expected=rotation(0.)@np.diag(PARAMS['eps_inf'])@rotation(0.).T
    for d,t in zip(PARAMS['strengths'],PARAMS['angles_rad']):expected+=rotation(t)@np.diag(d)@rotation(t).T
    np.testing.assert_allclose(samples[0],expected,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(m.permittivity(1e300),np.diag(PARAMS['eps_inf']),rtol=1e-12,atol=1e-14)
    samples[:]=99
    assert not np.array_equal(samples,m.permittivity(F))


@pytest.mark.parametrize('params',[{},dict(strengths=[[4,0],[0,0]]),dict(eps_inf=[1,1],strengths=[[0,0],[0,0]])])
def test_passive_reciprocal_tensor_over_wide_finite_grid(params):
    eps=model(**params).permittivity(np.r_[0.,np.logspace(-10,30,301)])
    np.testing.assert_array_equal(eps,eps.swapaxes(-1,-2))
    assert np.isfinite(eps).all()
    assert np.linalg.eigvalsh(eps.real).min()>=1-1e-12*np.max(abs(eps.real))
    loss=-eps.imag
    assert np.linalg.eigvalsh(loss).min()>=-1e-12*np.max(abs(loss))


def test_extreme_finite_relaxations_do_not_overflow_ratios():
    m=model(relaxation_hz=[1e-300,1e308])
    f=np.array([0.,1e-300,1e-100,1.,1e100,1e300,1e308])
    with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
        eps=m.permittivity(f)
    assert np.isfinite(eps).all()
    np.testing.assert_array_equal(eps,eps.swapaxes(-1,-2))
    residue=rotation(np.pi/4)@np.diag([.25,3.])@rotation(np.pi/4).T
    np.testing.assert_allclose(eps[-1],np.diag([2,3])+(.5-.5j)*residue,rtol=1e-12,atol=1e-14)


def test_deeply_immutable_constructor_and_detached_exact_json():
    p=copy.deepcopy(PARAMS);m=TensorDebyeDielectric(**p);before=m.permittivity(F)
    p['eps_inf'][0]=99;p['strengths'][0][0]=99;p['angles_rad'][0]=99
    np.testing.assert_array_equal(m.permittivity(F),before)
    assert isinstance(m.strengths,tuple) and isinstance(m.strengths[0],tuple)
    with pytest.raises(FrozenInstanceError):m.eps_inf=(9,9)
    raw=tensor_to_dict(m);canonical=json.dumps(raw,allow_nan=False,sort_keys=True)
    assert raw['schema']=='sipi.dielectric/3' and raw['kind']=='tensor-debye'
    restored=tensor_from_dict(json.loads(canonical));assert restored==m
    assert json.dumps(tensor_to_dict(restored),allow_nan=False,sort_keys=True)==canonical
    raw['parameters']['strengths'][0][0]=99
    np.testing.assert_array_equal(m.permittivity(F),before)


def test_term_count_limit_accepts_declared_maximum():
    m=TensorDebyeDielectric([2,3],[[1,0]]*64,[1e8]*64,[.4]*64)
    assert len(m.strengths)==64 and np.isfinite(m.permittivity(F)).all()


@pytest.mark.parametrize('change',[
 dict(eps_inf=2),dict(eps_inf=[2]),dict(eps_inf=[[2,0],[0,3]]),dict(eps_inf=[.9,3]),
 dict(eps_inf=[True,3]),dict(eps_inf=[np.inf,3]),dict(eps_inf=[2+0j,3]),dict(eps_inf=['2',3]),
 dict(strengths=[]),dict(strengths=[1,2]),dict(strengths=[[1],[2]]),dict(strengths=[[1,2,3]]),
 dict(strengths=[[1,-.1],[2,3]]),dict(strengths=[[True,1],[2,3]]),dict(strengths=[[np.nan,1],[2,3]]),
 dict(strengths=[[1+0j,1],[2,3]]),dict(strengths=[['1',1],[2,3]]),
 dict(strengths=[[1,1]]*65,relaxation_hz=[1e8]*65,angles_rad=[0.]*65),
 dict(relaxation_hz=[0,1]),dict(relaxation_hz=[1,-1]),dict(relaxation_hz=[1]),
 dict(relaxation_hz=[True,1]),dict(relaxation_hz=[np.inf,1]),dict(relaxation_hz=[[1,2]]),
 dict(angles_rad=0),dict(angles_rad=[0]),dict(angles_rad=[np.nan,0]),dict(angles_rad=[False,0]),
 dict(angles_rad=[0+0j,0]),dict(angles_rad=['0',0]),
 dict(eps_inf_angle_rad=True),dict(eps_inf_angle_rad=[0]),dict(eps_inf_angle_rad=np.inf),dict(eps_inf_angle_rad=0j),
 dict(eps_inf=[1e308,1e308],strengths=[[1e308,0],[0,1e308]]),
])
def test_invalid_parameters_reject_before_evaluation(change):
    with pytest.raises(ValueError):model(**change)


@pytest.mark.parametrize('frequency',[[],[1,-1],-1,True,[True,1],np.inf,[1,np.nan],1j,'1',[[1,2]]])
def test_invalid_frequency_shape_or_type_rejects(frequency):
    with pytest.raises(ValueError):model().permittivity(frequency)


@pytest.mark.parametrize('mutation',[
 lambda x:x.update(extra=1),lambda x:x.update(schema='sipi.dielectric/2'),
 lambda x:x.update(kind='principal-axes'),lambda x:x.update(kind=[]),lambda x:x.pop('kind'),
 lambda x:x.update(parameters=[]),lambda x:x['parameters'].update(extra=1),
 lambda x:x['parameters'].pop('eps_inf_angle_rad'),
 lambda x:x['parameters'].update(eps_inf=[True,3]),
 lambda x:x['parameters'].update(relaxation_hz=[-1,1]),
])
def test_strict_versioned_model_document(mutation):
    raw=tensor_to_dict(model());mutation(raw)
    with pytest.raises(ValueError):tensor_from_dict(raw)
