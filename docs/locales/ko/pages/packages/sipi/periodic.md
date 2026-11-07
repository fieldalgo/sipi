# 표본 네트워크의 주기 응답

`periodic_response(network, incident)`는 `LineNetwork`에 한 주기의 실수 입사
전력파를 적용합니다. `periodic_impulse(network)`는 같은 이산 원형 컨볼루션
가중치를 반환합니다. 기존 RLGC·회로·측정 네트워크도 아래 조건을 만족해야 합니다.

## 주파수·시간 계약

- `F >= 2`개 표본이 **정확히 0 Hz**부터 시작하고 `f[k] = k*df`,
  `df = f[1] > 0`이어야 합니다. 최대 격자 오차는 `1e-12*f[-1]` 이하입니다.
  반올림 오차만 허용하며 표본을 보간하지 않습니다.
- DC S 행렬의 허수부는 모두 정확히 0이어야 합니다. DC 누락·불균일 간격·복소 DC는
  오류입니다. DC 추정·외삽·창 함수·패딩·평활화·수동성/인과성 보정을 하지 않습니다.
- 시간 표본 수는 **홀수** `N = 2*F-1`, 주기는 `T = 1/df`, 간격은 `dt = T/N`입니다.
  Nyquist bin이 없으므로 최고 양수 주파수의 위상을 보존합니다.
  시각은 `0, dt, ..., (N-1)*dt`이며 끝점을 반복하지 않습니다.
  주기·격자·스펙트럼·결과의 숫자 표현이 불가능하면 `ValueError`를 냅니다.
- `incident`는 `(N, ports)` 모양의 유한 실수이고 bool은 허용하지 않습니다.
  푸리에 성분은 `b[k] = S[k] @ a[k]`를 따릅니다. 원래 포트 순서·기저와
  주파수에 무관한 양의 실수 기준 임피던스를 보존하며 비상반 행렬을 전치하지 않습니다.

결과의 배열은 읽기 전용입니다. `incident`, `reflected` [sqrt(W)], `voltage` [V],
`current` [A], `time` [s], `z_ref` [ohm]와 `period`, `dt`, `port_names`, `basis`를
제공합니다. 각 시각·포트에서 다음을 만족합니다.

```
V = sqrt(Zref) * (a + b)
I = (a - b) / sqrt(Zref)
V*I = a*a - b*b
```

전류는 **네트워크 안쪽**이 양수입니다. 실수 시간 표본이므로 페이저/RMS의 1/2 계수를
붙이지 않습니다. 혼합 모드는 실제 모드 기준값을 사용합니다. 예를 들어 단일 종단
50 ohm 선로 쌍의 차동 기준은 100 ohm, 공통 기준은 25 ohm입니다.

## 정합 선로의 주기 지연 예제

```python
import numpy as np
from sipi import rlgc_network, periodic_response, periodic_impulse

frequency = np.arange(9)*1e8
count = 2*len(frequency)-1
dt = (1/frequency[1])/count
velocity = 2e8
network = rlgc_network(frequency, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=velocity*2*dt, z_ref=50.)
incident = np.zeros((count, 2))
incident[:, 0] = np.cos(2*np.pi*np.arange(count)/count)
response = periodic_response(network, incident)
np.testing.assert_allclose(response.reflected[:, 1],
    np.roll(incident[:, 0], 2), atol=1e-12, rtol=0)
impulse = periodic_impulse(network)
assert impulse.weights.shape == (count, 2, 2)
assert response.port_names == network.port_names
```

## 이산 임펄스와 한계

`PeriodicImpulse.weights[lag, output_port, input_port]`는 무차원 가중치입니다.
중앙 정렬한 지연은 `-(F-1)*dt`부터 `+(F-1)*dt`까지입니다.
`np.fft.ifftshift(weights, axes=0)`로 풀면 원형 컨볼루션의 지연 `0..N-1` 순서가 됩니다.
모든 지연의 합은 수치 오차 안에서 DC S 행렬과 같습니다. 이산 표본에 곱하는 값이며
연속 Dirac 밀도가 아니므로 이산 컨볼루션에 `dt`를 추가로 곱하지 않습니다.

음의 지연은 한 주기 안에서 감긴 위치입니다. 유한 대역의 주기 정상상태 응답이며
시작 과도응답·고립 펄스 응답·TDR 임피던스·인과성/안정성/재료 정확도의 증명이 아닙니다.
최고 주파수를 늘리면 시간 해상도가 바뀌고 `df`를 바꾸면 주기와 감김이 바뀝니다.
주어진 S만으로 누락 조화파나 표본 사이의 거동을 알 수 없습니다. 짧은 주기와 앨리어싱은
긴 지연을 숨길 수 있습니다. 자동 감김 해제나 물리 오차 추정을 제공하지 않습니다.
사용자가 만든 능동 S의 이득이 1보다 크다는 이유만으로 거부하지 않으며, 그렇다고
안정성을 인증하지도 않습니다. 적절한 원래 모델을 사용해야 합니다.

## 검증 범위

FFT를 사용하지 않는 유한 DFT 합으로 비상반 다중 포트와 최고 양수 주파수 위상을
절대 `1e-12`에 비교합니다. 일정 반사·정수 표본 지연/감김·중첩·시간 이동·실수 전력
항등식·수동 표본 네트워크의 에너지를 확인합니다. RC의 알려진 조화해를 두 주기·두
해상도에서 `1e-12`에 비교하며, 이는 표현한 조화해의 검증이지 임의 과도응답의 수렴은
아닙니다. 기존 RLGC 엔진의 무손실 지연과 혼합 모드 정규화도 확인합니다.
변환 자체가 새로운 기하 추출이나 메시 수렴 근거를 추가하지는 않습니다.

scikit-rf 2.2.0(BSD-3-Clause)의 창 없는 홀수 길이 lowpass 임펄스와 비교합니다.
이 도구는 NumPy FFT를 공유하므로 별도의 직접 유한합 기준이 필요합니다.
SciPy 1.18.1(BSD-3-Clause)의 직접 컨볼루션을 원형으로 접은 값도 절대 `1e-12`에
비교합니다. 실측 검증은 아니며 엄격한 입력·숫자 범위 오류를 별도로 검사합니다.
이번 Python API는 저장 JSON 스키마나 앱 지원 범위를 바꾸지 않습니다.
[네트워크](network.md) · [English](../../../../../packages/sipi/periodic.md)
