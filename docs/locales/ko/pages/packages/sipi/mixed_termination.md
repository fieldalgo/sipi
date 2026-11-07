# 전압원·전류원 혼합 종단

`terminate_mixed_network(network, boundaries)`는 각 포트에서 Thevenin 또는
Norton 경계를 독립적으로 선택합니다. 따라서 이상 전압원·단락과 개방·이상
전류원을 같은 네트워크에서 사용할 수 있습니다. 기존 [Thevenin](termination.md)·
[Norton](norton_termination.md) API의 계약과 기본값은 유지합니다.

`boundaries`는 네트워크의 실제 basis에 있는 모든 포트를 명시합니다. 각 항목은
아래 형태 중 하나이며, 값은 유한 복소 스칼라 또는 F개 주파수 표본입니다.

| kind | 전원 | 수동 부하 | 단자 관계 |
|---|---|---|---|
| `thevenin` | `source_voltage` [V] | `impedance` [ohm], Re Z≥0 | V+ZI=Vs |
| `norton` | `source_current` [A] | `admittance` [S], Re Y≥0 | I+YV=Is |

Z=0은 이상 전압원이며 Vs=0이면 단락입니다. Y=0은 이상 전류원이며 Is=0이면
개방입니다. 포트를 생략해 기본값을 넣거나 무한대·큰 부하로 근사하지 않습니다.
미지 필드·포트, 누락 필드, 불리언, 음의 실수부 부하, 잘못된 배열 모양을
거부합니다. 포트 기하나 전원 위치를 추론하지 않고 원래 주파수 순서를 따릅니다.

```python
import numpy as np
from sipi import rlgc_network, terminate_mixed_network

f = np.array([0., 1e8, 2e8])
network = rlgc_network(f, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
result = terminate_mixed_network(network, {
    'near:1': dict(kind='thevenin', source_voltage=1., impedance=0.),
    'far:1': dict(kind='norton', source_current=0., admittance=0.)})
theta = 2*np.pi*f*.1*5e-9
np.testing.assert_allclose(result.voltage[:, 0], 1., atol=1e-12, rtol=0)
np.testing.assert_allclose(result.voltage[:, 1], 1/np.cos(theta), atol=1e-12, rtol=0)
np.testing.assert_allclose(result.current[:, 1], 0., atol=1e-12, rtol=0)
```

## 피드백·잔차·보존 데이터

양의 실수 기준 임피던스 Zr에서 `a=Gamma*b+drive`, `b=S*a`를 풉니다.

- Thevenin: `Gamma=(Z-Zr)/(Z+Zr)`, `drive=Vs*sqrt(Zr)/(Z+Zr)`;
- Norton: `Gamma=(1-Y*Zr)/(1+Y*Zr)`, `drive=Is*sqrt(Zr)/(1+Y*Zr)`.

구현은 동등한 비율 표현을 사용하며 비유한 중간값·결과와 1e12 초과 조건수를
거부합니다. 정규 경계·파형 잔차는 각각 1e−10 이하여야 합니다. 부유 회로나
서로 모순되는 이상 경계는 전원이 0이어도 오류입니다.

KVL[V]과 KCL[A]은 포트별로 정규화하며 서로 다른 단위를 한 노름에 섞지
않습니다. 분모는 전원·주항·부하항·입사/반사 기여의 최댓값이며 float-tiny를
하한으로 사용합니다. 파형 기여는 KVL에서 `sqrt(Zr)*a,b`, KCL에서 `a,b/sqrt(Zr)`입니다.
상쇄 전 기여를 포함하여 개방 단자의 반올림 전류를 그 전류 자체로 나누지 않습니다.
이는 후방오차 기준이며 독립 기준과의 절대 V/I 일치 검증은 별도입니다.

`MixedTerminatedNetwork`는 원본 `network`, 포트 순서의 `kinds`,
`source_voltages`[V], `series_impedances`[ohm], `source_currents`[A],
`shunt_admittances`[S], `a,b`[sqrt(W)], `voltage`[V], 유입 `current`[A],
`condition_number`[F], `boundary_residual`[F,P], `wave_residual`[F]를 보존합니다.
사용하지 않는 전원·부하 열은 0입니다. 계산 배열은 읽기 전용이며 기준 임피던스,
포트 이름, 주파수, basis도 확인할 수 있습니다.

## 전력과 검증 범위

주파수별 `network_power`, `termination_power`, `source_power`의 단위는 W입니다.
DC 가중치는 1, 양의 주파수 첨두 페이저는 1/2입니다. 전원 전력은 Thevenin에서
Vs·conj(I), Norton에서 V·conj(Is)를 사용합니다. 부하 전력은 각각 ZI·conj(I),
V·conj(YV)입니다. 검증한 회로에서 실수 전원 전력은 네트워크와 부하 전력의 합과
일치합니다. 비유한 곱·합은 예외이며 독립 주파수 전력을 시간 평균으로 합산하지 않습니다.

유한 Thevenin/Norton 등가회로의 외부 V/I·파형·네트워크 전력은 일치하지만,
내부 전원·부하 전력은 회로 구조가 달라 같을 필요가 없습니다. 모든 포트가 한
종류인 경우에는 기존 API의 내부 전력도 일치합니다.

DC를 포함한 이상 전압원·개방 무손실 선로, 단락한 저항 브리지, 실제 결합 RLGC의
도체/혼합 basis, 기준 임피던스 변환, 중첩·스냅샷·엄격 입력·조건수·overflow를
검증합니다. SciPy 1.18.1(BSD-3-Clause)의 해석 RLC 절점식과
scikit-rf 2.2.0(BSD-3-Clause)의 S→Y 절점식으로 고정 전압 절점과
개방/전류원/병렬 부하 절점을 독립 계산했습니다. 최대 V/I 차이는
2.289e−16 V / 2.454e−17 A로 절대 기준 1e−12 이내입니다.

저장 입력은 [mixed-circuit/1](mixed_circuit.md)을 사용합니다. 이 API는 시간 변환을 추가하지 않습니다.
새 전계·실측 정확도, 입력 네트워크 수동성·인과성·시작 과도, 앱·Windows 수락을
입증하지 않습니다.

[English](../../../../../packages/sipi/mixed_termination.md)
