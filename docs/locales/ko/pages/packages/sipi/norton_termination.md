# 전류원과 개방 단자 경계

[혼합 종단](mixed_termination.md)은 이상 전압원·단락과 개방·전류원 포트를 한 번에 풉니다.

[Norton 회로 저장](norton_circuit.md)은 별도 버전 입력과 공통 실행 계약을 제공합니다.

`terminate_norton_network`는 `LineNetwork`에 명시한 Norton 전류원을 적용하고
개방을 포함한 **모든 포트**의 전압·전류를 보존합니다. 원래 포트 이름·순서·basis와
양의 실수 기준 임피던스를 사용하며 소스 위치·피해 포트·토폴로지를 추론하지 않습니다.

단자 경계는 `I + Y*V = Is`입니다. I는 **네트워크 안으로** 들어가는 전류,
Is는 전류원 전류[A], Y는 병렬 소스/부하 어드미턴스[S], V는 단자 전압[V]입니다.
입력은 유한 복소 스칼라 또는 주파수별 배열입니다. `source_currents`는 비어 있지
않은 사전이어야 하며 생략한 소스는 0입니다. `termination_admittances`에서 생략한
포트는 `1/Zref`입니다. 각 주파수에서 `Re(Y)>=0`인 수동 부하만 받습니다.

- `Y=0, Is=0`: 개방 단자이며 전압도 보존합니다.
- `Y=0, Is!=0`: 이상적인 전류원입니다.
- 유한한 비영 Y: 외부 단자에서 Thevenin `Vs=Is/Y, Zt=1/Y`와 등가입니다.
- 단락·이상 전압원은 기존 [Thevenin API](termination.md)의 직렬 임피던스 0을
  사용합니다. 무한 어드미턴스는 받지 않습니다.

개방을 큰 임피던스로 대체하지 않습니다. 계산된 파동에서 전류를 구하고 회로 잔차로
검사하며 0으로 잘라내지 않습니다. 리액턴스에 해당하는 어드미턴스 표본은 허용하지만
표본별 수동성만으로 네트워크·부하 모델의 인과성이나 안정성을 인증하지 않습니다.

```python
import numpy as np
from sipi import rlgc_network, terminate_norton_network

network = rlgc_network([1e8, 2e8, 5e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length=.1)
result = terminate_norton_network(network,
    source_currents={'near:1': .002},
    termination_admittances={'near:1': .02, 'far:1': 0.})
assert result.port_names == ('near:1', 'far:1')
assert np.max(abs(result.current[:, 1])) < 1e-12
assert np.max(abs(result.source_power-result.network_power-result.termination_power)) < 1e-12
```

## 결과와 전력 계약

`NortonTerminatedNetwork`는 네트워크 스냅샷과 읽기 전용 `source_currents`,
`termination_admittances`, `a`, `b`, `voltage`, `current` 배열을 보존합니다.
크기는 `(주파수,포트)`입니다. 조건수·KCL 잔차·파동 잔차와 전력은 주파수마다
하나의 값을 갖습니다. 전력 속성의 단위는 W이고 역시 읽기 전용입니다.

| 속성 | 주파수 가중치 적용 전 포트 합 |
|---|---|
| `network_power` | `Re(V*conj(I))` |
| `termination_power` | `Re(V*conj(Y*V))`, 병렬 부하 소비전력 |
| `source_power` | `Re(V*conj(Is))`, 이상 전류원 공급전력 |

DC 가중치는 1, 양의 주파수 **피크 페이저**는 1/2입니다.
`source_power = network_power + termination_power`를 만족합니다.
입력 S가 능동이면 네트워크 전력이 음수일 수 있으며 API가 수동성을 인증하지 않습니다.

등가 소스 변환은 외부 V/I·파동·네트워크 전력을 보존합니다. 내부 이상 소스 전력과
직렬/병렬 저항의 소비전력까지 보존하지는 않습니다. Thevenin과 Norton의 내부
전력 속성은 각각의 회로에서 해석해야 하며 각자 전력 보존식을 만족합니다.

풀이식은 `a=gamma*b+drive`, `gamma=(1-Y*Zref)/(1+Y*Zref)`,
`drive=Is*sqrt(Zref)/(1+Y*Zref)`입니다. 특이·부유 경계, 조건수 `1e12` 초과,
정규화 KCL/파동 잔차 `1e-10` 초과를 거부합니다. 서로 모순되는 이상 소스 조건을
임의 보정하지 않습니다. 유한 입력이라도 중간값·결과·요청 전력이 부동소수점 범위를
벗어나면 거부합니다. 소스가 모두 0이어도 경계 해의 유일성이 필요합니다.

## 검증 범위

RC 전류 분배·이상 전류원·끝이 열린 무손실 선로(`Zin=-j Z0 cot(beta*l)`),
중첩, DC/양의 주파수 전력 가중치와 외부 Thevenin 등가성을 해석식으로 검사합니다.
실제 결합 RLGC 네트워크의 도체·혼합 좌표와 기준 임피던스 변경에서도 V/I를
보존합니다. 명시한 합성 fixture에 맞춰 절대/상대 `1e-12` 기준을 사용합니다.

SciPy 1.18.1(BSD-3-Clause)의 독립 nodal 풀이에는 RLC pi 회로의 해석적 Y를,
scikit-rf 2.2.0(BSD-3-Clause)에는 별도의 S→Y 변환을 사용합니다. 최대 차이는
`3.470e-17 V`/`1.698e-18 A` 미만으로 절대 `1e-12` 기준 이내입니다.
잘못된 입력·특이/부유/나쁜 조건수·수치 및 전력 overflow·스냅샷 불변성도 검사합니다.

새 메시나 전계 추출 모델을 추가하지 않는 회로 대수 API입니다. API 자체가 저장 계약·시간 적분·실측 정확도·앱/플랫폼 수락을 뜻하지 않습니다.
기존 유한 Thevenin 입력과 별도 포트 축소 API를 유지합니다.

[네트워크](network.md) · [English](../../../../../packages/sipi/norton_termination.md)
