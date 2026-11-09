# 극점과 방향을 고정한 텐서 피팅

[저장 피팅 요청](tensor_dielectric_fit_document.md)은 엄격한 JSON과 공통 실행을 연결합니다.

[English](../../../../../packages/sipi/tensor_dielectric_fit.md) · [텐서 재료](tensor_debye.md) · [스칼라 피팅](dielectric_fit.md)

`fit_tensor_debye`는 `exp(+j omega t)` 규약의 명시적 상대 유전율 텐서 표본에
유한 [TensorDebyeDielectric](tensor_debye.md)를 맞춥니다. 각 잔차와 고주파 텐서의
주축 방향, 극점 주파수는 입력으로 고정합니다. 미지수는 1 위의 고주파 증분 두 개와
극점마다 잔차 강도 두 개이며 모두 음수가 아니어야 합니다. 결과는 수동·상반
횡방향 모델입니다. 극점/각도 자동 선택, 측정 불확실성 추정, 실측 유효성 인증은
수행하지 않습니다.

## 직접 피팅

```python
import json
import numpy as np
from sipi.dielectric import TensorDebyeDielectric, dielectric_from_dict
from sipi.tensor_dielectric_fit import fit_tensor_debye

frequency = np.geomspace(1e6, 1e12, 41)
poles, angles, high_angle = [1e8, 1e10], [0, .7], .31
original = TensorDebyeDielectric([2, 3], [[4, .5], [.25, 3]],
    poles, angles, high_angle)
samples = original.permittivity(frequency)  # synthetic demonstration data
result = fit_tensor_debye(frequency,
    eps_real=samples.real, eps_loss=-samples.imag,
    relaxation_hz=poles, angles_rad=angles, eps_inf_angle_rad=high_angle,
    max_error=1e-8)
assert result.accepted
record = result.to_dict()
json.dumps(record, allow_nan=False)
restored = dielectric_from_dict(record['model'])
np.testing.assert_array_equal(restored.permittivity(frequency), result.predicted)
```

주파수는 Hz 단위의 음수가 아닌 유한 값 2–10000개이며 엄격히 증가해야 합니다.
극점은 Hz 단위의 양의 유한 값 1–16개이며 중복 없이 증가해야 합니다.
각도는 전역 횡방향 x축에서 반시계 방향 라디안입니다. 극점과 같은 길이의 각도
벡터와 고주파 각도 `eps_inf_angle_rad` 하나(기본값 0)를 지정합니다.
`eps_real`·`eps_loss`는 각각 `(F,2,2)` 모양이고 `eps_real - j*eps_loss`를 뜻합니다.
상대 `1e-12` 이내에서 상반이어야 하며 실수부 고유값은 1 이상, 손실 행렬은 상대
반올림 오차 범위에서 양의 준정부호여야 합니다. 불리언·복소 성분 배열·비유한 값·
잘못된 모양은 거부합니다. 비대각 손실 성분 하나가 음수인 것은 허용될 수 있습니다.

선택적 가중치는 주파수마다 양수 하나이며 복소 잔차 네 성분의 제곱합에 곱합니다.
모든 가중치에 같은 상수를 곱해도 피팅은 같습니다. 목적함수는 원입력에서 허용된
작은 반대칭 오차까지 포함한 가중 Frobenius 제곱합입니다. 표본을 잘라내거나
평균으로 고치지 않습니다. `max_error`는 가중치와 독립적인 주파수별 절대 Frobenius
오차 한계이며 양수로 명시해야 합니다.

정규화된 가중 실수 설계행렬은 열 full rank와 condition `1e10` 이하를 요구합니다.
비음수 최소제곱의 반복 상한은 미지수 개수의 10배이며 재시도하지 않습니다.
정규화된 gradient/complementarity KKT 오차는 `1e-10` 이하여야 하고, 계수로 유한한
유효 텐서 모델을 만들 수 있어야 합니다. 나쁜 조건수·식별 불가·최적화 오류·잘못된
수치 인증은 예외로 반환합니다. 표본 수만 많다고 식별 가능성이 보장되지는 않습니다.

## 허용치를 넘는 후보도 보존

```python
unmatched = fit_tensor_debye(frequency,
    eps_real=samples.real, eps_loss=-samples.imag + .01*np.eye(2),
    relaxation_hz=poles, angles_rad=angles, eps_inf_angle_rad=high_angle,
    weights=np.geomspace(.5, 3, len(frequency)), max_error=1e-5)
assert not unmatched.accepted
assert unmatched.residual.shape == (len(frequency), 2, 2)
np.testing.assert_array_equal(unmatched.eps_loss, -samples.imag + .01*np.eye(2))
```

계산을 마치면 모든 원표본, 후보 모델, 예측, 잔차 `model-(eps_real-j*eps_loss)`,
condition과 KKT 진단을 보관합니다. 배열은 복사하여 읽기 전용으로 반환합니다.
`maximum_error`는 주파수별 Frobenius 잔차의 최댓값, `weighted_rms_error`는 가중
RMS입니다. 한계를 넘은 모델도 `accepted=False`로 유지합니다. 가중치를 줄여 최대
오차 판정에서 실패 표본을 숨길 수 없으며 정확히 한계와 같은 값은 수락합니다.

결과 모델을 기존 저장 선로·재료 입력에 넣을 수 있습니다. 반환 사전은 피팅 결과이며
저장 피팅 요청 스키마가 아닙니다. 이번 범위는 Python 직접 피팅과 재료 직렬화입니다.
피팅 중 전계 계산은 수행하지 않습니다. 작은 표본 오차는 메시·외곽 수렴, 연속 대역
오차 상한, 실제 적층재 인증, 새 플랫폼 지원을 뜻하지 않습니다. 고정 방향은 텐서
응답의 볼록 부분집합을 정의하며 모든 수동 텐서 스펙트럼을 표현하지 않습니다.

## 검사 재현

```sh
python -m pytest -q -s tests/sipi/test_tensor_dielectric_fit.py tests/sipi/test_dielectric_fit.py
```

독립 유리식으로 만든 텐서 표본은 계수 복원 `1e-9`, 예측 `1e-10`, 피팅에 쓰지 않은
합성 주파수 표본 `1e-9` 이내를 요구합니다. 최대 16극점 설계도 검사합니다.
회전된 단일 극점 16조합은 독립 두 변수 정규방정식과 가능한 경계 후보를 전수 비교합니다.
저장된 잡음 합성 사례는 seed 912와 PSD 섭동을 쓰며 독립 유리식 기저 및
`scipy.optimize.lsq_linear`의 BVLS 결과와 계수·예측 차이 `1e-8` 미만을 요구합니다.
두 최적화 경로 모두 SciPy 수치 기반을 쓰므로 해석적 경계·계수 검사와 함께 해석해야
합니다. 원입력 보존·수동성 한계·회전 공변성·가중치 공통 배율·극단 주파수·명시적
실패 경로도 검사합니다. 기존 스칼라 피팅의 수치 구현은 유지합니다.
