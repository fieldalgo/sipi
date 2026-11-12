# 주기 혼합 전원 회로 저장

`sipi.periodic-mixed-circuit/1`은
`sipi.periodic_mixed_circuit.PeriodicMixedCircuitDocument`로
[주기 혼합 전원](periodic_mixed.md)을 저장합니다. 최상위 필드는
`schema`, `network`, `basis`, `boundaries`입니다.

기존 7종 자체 포함 네트워크와 메타데이터 검사는 [혼합 회로 계약](mixed_circuit.md)을
따릅니다. 주기 격자는 정확히 실수인 DC S부터 균일 고조파 F≥2, 홀수 N=2F−1,
주기 1/df가 필요합니다. `basis`는 single-ended 또는 기존 4포트·동일 기준
임피던스의 mixed-mode입니다. 모든 최종 포트의 경계를 명시하며 기본값을 추론하지 않습니다.

- Thevenin 필드: `kind='thevenin'`, `source_voltage`[V], `impedance`[ohm].
- Norton 필드: `kind='norton'`, `source_current`[A], `admittance`[S].
- 전원은 유한 실수 DC 상수 또는 N개 실수 시간 표본입니다. 복소 객체·불리언·
  잘못된 모양을 거부합니다.
- 부하는 유한 실수 또는 `{real, imag}`이며 같은 모양의 스칼라/F개 성분입니다.
  정규 부하는 항상 `{real, imag}`입니다. Re Z/Y≥0, DC 허수부 정확히 0이 필요합니다.
  Z=0 이상 전압원·단락과 Y=0 이상 전류원·개방을 함께 사용할 수 있습니다.
  무한대·부하 이름 문자열·추가 필드는 오류입니다.

```python
import json
import numpy as np
from sipi.periodic_mixed_circuit import PeriodicMixedCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
drive = (.3+.2*np.cos(2*np.pi*np.arange(5)/5)).tolist()
request = PeriodicMixedCircuitDocument(source, boundaries={
    'near:s': dict(kind='thevenin', source_voltage=drive, impedance=0.),
    'far:s': dict(kind='norton', source_current=0., admittance=0.)})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=5)
result = out['result']
v = np.array(result['response']['voltage_v'])
i = np.array(result['response']['current_a'])
np.testing.assert_allclose(v[:, 0], drive, atol=1e-12, rtol=0)
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
np.testing.assert_allclose(np.mean(np.sum(v*i, axis=1)),
    result['mean_power_w']['network'], atol=1e-12, rtol=0)
assert result['harmonics']['kinds'] == ['thevenin', 'norton']
json.dumps(out, allow_nan=False)
```

## 실행·진단·전력

파싱은 장 계산을 하지 않지만 기존 소규모 네트워크 대수는 수행할 수 있습니다.
`analyze`와 공통 실행은 장·FFT 전에 N을 `max_evaluations`(기본 128, 정수 2..10000)와
비교하며 격자를 줄이지 않습니다. 바이트·포트 수·장 실행 시간·출력 크기는 별도로 제한합니다.

기존 입력 규칙에 따라 기하 발생을 한 번 추출하고, 혼합 모드 변환 전에 주파수·
포트·기준 임피던스·원 basis를 정확히 확인합니다. `PeriodicMixedCircuitResult`는
정규 `input_json`, `source_network`, 최종 `network`, `extraction`,
`solution`(`PeriodicMixedResponse`)을 보존합니다. 중첩 장 객체는 Python으로 확인합니다.

공통 실행은 정규 입력과 다음 유한 JSON을 반환합니다.

- `coverage='sampled-periodic-steady-state'`, 원본·최종 네트워크;
- `response`: 시간·주기·dt[s], 실수 파형[sqrt(W)], 전압[V], 유입 전류[A];
- N×P 실수 `source_voltage_v`, `source_current_a`, `termination_voltage_v`,
  `termination_current_a`; 사용하지 않는 종류의 열은 0;
- `harmonics`: `convention='dc-mean-positive-peak'`, 포트 순서의 `kinds`,
  일반 혼합 회로의 복소 전원·부하 배열 네 개와 a/b/V/I,
  `condition_number`[F], `boundary_residual`[F,P], `wave_residual`[F];
- `harmonics.frequency_power_w`, `mean_power_w`: `network`, `terminations`,
  `sources` 키를 사용하며 평균은 주기 고조파 전력 합[W].

복소 고조파는 `{real, imag}`이며 DC 평균·양의 첨두 페이저는 원 주파수·최종
포트 순서를 따릅니다. 리액티브 직렬 전압강하·병렬 전류는 ZI/YV에서 합성합니다.
시간 평균 전력은 각각 V·I, drop·I+V·shunt, Vs·I+V·Is입니다. 주기 합산이 일반
혼합 회로의 독립 주파수 전력 의미를 바꾸지 않습니다. 포트별 KVL/KCL 정규화도
별도 단위와 상쇄 전 파형 척도를 유지합니다.

잘못된 입력·메타데이터/DC 변경·특이 피드백·비유한 전력/합은 예외이며
`complete`는 계산 성공만 뜻합니다. 보간·창·누락 DC·인과적 시작 과도를 추론하지 않습니다.

7종 무장 정규화, 5종 정확 API/JSON 재실행, 실제 PEC 단일·차동 혼합 모드의
한 번 추출과 절대 1e−12 일치, 이상 전압원·개방 선로의 주기 해석 합성,
시간/고조파 전력·종류별 열, 엄격한 입력·예산·메타데이터·오류 전달을 검증합니다.
volume 호출 수는 통제된 시험이며 새 물리 검증이 아닙니다. SciPy·scikit-rf
주기 혼합 기준과 기존 일반 혼합 직렬화도 관련 회귀에 유지합니다. 46번째 스키마가
새 장·실측 정확도, 시작 과도·인과성 인증, 앱 입력 화면·Windows 수락을 뜻하지 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/periodic_mixed_circuit.md)

## 전력 합계 재현

`mean_power_w`는 내보낸 각 `frequency_power_w` 목록에 Python `sum`을 적용합니다.
지원 Python 런타임에서 저장된 성분을 합산하면 동일한 합계를 재현하며,
NumPy의 다른 합산 경로를 사용하지 않습니다. 주파수별 해, 시간 영역 전력 검사,
비유한 결과 거부는 그대로입니다. 물리 모델의 정확도 개선을 뜻하지 않습니다.
