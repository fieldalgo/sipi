# 고정 relaxation pole의 수동 Debye 재료 fitting

[English](../../../../../packages/sipi/dielectric_fit.md) · [유전체 모델](dielectrics.md)

`fit_debye`는 명시한 실수 유전율과 0 이상 유전체 손실 표본에 기존
`DebyeDielectric`을 맞춥니다. relaxation 주파수는 입력으로 고정하고
`eps_inf >= 1`, 0 이상의 strength만 구합니다. 원래 표본·가중치·예측·잔차와
오차 기준 판정을 모두 보존합니다.

```python
import json
import numpy as np
from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import fit_debye

frequency = np.geomspace(1e6, 1e12, 61)
poles = [1e8, 1e9, 1e10]
known = DebyeDielectric(2., [.8, 0., 1.2], poles)
samples = known.permittivity(frequency)
fit = fit_debye(frequency, eps_real=samples.real, eps_loss=-samples.imag,
               relaxation_hz=poles, max_error=1e-8)
assert fit.accepted and fit.maximum_error <= 1e-8
np.testing.assert_allclose(fit.model.strengths, [.8, 0., 1.2], atol=1e-8, rtol=0)
report = fit.to_dict()
json.dumps(report, allow_nan=False)
restored = dielectric_from_dict(report['model'])
np.testing.assert_array_equal(restored.permittivity(frequency), fit.predicted)
```

예제는 실측이 아닌 합성 표본입니다. 결과 모델은 기존 선로·공차·역산의 재료 API와
저장 재료 record에 넣을 수 있습니다. [저장 fitting 요청](dielectric_fit_document.md)은
dielectric-fit/1과 공통 실행으로 같은 알고리즘을 재사용합니다.

## 입력과 목적 함수

중복 없이 증가하는 0 이상 주파수 2–10000개와 양수 relaxation pole 1–32개를
Hz로 지정합니다. DC를 포함할 수 있습니다. `eps_real`, `eps_loss`는 주파수와
같은 길이의 유한 실수 배열이며 각각 1 이상, 0 이상이어야 합니다.
exp(+j omega t)에서 `eps = eps_real - j*eps_loss`입니다. 부호 교정·clipping,
누락 행 제거·pole 추정은 하지 않습니다.

선택적인 `weights`는 모든 주파수에서 양수 유한 값이며 기본은 1입니다.
목적 함수는 `sum(weights * abs(model_eps - input_eps)**2)`로, 같은 주파수의
실수·손실 성분에 같은 가중치를 적용합니다. 모든 가중치를 같은 양수 배율로 바꿔도
fit은 같습니다. 가중치는 지정한 목적 함수의 의미이며 자동으로 실측 불확도나
신뢰수준을 뜻하지 않습니다.

실수 설계행렬에는 Debye relaxation의 실수·양수 손실 성분과 eps_inf-1의 상수
열을 쌓습니다. SciPy NNLS 전에 가중치와 목표 크기를 정규화합니다. 행렬은 full
column rank이고 조건수가 1e10 이하여야 합니다. 거의 구분되지 않는 pole이나
정보가 부족한 표본은 유일한 정답처럼 출력하지 않고 거부합니다. relaxation 기저는
주파수 비율·제곱의 overflow를 피하도록 계산합니다.

NNLS 반복 한도는 10*(pole 수+1)이며 재시도하지 않습니다. 반환된 비음수 계수는
scaled KKT 검사 1e−10 이하여야 합니다. 목적 함수 gradient는 음수가 아니고
계수와 gradient의 곱은 0이어야 합니다. gradient scale은 max(1, 최대 singular
value × 잔차 norm)이며 상보성 검사에는 max(1, 최대 계수)도 나눕니다. 정규화한
최적화 변수의 검사이고 통계적 오차 상한은 아닙니다. 비유한 결과·미수렴·최적성
검사 실패는 예외입니다.

## 결과와 수락

`max_error`는 필수 양수이며 **입력 주파수 전체에서 가장 큰 복소 유전율 잔차**의
절대 제한입니다. 가중치와 독립이며 maximum_error <= error_limit일 때만
`accepted=True`입니다. 수치적으로 유효하지만 기준을 넘는 fit도 후보·전체 잔차를
`accepted=False`로 반환합니다. 행을 버리거나 다른 tolerance를 선택하지 않습니다.

`DebyeFit`는 모델과 원래 주파수·실수·손실·가중치 배열, 복소 `predicted`,
`residual`, 행렬 조건수·scaled KKT 오류·최대 오차·가중 복소 RMS 오차·요청한
오차 제한을 보존합니다. 잔차는 음수 허수 손실 부호를 포함해 모델−입력입니다.
배열은 읽기 전용 사본이며 `to_dict()`는 분리된 유한 값, 복소 값의 실수/허수
배열과 기존 버전 있는 유전체 모델 record를 반환합니다.

비음수 Debye strength와 양수 pole은 수학적으로 수동·인과적인 모델을 정의합니다.
표본 fitting 성공이 실물 재료 유효범위·불확도·표본 사이 오차 상한·외삽 정확도를
보장하지는 않습니다. pole은 최적화하지 않습니다. 도체/fixture deembedding,
거칠기 fitting, 텐서 축 fitting이나 필드와 결합한 역문제는 수행하지 않습니다.

## 검증

합성 다중 pole 계수와 strength=0·상수·eps_inf=1 한계는 절대 1e−8 이내로
복원합니다. 독립 단일 pole의 모든 active-set 경계를 직접 비교한 해는 1e−10
이내입니다. 별도 SciPy 1.18.1 bounded-variable least squares와 직접 복소 기저의
계수·예측은 1e−8 이내로 일치합니다. 두 알고리즘 모두 SciPy 수치 연산을 사용하므로
해석적 검사를 별도로 유지합니다. 일부러 맞지 않는 표본 보존·가중치 배율 불변·나쁜
조건수 거부·수치 실패·큰 유한 주파수도 검사합니다.

fit 모델의 저장·전방 선로 추출은 알려진 합성 재료를 1e−8 이내로 재현합니다.
fitting 자체에는 메시 연산이 없으며 기존 전방 재료·필드 수렴 근거는 별도로
적용됩니다. 새 플랫폼이나 실측 재료 수락을 뜻하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_dielectric_fit.py tests/sipi/test_dielectric.py tests/sipi/test_line_model.py
```
