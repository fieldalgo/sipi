# Norton 회로 저장 입력

`sipi.norton_circuit.NortonCircuitDocument`는 주파수 영역 전류원 경계 문제를
**`sipi.norton-circuit/1`**로 저장합니다. [Norton API](norton_termination.md)와
[공통 실행 진입점](execution.md)을 재사용하며 새 전계 모델이나 주기 시간영역
가정을 추가하지 않습니다.

최상위 필드는 `schema`, `network`, `basis`, `source_currents`,
`termination_admittances`입니다. 두 표에는 **최종 basis의 모든 포트**를
명시해야 하며 0 소스와 개방 어드미턴스도 생략할 수 없습니다. Python API의
생략 포트 기본값을 저장 문서에 암묵 적용하지 않습니다. 전류는 A, 병렬 어드미턴스는 S입니다.

복소수는 `{real, imag}`로 쓰며 두 성분이 같은 유한 스칼라 또는 주파수별 배열
형태여야 합니다. 실수 입력도 이 형태로 정규화합니다. 배열 길이는 F입니다.
bool·누락/추가/중복 키·비유한 값·미등록 포트/버전·음수 어드미턴스 실수부를
거부합니다. `Y=0, Is=0`은 명시적 개방, `Y=0, Is!=0`은 이상 전류원입니다.
`open`/`short` 문자열이나 무한 어드미턴스를 사용하지 않습니다.

```python
from sipi.norton_circuit import NortonCircuitDocument
from sipi.execution import normalize_saved, execute_saved

network = dict(kind='rlgc', frequency_hz=[0., 1e8, 3e8],
    R=[[10.]], L=[[250e-9]], G=[[.001]], C=[[100e-12]],
    length_m=.03, reference_ohms=50., names=['s'])
doc = NortonCircuitDocument(network,
    source_currents={'near:s': .001, 'far:s': 0.},
    termination_admittances={'near:s': .02, 'far:s': 0.})
assert normalize_saved(doc.dumps()) == doc.dumps()
output = execute_saved(doc.dumps(), max_evaluations=3)
assert output['status'] == 'complete' and output['input'] == doc.to_dict()
current = output['result']['response']['current_a']
assert all(abs(re[-1])+abs(im[-1]) < 1e-12
           for re, im in zip(current['real'], current['imag']))
```

## 네트워크·좌표·계산 예산

`network.kind`는 기존 엄격 입력인 `rlgc`, `touchstone`, `lumped-network`,
`transmission-line`, `volume-line`, `network-transform`, `network-assembly`를
지원합니다. 생성·정규화는 전계를 풀지 않으며 기존 검증기의 작은 네트워크 대수
계산은 허용합니다. 원래 주파수 격자와 추출 모델의 유효범위를 유지합니다.
단일 주파수·비균일 양의 표본·주파수 영역의 복소 DC 입력도 받으며 보간·DC 추정이나
주기 입력의 실수 DC 제약을 추가하지 않습니다.

원본은 single-ended 네트워크여야 합니다. `basis='single-ended'`는 원포트를
유지하고, `basis='mixed-mode'`는 동일 기준 임피던스의 4포트에 기존 전력 쌍대
변환을 적용합니다. 최종 순서는 `d_near, d_far, c_near, c_far`입니다.
전류원과 부하는 최종 basis에 속하며 이름으로 물리 단자나 소스 위치를 추론하지 않습니다.

`frequency_count`는 F입니다. `analyze(max_evaluations=128)`와 `execute_saved`의
예산은 2–10000 정수이며 F 이상이어야 합니다. 한 주파수 요청도 예산은 최소 2입니다.
입력 검사 뒤 전계 추출·단자 피드백 전에 예산을 확인합니다. 전계 기반 소스는 한 번
추출하며 기록한 주파수·포트 순서·기준 임피던스·source basis가 바뀌면 경계 풀이 전에
거부합니다.

## 결과와 한계

`NortonCircuitResult`는 `input_json`, `source_network`, 최종 `network`,
원본 `extraction`(해당할 때)과 전체 Norton `response`를 보존합니다.
공통 `sipi.execution/1`은 정규 입력과 `sampled-frequency-boundary` 범위를
기록하고 단위를 명시합니다.

| 출력 | 의미 |
|---|---|
| `source_current_a`, `termination_admittance_s` | 전류원·병렬 부하 표 |
| `incident_sqrt_w`, `reflected_sqrt_w` | 전력 파동 페이저 |
| `voltage_v`, `current_a` | 단자 전압·네트워크 안으로 들어가는 전류 |
| `condition_number`, `kcl_residual`, `wave_residual` | 원본 솔버 진단 |
| `frequency_power_w` | 각 주파수의 네트워크·병렬 부하·이상 전류원 전력 |

응답 필드는 `result.response`, 전력은 `result.frequency_power_w`에 있습니다.
복소 배열은 실수·허수 성분을 보존합니다. DC 전력 가중치는 1, 양의 주파수 피크
페이저는 1/2이며 **서로 다른 주파수를 주기 평균전력으로 합산하지 않습니다**.
Norton 내부 소스·병렬 전력은 해당 토폴로지의 값이며 Thevenin 변환 후 내부 전력과
같지 않습니다.

특이·부유·조건수·잔차·overflow 실패는 원래 API 예외로 전달하며 완료나 부분 성공으로
포장하지 않습니다. 결과는 유한 JSON입니다. 최상위 전계 진단 옵션은 이 회로 래퍼에
적용하지 않습니다.

7종 소스의 전계 없는 정규화, 대수 소스 5종의 정확한 직접 재현, 실제 PEC 단일/쌍
혼합 좌표의 전계 한 번 추출과 절대 `1e-12` 대조, 엄격 입력·메타데이터 변경·전계/
피드백 전 예산·실패 전달을 검사합니다. volume-line은 제어된 fixture로 호출 횟수를
검사하며 새 volume 물리 검증이 아닙니다. 독립 회로 수치 기준은 별도로 검증한
Norton API를 따릅니다. 등록 저장 스키마는 43종입니다. 실측 정확도·일반 3D 구조나
새 스키마의 브라우저/Windows 수락을 뜻하지 않습니다.

[Thevenin 회로 입력](circuit_document.md) · [English](../../../../../packages/sipi/norton_circuit.md)
