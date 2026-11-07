# 혼합 종단 회로 저장

`sipi.mixed-circuit/1`은 `sipi.mixed_circuit.MixedCircuitDocument`로
[혼합 종단](mixed_termination.md)을 저장합니다. 이상 전압원·단락과 개방·전류원을
함께 지정하면서 모든 포트의 전압과 전류를 보존합니다. 최상위 필드는
`schema`, `network`, `basis`, `boundaries` 네 개입니다.

`network`는 [Norton 회로](norton_circuit.md)의 기존 7종 입력과 메타데이터
계약을 재사용합니다. `basis`는 `single-ended` 또는 기존 4포트·동일 기준
임피던스의 `mixed-mode`입니다. `boundaries`에는 최종 basis의 모든 포트를
정확히 한 번 명시하며 키 삽입 순서가 포트 순서를 바꾸지 않습니다.

각 경계의 필드는 다음 중 하나입니다.

- `kind='thevenin'`, `source_voltage`[V], `impedance`[ohm];
- `kind='norton'`, `source_current`[A], `admittance`[S].

숫자는 유한 실수 또는 `{real, imag}`이며 두 성분은 같은 모양의 스칼라나
F개 표본입니다. 정규 값은 항상 `{real, imag}`입니다. Re Z/Y는 0 이상이며
Z=0은 이상 전압원·단락, Y=0은 이상 전류원·개방입니다. 기본값 추론·무한대·
부하 이름 문자열·추가 필드·불리언을 허용하지 않습니다. 일반·비균일·단일 주파수와
복소 DC를 지원하며 주기 계산의 실수 DC·균일 격자 제약을 추가하지 않습니다.

```python
import json
import numpy as np
from sipi.mixed_circuit import MixedCircuitDocument
from sipi.execution import normalize_saved, execute_saved

source = dict(kind='rlgc', frequency_hz=[0., 1e8, 2e8], R=[[0.]], G=[[0.]],
    L=[[250e-9]], C=[[100e-12]], length_m=.1, reference_ohms=50., names=['s'])
request = MixedCircuitDocument(source, boundaries={
    'near:s': dict(kind='thevenin', source_voltage=1., impedance=0.),
    'far:s': dict(kind='norton', source_current=0., admittance=0.)})
assert normalize_saved(request.dumps()) == request.dumps()
out = execute_saved(request.dumps(), max_evaluations=3)
response = out['result']['response']
v = np.array(response['voltage_v']['real'])+1j*np.array(response['voltage_v']['imag'])
i = np.array(response['current_a']['real'])+1j*np.array(response['current_a']['imag'])
theta = 2*np.pi*np.array(source['frequency_hz'])*.1*5e-9
np.testing.assert_allclose(v[:, 1], 1/np.cos(theta), atol=1e-12, rtol=0)
np.testing.assert_allclose(i[:, 1], 0., atol=1e-12, rtol=0)
assert response['kinds'] == ['thevenin', 'norton']
json.dumps(out, allow_nan=False)
```

## 예산·동일성·결과

정규화는 메시나 장 계산을 하지 않지만 기존 소규모 네트워크 대수는 수행할 수
있습니다. `analyze(max_evaluations=128)`와 공통 실행은 F를 정수 2..10000의
예산과 비교한 뒤 장 추출·종단 피드백을 실행합니다. 바이트·포트 수·장 실행 시간·
출력 크기는 별도로 제한해야 합니다. 주파수 격자를 줄여 맞추지 않습니다.

기존 추출 helper는 혼합 모드 변환 전에 주파수·포트 순서·기준 임피던스·
single-ended 원본 basis를 정확히 확인합니다. 기존 입력 규칙에 따라 기하 발생을
한 번 추출합니다. `MixedCircuitResult`는 정규 `input_json`, `source_network`,
최종 `network`, `extraction`, `response`(`MixedTerminatedNetwork`)를 보존합니다.
중첩 장 추출 객체는 Python으로 확인합니다.

공통 실행은 정규 입력과 다음 결과를 반환합니다.

- `coverage='sampled-frequency-boundary'`,
  `power_convention='dc-weight-one-positive-peak'`, 원본·최종 네트워크;
- 최종 포트 순서의 `response.kinds`, 복소 `{real, imag}` 배열
  `source_voltage_v`, `series_impedance_ohms`, `source_current_a`,
  `shunt_admittance_s`, `incident_sqrt_w`, `reflected_sqrt_w`, `voltage_v`,
  `current_a`; 사용하지 않는 전원·부하 열은 0;
- 실수 `condition_number`[F], `boundary_residual`[F,P], `wave_residual`[F];
- `frequency_power_w`의 `network`, `terminations`, `sources` 배열[W].

KVL·KCL 잔차는 API의 포트별 단위와 상쇄 전 파형 척도를 유지합니다. 전력은
각 포트의 실제 전원 구조를 따릅니다. 독립 주파수 결과이므로 주기 평균으로
합산하지 않습니다. 잘못된 입력·메타데이터 변경·특이/나쁜 조건수·overflow·
비유한 전력은 부분 `complete` 결과로 감추지 않고 예외로 전달합니다.

7종 무장 정규화, 5종 정확 API/JSON 재실행, 실제 PEC 단일·차동 혼합 모드의
한 번 추출과 절대 1e−12 일치, 이상 전압원·개방 선로 해석식, 엄격한 표·예산 순서·
메타데이터·비주기 격자·복소 DC·오류 경로를 검증합니다. volume 어댑터 호출 수는
통제된 시험이며 새로운 물리 정확도 근거가 아닙니다. 혼합 API의 SciPy·scikit-rf
독립 절점 검증도 관련 회귀에 유지합니다. 45번째 저장 스키마가 새 장 모델·실측
정확도·인과성/시작 과도·앱 화면·Windows 수락을 뜻하지 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/mixed_circuit.md)
