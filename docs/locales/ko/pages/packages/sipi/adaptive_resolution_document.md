# 예산 있는 자동 세분 요청 저장

명시적 `sipi.line-resolution/2`는 기존 [자동 세분](adaptive_line_resolution.md)
요청을 저장합니다. 버전 1의 키에 필수 `max_levels`가 추가됩니다. 버전 1은
기존 고정 비교 순서와 정규화 입력을 보존합니다. 생성·정규화 중 전계 계산은
없습니다. 내부 선로 1–7, SI 허용차와 물리 조건을 보존하는 외곽 검증은 직접
API와 같습니다.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import LineResolutionDocument
from sipi.execution import execute_saved

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={"kind": "perfect"}, length=.02)
raw = line.to_dict()
raw["cross_section"]["box"]["width"] = .016
for key in ("edge_size", "far_size", "grade"):
    raw["cross_section"]["mesh"][key] *= .5
request = LineResolutionDocument(line,
    outer_documents=[TransmissionLineDocument.from_dict(raw)],
    tolerances={"C": ResolutionTolerance(.005, 0.)},
    schema="sipi.line-resolution/2", max_levels=3, max_solves=5)
text = request.dumps()
assert LineResolutionDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=5)
assert output["status"] == "complete"
```

`max_levels`는 2–8 정수, `max_solves`는 4–16입니다. 저장 예산과 공통 실행의
`max_evaluations`가 모두 전체 선로 평가 횟수를 제한합니다. 전계 계산 전에
최소 `3 + len(outer_lines)`가 들어가는지 검사합니다. 다음 메시를 풀기 전에
필수 외곽 평가 예산을 확보하며 기존 결과를 재사용합니다. 예산을 다 쓴 뒤
외곽 검사를 생략하고 성공으로 처리하지 않습니다.

결과에는 정확한 입력·완료된 전계 배열·차이·허용량·실패가 보존됩니다.
추가 필드는 `stop_reason`, `mesh_levels`, `expected_outer_evaluations`,
`outer_completed`, `selected_evaluation_index`입니다. 수락했을 때 선택 인덱스는
원래 영역에서 세분한 결과를 가리키며 그 외에는 `null`입니다.

| 종료 이유 | 공통 상태 | Completed | Accepted |
|---|---|---|---|
| `accepted` | `complete` | true | true |
| `mesh-unaccepted` | `complete` | true | false |
| `outer-unaccepted` | `complete` | true | false |
| `budget-exhausted` | `failed` | false | false |
| `field-failed` | `failed` | false | false |

예산 소진은 부분 결과를 보존하고 `budget` 단계의 `ResolutionBudgetExceeded`
오류를 반환합니다. 전계 예외로 멈춘 것은 아니므로 결과의 `failure`는
`null`입니다. 전계 실패는 원래 예외와 시도한 정확한 입력·단계를 보존합니다.
사용자 중단은 전파합니다. 계산 완료 후 미수락은 실행 오류가 아니므로
소비자는 상태와 함께 `accepted`를 확인해야 합니다.

연속 두 메시 비교와 명시 외곽 검사 통과는 절대 오차나 실측 정확도의 증명이
아닙니다. 수락을 얻기 위해 허용차·기하·재료·추출 방식을 바꾸지 않습니다.
패널 선로 평가는 [별도 명시 API](panel_resolution.md)로 유지합니다.

[English](../../../../../packages/sipi/adaptive_resolution_document.md)
