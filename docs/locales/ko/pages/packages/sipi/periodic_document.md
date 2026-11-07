# 주기 네트워크 응답 저장

`sipi.periodic-network/1`은 원래 네트워크, 명시 출력 기저, 입사 전력파 표본과 선택적인
이산 임펄스 요청을 저장합니다. [주기 API](periodic.md)의 실수 DC·균일 조화파·홀수
표본 수·원형 주기 정상상태 계약을 그대로 사용합니다. 누락 DC·창 함수·보간·시작
과도응답·소스/종단 추정을 추가하지 않습니다.

`sipi.periodic_document`의 `PeriodicNetworkDocument`를 사용합니다. 정규 객체의 필드는
`schema`, `network`, `basis`, `incident`, `include_impulse`뿐입니다. 생성자 기본값은
`basis='single-ended'`, `include_impulse=False`이며 저장 JSON에는 둘 다 명시합니다.
알 수 없는 필드/버전·중복 키·비유한 숫자·bool/비숫자 표본·잘못된 포트는 거부합니다.

## 원본과 입사파 계약

`network`는 기존 자체 완결 입력 7종을 재사용합니다:
`rlgc`, `touchstone`(내장 텍스트), `lumped-network`, `transmission-line`,
`volume-line`, `network-transform`, `network-assembly`.
기존 모델·중첩·메타데이터 제한을 유지하며 파일명·URL·표현식·자동 외부 읽기는
입력 방식으로 허용하지 않습니다.

`incident`는 **최종 기저의 모든 포트 이름을 정확히 한 번씩** 명시하는 객체입니다.
생략이나 추가 포트는 없으며, 값은 sqrt(W) 단위의 유한 실수 배열입니다.
원 주파수 표본 수 F에 대해 길이는 `N = 2*F-1`입니다. 객체 삽입 순서로 포트 순서를
정하지 않습니다. 구동하지 않는 포트도 0 배열로 명시합니다. 기준면의 입사파이며
Thevenin 소스 전압이 아닙니다. 비정합 소스/부하는 원 네트워크에 포함하거나 따로
모델링해야 합니다. 이 요청은 그 피드백을 암묵적으로 풀지 않습니다.

`basis='mixed-mode'`는 near+/near-/far+/far- 순서의 동일 기준 임피던스 단일 종단
4포트를 요구합니다. 입사 키는 `d_near`, `d_far`, `c_near`, `c_far`이고 기존 변환의
차동/공통 기준값을 사용합니다. 그 밖에는 `basis='single-ended'`를 사용합니다.
`include_impulse`는 JSON bool이어야 합니다.

```python
import json
from sipi import LumpedNetworkDocument
from sipi.periodic_document import PeriodicNetworkDocument
from sipi.execution import normalize_saved, execute_saved

source = LumpedNetworkDocument([0., 1e8, 2e8], resistance=10., inductance=2e-9)
request = PeriodicNetworkDocument(
    dict(kind='lumped-network', document=source.to_dict()),
    incident={'near': [0., 1., .5, -.5, -1.], 'far': [0.]*5},
    include_impulse=True)
text = normalize_saved(request.dumps())
assert text == request.dumps()
output = execute_saved(text, max_evaluations=5)
assert output['status'] == 'complete'
assert output['result']['coverage'] == 'sampled-periodic-steady-state'
assert len(output['result']['response']['time_s']) == 5
assert output['result']['impulse'] is not None
json.dumps(output, allow_nan=False)
```

## 검증·예산·결과

정규화에서는 주파수·표현 가능한 주기·입사 표본 수·포트 메타데이터를 검사하며
필드 메시를 만들지 않습니다. 기존 RLGC/집중 소자 검증은 작은 대수 계산을 할 수
있습니다. S가 이미 있으면 복소 DC를 즉시 거부하고, 필드 기반 S는 추출 후 검사합니다.
원 모델 자체의 DC 제한도 유지합니다. 고주파 표면 근사를 이 요청에 맞추려고 DC까지
늘려서는 안 됩니다.

`analyze(max_evaluations=128)`와 공통 실행의 같은 인수는 **시간 표본 N개**를 셉니다.
기존 정수 범위 2..10000과 표본 수를 필드 추출/FFT 전에 검사하며 격자를 줄이지 않습니다.
필드 시간·포트 수·포트 수 제곱에 비례하는 S/임펄스 크기·파싱 대수 계산 전체의
제한은 아닙니다. 입력 바이트 예산과 호출자 프로세스 제한은 별도입니다.

각 저장 기하 항목은 기존 원본 추출을 한 번 수행합니다. 추출 후 주파수·포트 순서·
기준값·단일 종단 기저가 저장 메타데이터와 일치해야 혼합 모드로 바꿀 수 있습니다.
Python 결과는 `input_json`, `source_network`, 최종 `network`, `extraction`,
`response`, 선택적인 `impulse`를 보존합니다.

공통 유한 JSON 결과는 이름·기저·기준값·복소 S를 포함한 두 네트워크와 다음을 보존합니다.

- `coverage='sampled-periodic-steady-state'`;
- `response.time_s`, `period_s`, `dt_s`, `incident_sqrt_w`, `reflected_sqrt_w`,
  `voltage_v`, `current_a` — 시간 × 최종 기저 포트 순서;
- `impulse=null` 또는 `{lag_s, weights}` — 같은 주기·간격의 지연 × 출력 포트 ×
  입력 포트 순서이며 가중치는 무차원입니다.

정규 입력을 보존하지만 중첩 필드 객체는 JSON에서 생략하므로 필요하면 Python 결과를
사용합니다. `complete`는 변환 완료이며 물리 정확도/인과성 인증이 아닙니다.
원본·메타데이터·DC·숫자 범위 오류는 그대로 전달하며 부분 성공으로 바꾸지 않습니다.

7종 원본의 정규화 무필드 검사, 대수 원본 5종의 직접/저장 정확 재생, 실제 PEC 단일/쌍
추출과 혼합 모드 응답의 절대 `1e-12` 비교, 추출 횟수·예산·메타데이터 변조를 검증합니다.
volume-line 어댑터 호출 횟수는 통제한 네트워크 fixture로 검사하며 새 체적 추출 정확도
검증이 아닙니다. 기존 주기 API의 직접 유한 DFT·scikit-rf·SciPy 비교를 관련 회귀에
포함하고 한·영 예제와 정확 설치본을 검사합니다. JSON 지원이 웹 폼·Worker 동등성·
Windows 지원을 갱신하지는 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/periodic_document.md)
