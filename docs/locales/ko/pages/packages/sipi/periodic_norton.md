# 주기 전류원과 개방 단자

[주기 Norton 회로 저장](periodic_norton_circuit.md)으로 입력·시간 응답·전력을 재실행할 수 있습니다.

`periodic_norton_response`는 `LineNetwork`에 실수 전류원 파형과 유한 수동
병렬 어드미턴스를 적용합니다. [Norton 경계 솔버](norton_termination.md)와
기존 [주기 격자·파동 규칙](periodic.md)을 결합하며 개방 단자를 포함한 모든
포트 V/I를 원래 네트워크 basis로 보존합니다.

주파수는 정확히 실수인 DC S와 `f[k]=k*df`의 균일 고조파이며 최소 2개입니다.
F개 주파수에 실수 파형은 홀수 길이 `N=2*F-1`, 주기 `T=1/df`, 간격 `dt=T/N`을
갖습니다. 모든 양의 주파수 위상을 유지하며 Nyquist bin·보간·window·DC 추정·
인과성 보정을 추가하지 않습니다.

`source_currents`는 포트별 실수 DC 상수 또는 N개 전류 표본[A]입니다.
비어 있지 않은 사전이어야 하며 생략한 소스는 0입니다. 복소 시간 표본은 거부합니다.
`termination_admittances`는 유한 수동 복소 스칼라 또는 F개 어드미턴스 표본[S]이며
생략하면 `1/Zref`입니다. DC 어드미턴스는 정확히 실수여야 합니다.
`Y=0`은 이상 전류원이고 소스 파형까지 0이면 개방입니다. 무한 어드미턴스나
문자열 부하는 받지 않습니다. 소스·부하는 실제 네트워크 포트 basis에 속합니다.

```python
import numpy as np
from sipi import rlgc_network, periodic_norton_response

frequency = np.arange(5)*1e8
network = rlgc_network(frequency, R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
t = np.arange(9)/9
source = .0008+.0004*np.cos(2*np.pi*t)+.0001*np.sin(4*np.pi*t)
result = periodic_norton_response(network, source_currents={'near:1': source},
    termination_admittances={'near:1': .02, 'far:1': 0.})
assert np.max(abs(result.response.current[:, 1])) < 1e-12
assert np.max(abs(result.source_currents-result.response.current-result.termination_currents)) < 1e-12
```

## 고조파·전류·전력

실수 소스 표본을 DC 평균과 양의 주파수 **피크 페이저**로 변환합니다. 각 고조파에
기존 Norton 식 `I+YV=Is`와 조건수·잔차 기준을 적용합니다. 역합성으로 실수 파동,
V/I와 `Y(f)V(f)`에서 구한 병렬 전류를 반환합니다. 리액턴스 어드미턴스를 시간
표본에 그대로 곱하지 않습니다. 병렬 G+C의 전류는 지정 고조파에서 `G*V+C*dV/dt`입니다.

`PeriodicNortonResponse`는 다음을 보존합니다.

- `source_currents`: 실수 N×P 소스 표본[A].
- `termination_currents`: 실수 N×P 병렬 부하 전류[A].
- `response`: 기존 읽기 전용 `PeriodicResponse`의 시간·파동·V/I·기준값·포트·basis.
- `frequency_solution`: DC 평균·양의 피크 페이저·원래 어드미턴스·진단·주파수별
  전력을 가진 `NortonTerminatedNetwork`.

계산 배열은 모두 읽기 전용 스냅샷입니다. 각 시간에
`source_currents = response.current + termination_currents`를 만족합니다.
시간 평균 `sum(V*I)`는 고조파 네트워크 전력 합과 같고 소스·병렬 전력도 같습니다.
DC 가중치는 1, 양의 피크 페이저는 1/2입니다. 이 합산은 주기 격자에서 성립하며
일반 Norton 회로의 서로 무관한 주파수 표본을 같은 방식으로 합산하지 않습니다.

기존 Thevenin 주기 API는 전압원·직렬 부하 계약을 유지합니다. 외부 단자 거동이
같아도 Norton 내부 소스·병렬 전력은 Thevenin 소스·직렬 전력과 다른 토폴로지의 값입니다.

## 수락 기준과 한계

DC/AC 저항 전류 분배·이상 전류원·병렬 커패시터 시간 미분·DC를 포함한 개방
무손실 선로 해석식·도체/혼합 RLGC·직접 고조파 합성·중첩·순환 이동·시간/주파수
전력·스냅샷을 검사합니다. 명시한 합성 fixture에 절대/상대 `1e-12`를 적용합니다.

SciPy 1.18.1(BSD-3-Clause)의 해석적 RLC nodal 식과 scikit-rf 2.2.0
(BSD-3-Clause)의 S→Y nodal 회로는 API FFT와 별개인 명시적 유한 DFT·합성을
사용합니다. 최대 시간 V/I 차이는 `2.429e-17 V`/`5.693e-19 A`로 절대 `1e-12`
기준 이내입니다. 소스 형태·수동 Y·실수 DC·DC 누락/비균일 격자·부유 개방·수치
overflow를 거부합니다. 고조파 조건수 `1e12` 초과 또는 정규 잔차 `1e-10` 초과도
기존 기준대로 실패합니다.

이는 **주기 정상상태**이며 시작 과도응답이나 고립 펄스가 아닙니다. 순환 되감김,
표본 대역폭과 원래 네트워크·모델의 유효범위를 따릅니다. 인과성·안정성·실측 보드
정확도·새 전계 추출을 입증하지 않습니다. 저장 입력은 별도의
[periodic-norton-circuit/1](periodic_norton_circuit.md)을 사용합니다.
새 경로의 앱·Windows 수락도 별개입니다.

[Thevenin 주기 소스](periodic_termination.md) · [English](../../../../../packages/sipi/periodic_norton.md)
