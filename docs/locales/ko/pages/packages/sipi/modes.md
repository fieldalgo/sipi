# 서로 구분되는 전진 모드와 주파수 샘플 추적

`rlgc_modes`는 기존 [전체 행렬 특성 해](characteristic.md)에서 상반·수동 RLGC의
서로 구분되는 전진 모드를 구합니다. 모드마다 **시간 평균 전진 전력 1 W**로
정규화하고 도체·유전체 감쇠를 분리하며 입력 주파수 사이의 인덱스를 추적합니다.

```python
import numpy as np
from sipi import rlgc_modes

result = rlgc_modes(
    np.logspace(4, 9, 21),
    R=[[2, .2], [.2, 3]], L=np.array([[400, 60], [60, 300]])*1e-9,
    G=[[.002, -.0003], [-.0003, .003]], C=np.array([[100, -15], [-15, 80]])*1e-12,
    names=("first", "second"),
)
print(result.gamma[-1])
print(result.alpha_conductor[-1], result.alpha_dielectric[-1])
print(result.overlap.min())
voltage = result.voltage[-1, :, 0]  # conductor voltages for tracked mode zero
current = result.current[-1, :, 0]
assert abs(.5*np.vdot(voltage, current).real-1) < 1e-10
```

입력은 특성 API의 실수 대칭 PSD R/G·PD L/C와 양수 증가 주파수를 따릅니다.
SI·peak phasor·`exp(+jωt)` 규약입니다. `TransmissionLineResult.modes()`와
`VolumeLineResult.modes()`는 추출 RLGC를 재사용하며 장을 다시 풀지 않습니다.
기하·재료·선로 JSON은 바뀌지 않습니다.

## 배열·전력·해석

`LineModes`는 배열을 복사해 읽기 전용으로 만듭니다. `frequency`는 Hz,
`names`는 **도체 좌표 이름**이며 모드 이름이 아닙니다. 열 인덱스로 모드를 구분합니다.

| 배열 | 형상 | 의미 |
|---|---|---|
| `gamma` | (F,N) | 진폭 감쇠+j 위상 상수, 1/m |
| `voltage`, `current` | (F,N,N) | 도체 행·모드 열, 기준 단면의 V/A |
| `alpha_conductor`, `alpha_dielectric` | (F,N) | 단일 모드 진폭 감쇠 기여, Np/m |
| `overlap` | (F,N) | 배정된 인접 샘플 전력 overlap |
| `assignment_gap` | (F,) | 최선과 차선 배정의 총 점수 차이 |

각 열은 `Gamma_v V = gamma V`, `I = Yc V`,
`P = Re(V.conj().T @ I)/2 = 1 W`를 만족합니다. 단일 모드 항등식은 다음과 같습니다.

```text
alpha_conductor = Re(I^H R I)/(4 P)
alpha_dielectric = Re(V^H G V)/(4 P)
alpha_conductor + alpha_dielectric = Re(gamma)
```

진폭 Np/m에 `20/log(10)`을 곱하면 dB/m입니다. **같은 손실 전진 모드**에서
분리한 값이며, 도체만/유전체만 있는 별도 네트워크의 삽입 손실 차이가 아닙니다.
모드 사이 전력 직교가 보장되지 않아 중첩에는 간섭항이 있을 수 있습니다.
교차항이 사라진다고 가정하여 개별 전력을 단순 합산하지 마세요. 비대칭 모드에
유일한 스칼라 모드 임피던스나 차동/공통 이름을 부여하지 않습니다.
유한 종단·반사는 기존 네트워크/회로 API를 사용합니다.

## 인덱스 연속성과 거부 조건

첫 주파수에서는 허수 gamma, 다음 실수 gamma 오름차순입니다. 전압 최대 성분이
양의 실수가 되도록 초기 위상을 정합니다. 이후 `H=(Yc+Yc^H)/2`의 인접 평균으로
정규화한 절대 H 내적을 old/new 전압의 overlap으로 사용합니다. 일대일 최적
배정으로 총 점수를 최대화하고 배정된 복소 내적이 양의 실수가 되도록 위상을
맞춘 뒤 전력 정규화합니다. 고정 실수 전력 쌍대 도체 좌표 변환에 불변인 metric입니다.
첫 overlap/gap은 앞 샘플이 없으므로 1입니다.

반복·근접 근(최소 차이 `1e-8*max(abs(gamma))` 이하), 고유벡터 condition
`1e10` 초과, overlap 0.7 미만, 최선/차선 총 점수 차이 `1e-6` 이하는
`index`·`frequency`를 담은 `ModeTrackingError`입니다. 배정이 불명확하면
주파수 격자를 세분하세요. 축퇴를 지나며 임의 인덱스를 성공으로 반환하지 않습니다.
축퇴에서는 전체 행렬 특성 API를 사용할 수 있고 기존 branch/condition 조건도 유지됩니다.

모드 방정식·전력 균형 잔차는 전체 방정식/전파 스케일 대비 `1e-10`으로 검사합니다.
표현 불가능 정규화나 계산된 음수 손실을 clipping 없이 거부합니다. 입력 PSD가
반올림 허용 범위 안에 있어도 이 더 엄격한 선택적 모드 계산은 거부할 수 있습니다.
1 W 전력 오차는 `1e-10` 미만이어야 합니다.

추적은 **입력한 샘플**에 대한 것입니다. 샘플 사이 유일한 물리 모드 정체성,
모든 미샘플 교차 탐지, 축퇴 부분공간 추적, 재료 적합·메시 정확도·시간영역 진화를
보장하지 않습니다. 교차 뒤 모드 순서는 위상 속도 순서와 달라질 수 있습니다.

## 독립 검증

Scikit-rf 2.2.0의 스칼라 `DistributedCircuit` 모드를 알려진 실수 비직교 행렬로
비대칭 3도체 선로로 변환합니다. 손실/무손실 gamma·모드 전력/손실 분리·복원 전진
전달이 `1e-10` 이내로 일치합니다. 별도 전체 block telegrapher 지수로 가환하지 않는
RLGC를 확인합니다. 샘플 사이 교차, 축퇴·모호/낮은 overlap 회전 거부, 더 고운
주파수의 성공, 위상 연속, 전력 쌍대 좌표 변환, 정확한 무손실 기여를 검사합니다.
실제 비대칭 tensor 유전체의 공유 메시·유한 금속 결과에서 추가 장 계산이 없음을
확인합니다. 대수·어댑터 검증이며 새 물리 기하나 실측 검증은 아닙니다.
런타임 의존성은 추가하지 않습니다.

[English](../../../../../packages/sipi/modes.md)
