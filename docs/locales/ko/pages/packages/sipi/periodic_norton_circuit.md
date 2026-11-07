# 주기 전류원 회로 저장

`sipi.periodic-norton-circuit/1`은 [주기 Norton 응답](periodic_norton.md)을
저장합니다. 클래스는 `sipi.periodic_norton_circuit.PeriodicNortonCircuitDocument`입니다.
개방 단자를 포함한 모든 최종 기준 포트의 전류 파형과 병렬 어드미턴스를
명시합니다. 정규 필드는 `schema`, `network`, `basis`, `source_currents`,
`termination_admittances` 다섯 개입니다.

- `network`는 [주기 네트워크 계약](periodic_document.md)의 기존 7종 입력을
  받습니다. 정규화는 메시나 장 계산을 수행하지 않지만 기존 소규모 네트워크
  대수는 허용합니다. 정확히 실수인 DC부터 균일 고조파 F≥2를 사용하며,
  N=2F−1개 홀수 표본, 주기 1/df, Nyquist 빈 없음의 계약을 유지합니다.
- `basis`는 `single-ended` 또는 기존 4포트·동일 기준 임피던스의 `mixed-mode`
  변환입니다. 두 표는 원본이 아닌 최종 기준의 포트를 참조합니다.
- 두 표에 모든 최종 포트를 정확히 한 번씩 명시합니다. 전류나 부하의 기본값을
  추론하지 않으며 키 삽입 순서가 네트워크 포트 순서를 바꾸지 않습니다.
- `source_currents`는 유한 실수 DC 상수 또는 N개 실수 표본[A]입니다.
  복소 시간 표본·불리언을 거부하며, 명시적 0은 구동하지 않는 포트입니다.
- `termination_admittances`는 유한 실수 또는 `{real, imag}`[S]입니다.
  두 성분은 같은 모양의 스칼라 또는 F개 배열이며 정규화하면 항상 복소 객체가
  됩니다. 실수부는 0 이상, DC 허수부는 정확히 0이어야 합니다. 어드미턴스 0은
  이상 전류원이며 전류원도 0이면 개방입니다. 무한대와 부하 이름 문자열은 거부합니다.

```python
import json
import numpy as np
from sipi.periodic_norton_circuit import PeriodicNortonCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
request = PeriodicNortonCircuitDocument(source,
    source_currents={'near:s': [.001, 0., -.001, 0., .001], 'far:s': 0.},
    termination_admittances={'near:s': .02, 'far:s': 0.})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
result = out['result']
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.array(result['source_current_a']),
    i+np.array(result['termination_current_a']), atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
json.dumps(out, allow_nan=False)
```

## 실행과 보존 결과

`analyze`와 공통 실행은 장 계산·FFT 전에 N을 `max_evaluations`와 비교합니다.
기본 128, 정수 2..10000이며 격자를 잘라 맞추지 않습니다. 파싱 중 기존 소규모
대수를 수행할 수 있으므로 입력 바이트·포트 수·장 실행 시간·출력 크기는 호출자가
별도로 제한해야 합니다.

기존 입력 규칙에 따라 각 기하 발생을 한 번 추출하고, 혼합 모드 변환 전에
주파수·포트 순서·기준 임피던스·원본 basis의 동일성을 확인합니다.
`PeriodicNortonCircuitResult`는 `input_json`, `source_network`, 최종 `network`,
`extraction`, `solution`(`PeriodicNortonResponse`)을 보존합니다.
중첩 장 결과는 Python 객체로 확인합니다.

공통 실행은 정규 입력과 다음 유한 JSON 결과를 보존합니다.

- `coverage='sampled-periodic-steady-state'`, 원본·최종 네트워크;
- `response`: 시간[s], 주기[s], dt[s], 파형[sqrt(W)], 전압[V], 유입 전류[A];
- N×P 실수 시간 배열 `source_current_a`, `termination_current_a`;
- `harmonics`: `convention='dc-mean-positive-peak'`, 복소 `source_current_a`,
  `termination_admittance_s`, `incident_sqrt_w`, `reflected_sqrt_w`,
  `voltage_v`, `current_a`, 실수 진단 `condition_number`, `kcl_residual`, `wave_residual`;
- `harmonics.frequency_power_w`, `mean_power_w`: 각각 `network`,
  `terminations`, `sources` 키를 사용하며 후자는 주기 고조파 전력을 합산한 값[W].

복소 출력은 `{real, imag}`이며 네트워크의 주파수·최종 포트 순서를 따릅니다.
DC는 평균, 양의 고조파는 첨두 페이저입니다. 리액티브 병렬 부하 전류는
Y(f)V(f)를 합성하며 시간 표본을 점별로 곱하지 않습니다. 시간 평균 V*I는
고조파 전력 합과 일치합니다. 독립 주파수 전력을 합산하지 않는 일반
[Norton 회로 저장](norton_circuit.md)의 계약은 그대로입니다.

잘못된 메타데이터·DC/격자, 부유·나쁜 조건수, 비유한 고조파 전력·전력 합은
예외입니다. `complete`는 계산 성공만 뜻합니다. 수동 부하가 네트워크의 수동성,
광대역 인과성·안정성·시작 과도·실측 정확도를 보장하지 않습니다.

7종 입력의 무장 정규화, 5종 대수 입력의 정확한 API/JSON 재실행, 실제 PEC 단일·
차동 혼합 모드의 한 번 추출과 절대 1e−12 일치, 엄격한 표·예산·메타데이터,
저항 전류 분배 해석식·원단 개방·시간/전력 항등식을 검증합니다. volume-line
어댑터 호출 수는 통제된 시험으로 확인하며 새로운 3D 물리 정확도 근거가 아닙니다.
기존 주기 API의 해석식·SciPy·scikit-rf 검사는 관련 회귀에 유지합니다.
44번째 스키마 추가가 앱 입력 화면이나 Windows 지원 갱신을 뜻하지 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/periodic_norton_circuit.md)
