# 주기 전압원·전류원 혼합 응답

`periodic_mixed_response(network, boundaries)`는 실수 전원 파형을
[혼합 종단](mixed_termination.md)에 연결합니다. 이상 전압원·단락과 이상 전류원·
개방을 함께 사용할 수 있습니다. 모든 실제 basis 포트가 Thevenin(`kind`,
`source_voltage`, `impedance`) 또는 Norton(`kind`, `source_current`,
`admittance`) 필드를 명시하며 전원·부하를 추론하지 않습니다.

전원은 유한 실수 DC 상수 또는 N개 실수 시간 표본이며 종류에 따라 V/A입니다.
부하는 유한 수동 복소 스칼라 또는 F개 주파수 표본[ohm/S]이며 DC 허수부는
정확히 0입니다. Z=0·Y=0의 이상 경계 의미를 유지합니다. 복소 시간 표본·불리언·
잘못된 모양·미지/누락 필드·음의 실수부 부하는 거부합니다.

[주기 격자 계약](periodic.md)은 정확히 실수인 DC S부터 균일 고조파 F≥2,
홀수 N=2F−1, 주기 1/df, dt=1/(N·df)를 요구합니다. Nyquist 빈·보간·창 함수·
누락 DC 추정·인과성 보정을 추가하지 않습니다. 기존 단일 종류 주기 API는 그대로입니다.

```python
import numpy as np
from sipi import rlgc_network, periodic_mixed_response

network = rlgc_network(np.arange(5)*1e8, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
t = np.arange(9)/9
drive = .3+.2*np.cos(2*np.pi*t)+.1*np.sin(4*np.pi*t)
result = periodic_mixed_response(network, {
    'near:1': dict(kind='thevenin', source_voltage=drive, impedance=0.),
    'far:1': dict(kind='norton', source_current=0., admittance=0.)})
np.testing.assert_allclose(result.response.voltage[:, 0], drive, atol=1e-12, rtol=0)
np.testing.assert_allclose(result.response.current[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(result.response.voltage*result.response.current, axis=1)),
    result.frequency_solution.network_power.sum(), atol=1e-12, rtol=0)
```

## 고조파·부하 응답·전력

실수 전원을 DC 평균과 양의 주파수 첨두 페이저로 변환합니다. 혼합 종단의
조건수·포트별 경계 잔차·파형 잔차 기준을 각 고조파에 적용하고, 전체 입사/반사
파형·V/I·직렬 전압강하 Z(f)I(f)·병렬 전류 Y(f)V(f)를 역합성합니다.
주파수 부하를 시간 표본에 점별로 곱하지 않습니다. 직렬 R+L은 RI+L·dI/dt,
병렬 G+C는 GV+C·dV/dt입니다.

`PeriodicMixedResponse`는 다음 읽기 전용 스냅샷을 보존합니다.

- `source_voltages`, `termination_voltages`: Thevenin 포트의 N×P 실수 V;
- `source_currents`, `termination_currents`: Norton 포트의 N×P 실수 A;
- `response`: 시간·주기·dt·파형·V/I·메타데이터를 포함한 `PeriodicResponse`;
- `frequency_solution`: 포트 순서의 종류·원부하·첨두 고조파·진단·전력을 포함한
  전체 `MixedTerminatedNetwork`.

네 전원·부하 배열에서 사용하지 않는 종류의 열은 0입니다. Thevenin 포트는
Vs=V+drop, Norton 포트는 Is=I+shunt를 만족합니다. 시간 평균 전력은 다음과 같습니다.

- 네트워크: mean Σ(V·I);
- 부하: mean Σ(drop·I+V·shunt);
- 전원: mean Σ(Vs·I+V·Is).

각 값은 대응 고조파 전력 합과 일치합니다(DC 가중치 1, 양의 첨두 페이저 1/2).
이는 명시 주기 격자에서의 합이며 일반 혼합 회로의 독립 주파수 전력 의미를
바꾸지 않습니다. 내부 전력은 선택한 전원 구조를 따릅니다.

## 검증 범위

DC를 포함한 이상 전압원·개방 선로 해석 페이저, 리액티브 부하 시간 미분,
모든 포트가 Thevenin/Norton인 경우 기존 주기 API와의 일치, 실제 결합 RLGC의
도체/혼합 basis, 직접 유한 합성·중첩·순환 이동·영 구동·스냅샷·시간/고조파
전력을 검증합니다. 모양·부하·격자·DC·부유 단자·overflow 제한도 유지합니다.

SciPy 1.18.1(BSD-3-Clause) 해석 RLC 절점식과 scikit-rf 2.2.0(BSD-3-Clause)
S→Y 절점식으로 고정 전압/자유 전류 2포트를 독립 계산하고 명시적 유한 DFT·합성을
적용했습니다. 최대 시간 V/I 차이는 3.886e−16 V / 1.388e−17 A로 절대 1e−12
기준 이내입니다. 조건수 1e12 초과·정규 잔차 1e−10 초과는 계속 오류입니다.

표본화된 주기 정상 상태이며 스위칭 시작 과도나 고립 펄스가 아닙니다. 순환 감김·
유한 대역·원 네트워크 모델 한계를 유지합니다. 인과성·안정성·새 전계·실측 정확도를
주장하지 않습니다. 저장 스키마는 45종 그대로이며 앱·Windows 수락을 추가하지 않습니다.

[Thevenin 파형](periodic_termination.md) · [Norton 파형](periodic_norton.md) · [English](../../../../../packages/sipi/periodic_mixed.md)
