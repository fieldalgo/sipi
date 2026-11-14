# 고정 반경의 표면 거칠기 피팅

`fit_huray`는 **명시적으로 고정한 반경**에서 기존 `CausalHuray` 법칙의 음이
아닌 구 표면적 비율을 피팅합니다. 복소 표면 임피던스 표본(ohm/square,
`resistance + j*reactance`, exp(+jωt))과 알려진 금속 전도도(S/m)·상대투자율이
필요합니다. 구성 표면 모델의 피팅이며 PCB S 파라미터에서 표면 임피던스를
추출하거나 Ra/Rq/Rz로 반경을 추정하지 않습니다.

```python
import numpy as np
from sipi.conductor import surface_impedance
from sipi.roughness import CausalHuray
from sipi.roughness_fit import fit_huray

frequency = np.geomspace(1e6, 1e11, 41)
radii = [.2e-6, 1.2e-6, 4e-6]
# Synthetic demonstration; substitute independently obtained surface samples.
samples = surface_impedance(frequency, conductivity=58e6,
    roughness=CausalHuray(radii, [.7, 2., 1.5]))
result = fit_huray(frequency, resistance=samples.real, reactance=samples.imag,
    radii_m=radii, conductivity=58e6, max_error_ratio=1e-8)
assert result.accepted
print(result.model.surface_ratios)
# The model can be used wherever CausalHuray is already accepted.
assert result.maximum_error_ratio < 1e-8
```

입력 주파수는 엄격히 증가하는 양수 2..10000개, 반경은 m 단위로 엄격히
증가하는 양수 1..16개입니다. 측정 R/X 모두 유한한 양수여야 하며 불리언,
복소수, 모양이 맞지 않는 숫자 배열은 거부합니다. 기존 good-conductor 기준을
유지합니다. 매끈한 금속 응답보다 작은 양의 표본도 불일치 가능성이 있는
자료로 보존하며 모델에 맞도록 잘라내지 않습니다.

알려진 매끈한 표면 임피던스 `Zs`에 대해 음이 아닌 표면적 비율로
`sum(weights * abs((Zmodel - Zinput)/Zs)**2)`를 최소화합니다. 복소 구 응답을
실수 적층 최소제곱 행렬로 만들며 전체 열 순위와 조건수 <=1e10을 요구합니다.
NNLS 반복 예산은 반경 수의 10배로 고정하며 재시도하지 않습니다. 스케일한
KKT 최적성 오차가 1e-10을 넘으면 실패합니다. 가중치 기본값은 모두 1이며
전체에 같은 양수를 곱해도 목적함수의 해는 바뀌지 않습니다.

`accepted`는 **표본 중 매끈한 응답으로 정규화한 복소 오차의 최댓값**이
명시적 `max_error_ratio` 이하라는 뜻뿐입니다. 목적함수의 가중치와 독립된
기준입니다. 초과한 후보도 `accepted=False`와 모든 원본 표본·예측·정규화 잔차·
가중 RMS·조건수·KKT 진단을 반환합니다. 입력을 복사하며 결과 배열은 읽기
전용입니다. 수치/입력 오류에서는 후보를 만들어내지 않고 예외를 냅니다.
`to_dict()['model']`은 기존 `causal-huray` 재료 형식입니다.

음이 아닌 구 모델의 기존 수동·인과적 연장은 유지합니다. 표본 일치가 측정
불확실성, 잡음 아래 파라미터 유일성, 연속 대역 정확도나 표본 밖 물리적
유효성을 입증하지 않습니다. 반경·전도도·투자율은 가정한 입력이며 추정한
실측값이 아닙니다. 자동 반경/개수 선택, 전도도 동시 추출, 실측 foil 보정,
공간적으로 분포한 일반 2D 거친 표면 또는 자기 히스테리시스는 제공하지 않습니다.

## 검증

시험은 구 응답의 실수·허수 유리식을 독립적으로 생성합니다. 반경 0.2/1.2/4 µm,
표면적 비율 0.7/2/1.5, 58 MS/m, 1 MHz–100 GHz의 합성 자료에서 비율 1e-8·예측
1e-10 기준으로 복원합니다. 1..4개 구 집단을 음이 아닌 active set 전수조사와
별도 SciPy BVLS 최적화로 비교합니다. 두 수치 최적화는 SciPy 기반 연산을
공유하며 active set 전수조사·해석 응답이 별도 근거입니다. 불일치 표본 보존,
0 비율, 가중치 배율, 순위 부족, 입력 불변 및 최적화/KKT 실패도 검사합니다.
피팅에서 메시나 외곽 경계를 풀지 않습니다. 피팅한 법칙을 선로에 적용할 때는
기하·표피 깊이와 메시·외곽 수렴 기준이 계속 필요합니다.

[English](../../../../packages/sipi/roughness_fit.md)
