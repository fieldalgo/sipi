# 주기 Thevenin 소스와 유한 종단

[저장 회로와 공통 실행](periodic_circuit.md)에서 소스·부하·진단을 함께 보존합니다.

`periodic_terminated_response`는 실수 주기 소스 전압과 유한 소스/부하 임피던스를
함께 풉니다. 기존 `terminate_network`의 조화파 피드백 풀이와 [주기 격자 계약](periodic.md)을
사용합니다. Thevenin 전압은 반사파·소스 임피던스와 독립적으로 입사파를 지정하는 값이
아니므로 이 둘을 구분합니다.

## 입력과 정규화

- `network`: DC S가 정확히 실수이고 0 Hz에서 시작하는 균일 주파수 `LineNetwork`입니다.
  주파수 F>=2개에 시간 표본은 `N = 2*F-1`개입니다. 같은 `1e-12*f[-1]` 격자 오차와
  표현 가능한 주기 조건을 적용합니다.
- `source_voltages`: 실제 포트 이름에서 실수 상수 또는 길이 N의 실수 배열로 가는
  비어 있지 않은 객체입니다. 단위는 V, 상수는 주기 전체의 DC 소스이며 빠진 포트의
  소스 전압은 0입니다. bool·비유한/복소 시간 값·알 수 없는 포트는 거부합니다.
- `terminations`: 실제 포트 이름별 유한 수동 임피던스[ohm]입니다. 복소 상수 또는
  길이 F의 복소 주파수 표본이며 모든 실수부가 0 이상이고 **DC는 정확히 실수**여야
  합니다. 빠진 값은 각 포트의 실수 기준 임피던스입니다. 0은 허용하지만 무한대/open은
  지원하지 않습니다. 개방 경계가 필요하면 명시 네트워크 모델이나 포트 축약을 사용합니다.

각 임피던스는 해당 포트의 직렬 소스/부하 임피던스입니다. 전류는 네트워크 안쪽이
양수이므로 `Vs = V + Vdrop`입니다. 혼합 모드 입력은 실제 모드 포트와 기준값에
적용하며 물리 단일 종단 소스 회로를 자동으로 추론하지 않습니다.

소스에 `rfft(..., norm='forward')`를 적용한 뒤 **양수 주파수 성분만** 2배로 만듭니다.
이로써 기존 회로 규약의 DC 평균값과 양수 주파수 **peak 페이저**를 얻습니다.
역변환할 때 양수 페이저만 절반으로 줄이고 홀수 N을 사용합니다. Nyquist bin이 없고
DC 계수는 바꾸지 않습니다. DC 전력에는 1/2가 없고 양수 주파수 peak 전력에는 있습니다.

## DC와 AC 전압 분배기 예제

```python
import numpy as np
from sipi import LineNetwork, periodic_terminated_response

frequency = np.arange(5)*1e6
count = 2*len(frequency)-1
source = .2+np.cos(2*np.pi*np.arange(count)/count)
# A 100-ohm one-port at a 50-ohm wave reference.
network = LineNetwork(frequency, np.full((5, 1, 1), 1/3), 50., ('port',))
result = periodic_terminated_response(network,
    source_voltages={'port': source}, terminations={'port': 50.})
np.testing.assert_allclose(result.response.voltage[:, 0], source*2/3,
                           atol=1e-12, rtol=0)
mean_power = np.mean(result.response.voltage*result.response.current)
np.testing.assert_allclose(mean_power,
    result.frequency_solution.network_power.sum(), atol=1e-12, rtol=0)
```

## 결과와 검증 한계

`PeriodicTerminatedResponse`는 다음을 보존합니다.

- `source_voltages`, `termination_voltages`: 시간 × 포트 순서의 읽기 전용 실수 V 배열.
  주파수 의존 Z의 직렬 강하는 `Z[k]*I[k]`를 역변환한 값이며 주파수 표와 시간 파형을
  같은 인덱스로 곱한 값이 아닙니다.
- `response`: 읽기 전용 `PeriodicResponse` 시간 격자, 실수 입사/반사 전력파[sqrt(W)],
  V/I, 기준값, 이름과 기저.
- `frequency_solution`: DC/peak 소스와 해의 페이저, 실제 임피던스 표, 조건수,
  정규 KVL/파 잔차를 포함하는 원래 `TerminatedNetwork`. 전력 속성은 주파수별 평균이므로
  시간 평균 소스/네트워크/종단 전력과 비교할 때 주파수별 값을 **합산**해야 하며
  주파수 개수로 평균 내지 않습니다.

기존 조건수 `1e12`와 정규 잔차 `1e-10` 기준을 유지합니다. 특이 피드백·복소 DC·
숫자 범위 오류는 예외로 전달하며 일부 주파수만 성공한 결과를 내지 않습니다.
구동이 모두 0이어도 회로가 정의되지 않으면 거부합니다. 원본 네트워크/소스와
결과 배열은 호출자 배열을 바꾸지 않고 보존합니다.

DC와 DC+AC 분배기·정합 선로 지연·이상적인 0 소스 임피던스·0 구동·결합 RLGC의
단일/혼합 기저·중첩·시간 이동을 검사합니다. RL 종단에서 표현한 조화해의
`Vdrop = R*I + L*dI/dt`를 확인합니다. 시간 KVL, `V*I = a*a-b*b`, 시간/조화파
평균 전력 수지는 절대 `1e-12`에 일치합니다. 직접 유한 조화합, SciPy 1.18.1
(BSD-3-Clause) V/I 블록 회로, scikit-rf 2.2.0(BSD-3-Clause) 임피던스 회로로
불균등 기준값·복소 RL 부하의 비상반 다중 포트를 `1e-12` V/A에 비교합니다.
필드 추출 정확도의 검증은 아닙니다.

표본 주기 정상상태 기능입니다. 실수 DC와 수동 임피던스 표본만으로 광대역 부하의
인과성/안정성을 입증할 수 없습니다. 누락 주파수 추론·고립 시작 과도응답·TDR/eye/BER·
자동 누화 peak 정의나 새 실측/재료/기하 정확도를 주장하지 않습니다.
JSON·앱 지원은 별도이며 이번 단위는 Python API입니다.

[주기 저장 입력](periodic_document.md) · [English](../../../../../packages/sipi/periodic_termination.md)
