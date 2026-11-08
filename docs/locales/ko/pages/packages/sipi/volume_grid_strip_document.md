# 유한 신호선·접지 격자 체적 입력 저장

[English](../../../../../packages/sipi/volume_grid_strip_document.md) | **한국어**

`VolumeGridStripCapacitanceDocument`는 [유한 신호선·접지 체적 셀](volume_grid_strip.md)의
18개 입력을 `sipi.volume-grid-strip-capacitance/1`에 보존합니다. 두 유한 PEC 체적,
세 실수 유전체 영역, 명시적 절연 경계를 사용하며 전체 정전용량 C[F]를 계산합니다.
기하·재료·조건을 명시한 수렴 범위는 그대로입니다.

```python
from sipi import VolumeGridStripCapacitanceDocument

document = VolumeGridStripCapacitanceDocument(
    pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3, height=.5e-3,
    top_clearance=1e-3, backside_depth=1e-3, ground_thickness=.25e-3, trace_thickness=.25e-3,
    eps_substrate=3.8, eps_above=1., eps_below=1.,
    transverse_periods=1, cells_per_pitch=4, cells_substrate=2,
    cells_above=4, cells_below=3, cells_grid=1, cells_trace=1)
saved = document.dumps()
reloaded = VolumeGridStripCapacitanceDocument.loads(saved)
assert reloaded.dumps() == saved
result = reloaded.analyze(max_evaluations=1)
assert result.capacitance_f > 0
```

루트는 정확히19키입니다. `schema`, `pitch_m`, `grid_width_m`, `trace_width_m`,
`height_m`, `top_clearance_m`, `backside_depth_m`, `eps_substrate`, `eps_above`,
`eps_below`, `transverse_periods`, `cells_per_pitch`, `cells_substrate`,
`cells_above`, `cells_below`, `ground_thickness_m`, `cells_grid`, `trace_thickness_m`,
`cells_trace`를 모두 명시합니다.
SI 기하·양의 상대 유전율에서 불리언은 거부하며 일곱 셀 수는 엄격한 정수입니다.
접지 두께는 양수이고 아래 깊이보다 작아야 합니다. 누락·추가·중복 키, 미지원 버전,
다른 단위, 비유한 값, 비정합 폭은 거부합니다. 다섯 수직 분할 수는 독립적입니다.

정규화는 원래의 스칼라·정합·금속 제거 전 노드/사면체·유한 체적·상단 여유를 검사하고
메시 생성이나 장 풀이는 하지 않습니다. 입력을 축소·추론하지 않으며 사전은 사본이고
JSON은 정렬된 유한 값입니다. `analyze(max_evaluations=1)`는 정수1..10000을 받아
장을 한 번 풉니다. [공통 실행기](execution.md)는 기존2..10000 범위를 유지하며2를
주어도 한 번 풉니다. 큰 예산은 세분 검사를 요청하지 않습니다.

```python
from sipi.execution import normalize_saved, execute_saved

assert normalize_saved(saved) == saved
output = execute_saved(saved, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result'] == result.to_dict()
assert not output['result']['fields_included']
```

재현 시 결과·셀·장 자료형과 입력, 제거 전·후 노드/사면체 수, 전극 수, 실제 폭·
edge index, 금속·유전체 체적, 재료·장 형태와 원래 체적 오차 제한을 검사합니다.
인덱스와 유한 좌표를 확인한 뒤 좌표 범위, 좌표로 정의한 전체 접지·트레이스 라벨,
미사용 노드가 없음, 세 유전체 영역을 확인합니다. 두 번째 메시를 생성하지 않으며
원래 장 오류를 전달합니다.

공통 결과는 배열을 생략합니다. 직접 결과는 `to_dict(include_fields=True)`로
메시·재료·1V 전위를 포함할 수 있습니다. 확장 결과는 입력 문서가 아닙니다.
파일 접근은 호출자가 담당하며 엔진이 암묵적으로 파일을 쓰지 않습니다.
기존 얇은 격자와 다른 저장 스키마는 별도로 유지합니다.

시험은 부분·완전 격자, 넓은 영역, 비균일 수직 층, 반올림 범위의 폭에서 전체 장을
정확히 재현합니다. 모든 키·단위·셀 수·기하/자원 예산·복사·한 번 풀이, 결과/기하/
재료 훼손38종, 다른 종류와 원래 오류를 검사합니다. 독립 장·해석·수렴 시험은
물리 suite에 보존하여 함께 실행합니다. 수치 기준이나 물리 솔버를 바꾸지 않습니다.

물리 API의 얇은 신호선 비교는 절대 상단과 공통 간격을 고정합니다. 신호선 두께는
양수이며 위 경계에 포함합니다. 신호선 상단과 그 위 여유가 모두 표현 가능해야 합니다. 저장 재현은 임의 재분할 단조·물리 정확도·개방 경계를 인증하지
않습니다. 선로 RLGC·귀환 인덕턴스·주파수·실측·앱·플랫폼 지원이나 새 의존성을
추가하지 않습니다.
