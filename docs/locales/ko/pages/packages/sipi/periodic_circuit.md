# 주기 소스·부하 회로 저장

`sipi.periodic-circuit/1`은 [유한 종단 주기 응답](periodic_termination.md)의 Thevenin
전압과 임피던스를 **최종 기저의 모든 포트**에 명시해 저장합니다.
`sipi.periodic_circuit`의 `PeriodicCircuitDocument`를 사용합니다. 입사파를 지정하는
[periodic-network/1](periodic_document.md)과 구별합니다.

정규 객체의 필드는 `schema`, `network`, `basis`, `source_voltages`, `terminations`
뿐입니다. 생성자는 기저만 `single-ended`를 기본으로 쓰고 저장 JSON에는 모든 필드를
명시합니다. 소스나 부하를 추론하지 않습니다.

- `network`는 주기 네트워크 계약의 기존 자체 완결 원본 7종입니다. 무필드 정규화·
  실수 DC·균일 주파수·홀수 N·메타데이터·혼합 모드 제한을 그대로 적용합니다.
- 두 표는 최종 기저의 모든 포트를 빠짐/추가 없이 한 번씩 명시합니다.
  객체 삽입 순서로 포트 순서를 정하지 않습니다.
- `source_voltages` 값은 유한 실수 상수 V(DC) 또는 N개의 실수 시간 표본입니다.
  구동하지 않는 포트도 0으로 명시하며 복소 시간 표본은 거부합니다.
- `terminations` 값은 실수 또는 `{real, imag}` 객체입니다. 각 성분은 상수 또는
  F개 주파수 배열이고 두 성분의 모양이 같아야 합니다. 정규 값은 항상 `{real, imag}`입니다.
  단위는 ohm, 유한하며 실수부가 음수가 아니고 DC 허수부는 정확히 0이어야 합니다.
  bool·음의 저항·무한대·`open` 문자열은 거부합니다. 0 임피던스는 기존 조건수 기준
  안에서 지원합니다.

명시 기저의 직렬 소스/부하 임피던스입니다. 주파수 의존 부하는 주기 조화파 피드백을
표현하며, 수동 표본과 실수 DC만으로 광대역 인과성/안정성을 인증하지 않습니다.

```python
import json
import numpy as np
from sipi import LumpedNetworkDocument
from sipi.periodic_circuit import PeriodicCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = LumpedNetworkDocument([0., 1e8, 2e8], resistance=10., inductance=2e-9)
request = PeriodicCircuitDocument(
    dict(kind='lumped-network', document=source.to_dict()),
    source_voltages={'near': [0., 1., .5, -.5, -1.], 'far': 0.},
    terminations={'near': 50., 'far': 75.})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
assert out['status'] == 'complete'
result = out['result']
assert result['harmonics']['convention'] == 'dc-mean-positive-peak'
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
json.dumps(out, allow_nan=False)
```

## 예산·보존 결과·실패

`analyze`와 공통 실행은 N개 시간 표본을 `max_evaluations`(기본 128, 정수 2..10000)와
비교한 뒤 필드/FFT를 수행합니다. 파싱에서 기존의 작은 원본 대수 계산은 가능합니다.
입력 바이트·포트 수·필드 시간·포트 수 제곱에 비례하는 출력 크기는 호출자가 별도로
제한해야 합니다. 격자를 자동으로 줄이지 않습니다.

기존 원본 규칙에 따라 각 기하 항목을 한 번 추출합니다. 공통 helper가 주파수·포트·
기준값·기저 일치를 확인한 뒤 혼합 모드로 바꿉니다. Python 결과는 정규 `input_json`,
`source_network`, 최종 `network`, `extraction`, `solution`을 보존합니다.
마지막 값은 원래 조화파 회로 진단을 가진 `PeriodicTerminatedResponse`입니다.

공통 유한 JSON은 정규 입력과 다음 결과를 보존합니다.

- `coverage='sampled-periodic-steady-state'`, 최종 `network`, `source_network`;
- `response`: periodic-network/1과 같은 시간 격자·실수 전력파·V/I;
- `source_voltage_v`, `termination_voltage_v`: 시간 × 포트 실수 배열;
- `harmonics`: `convention='dc-mean-positive-peak'`, 복소 `source_voltage_v`,
  `termination_ohms`, `incident_sqrt_w`, `reflected_sqrt_w`, `voltage_v`, `current_a`;
  실수 `condition_number`, `kvl_residual`, `wave_residual`;
  `network`, `terminations`, `sources` 배열을 가진 `frequency_power_w`;
- `mean_power_w`: 해당 주파수 전력 배열을 **합산**한 W 값.

조화파는 네트워크의 주파수 순서·최종 포트 기저를 따르며 복소 출력은 `{real, imag}`입니다.
DC는 평균, 양수 조화파는 RMS가 아닌 peak 페이저입니다. 시간 전력은 안쪽 전류로 V*I를
계산합니다. 동적 임피던스의 시간 강하는 ZI의 역변환이지 표의 같은 인덱스끼리 곱한 값이
아닙니다. 중첩 필드 객체는 공통 직렬화 대신 Python에서 제공합니다.

원본·메타데이터·DC·조건수·숫자 범위 오류는 그대로 전달합니다. 직렬화는 비유한 조화파
전력이나 전력 합도 거부하며 부분 결과를 내지 않습니다. `complete`는 계산 완료이고
물리/인과성 인증이 아닙니다.

모든 원본 파서의 무필드 검사, 대수 원본의 직접/API/JSON 정확 재생, 실제 PEC 단일/쌍
혼합 응답의 `1e-12` 비교, 추출 횟수·필드 전 예산·메타데이터 변조·엄격한 표·전력 넘침을
검증합니다. volume-line 호출 횟수는 통제 fixture이고 새 체적 정확도 연구가 아닙니다.
기존 주기 네트워크와 독립 유한 조화합/SciPy/scikit-rf 회로 검증도 관련 회귀에 포함합니다.
시간 평균과 조화파 전력 합은 `1e-12` W에 일치합니다. 시작 과도응답/TDR/eye/BER·실측
정확도 주장은 없으며 새 스키마가 웹 폼이나 Windows 수락을 갱신하지 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/periodic_circuit.md)
