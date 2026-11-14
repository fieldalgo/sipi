# 형상전류 반복 세분 계획 저장

`AdaptiveShapePanelResolutionDocument`는
[명시적 형상전류 반복 세분](adaptive_shape_panel_resolution.md)을
`sipi.adaptive-shape-panel-resolution/1`로 저장합니다. 필수 키는
`schema`, `line`, `refinements`, `tolerances`, `refinement_factor`,
`max_solves` 여섯 개입니다. 선로와 외곽 입력은 shape-panel 선로 버전 1을
명시하며 중첩 금속은 기존 벌크 또는 고정 코팅 모델을 사용합니다.
기본 방식이나 옛 요청을 자동으로 바꾸지 않습니다.

`refinements`는 `refined_panel`(세 제어 전체)과 `outer_lines`를 가진
2~4단계입니다. 정규화 시 미래 메시·패널·형상 이동, 고정 shape step,
물리 입력과 외곽 크기·순서를 전계 계산 없이 검사합니다. 허용차는 SI 키
`R_ohm_per_m`, `L_internal_h_per_m`, `L_external_h_per_m`, `C_f_per_m`,
`G_s_per_m`, `C0_f_per_m` 중에서 선택하며 각 값의 키는 `relative`,
`absolute`입니다. 모든 선택 항·주파수에 작은 항 하한 없이 적용합니다.

`analyze(max_evaluations=...)`는 저장 예산과 caller 예산의 최솟값을
사용합니다. 전체 선로 시도 7회+명시 외곽 수보다 작으면 계산 전에 거부합니다.
직접 API와 같은 상태기계가 다음 세 번과 외곽 예산을 예약하고 이전 동시 세분
결과를 재사용합니다. 네 방향 비교가 두 단계 연속 통과해야 외곽을 계산합니다.
사용하지 않는 미래 단계도 입력 검사는 하지만 전계는 풀지 않습니다.

공통 실행은 완료와 수락을 구분합니다. `accepted`, `resolution-unaccepted`,
`outer-unaccepted`는 status complete와 수락 여부를 보존한 result를 냅니다.
`field-failed`, `budget-exhausted`는 status failed, null result와 typed error를
냅니다. error의 `partial_assessment`에 정확한 입력·완료 행렬·전체 전류 표본·
비교·종료 이유를 보존합니다. 전계 실패는 원 종류·단계·입력과 전체/부분
전류 원인도 남깁니다. 예산 소진은 전계 오류와 구분하며 사용자 중단은 전파합니다.

기존 `SavedExecutionRecord` 두 버전에서 이 새 입력의 기록을 저장·복원하고
전계 없이 재실행 요청을 준비할 수 있습니다. 기존 record 규칙과 옛 부분 실패
형식은 바뀌지 않습니다. 프로젝트도 같은 기록과 호스트 artifact 선언을
보존합니다. 기록 무결성은 수치 정확도나 실측 인증이 아닙니다.

아래는 요청만 준비하는 예제입니다. 느슨한 C0 허용값은 제어 예시이며
저항이나 작은 상호항 수락 기준이 아닙니다. 유한 기하·주파수와 물리 모델
한계는 직접 API와 같습니다. `request.run()`으로 실제 계산을 시작하고
미수락·부분 결과도 보존합니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.adaptive_shape_panel_resolution import (
    ShapePanelResolutionRefinement, refine_shape_panel_line_resolution,
)

section = CrossSection([Layer('uniform', .002, 4.2)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={}, conductor={'kind': 'perfect'}, length=0.)
base = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=1024, interpolation_degree=16))
steps = []
for level in (1, 2):
    raw = base.to_dict()
    options = dict(base.line.panel_options, panels_per_edge=16 * 2**level)
    raw['line']['panel'] = dict(options, ground_modes=2048)
    cross = raw['line']['line']['cross_section']
    cross['box']['width'] *= 2
    cross['layers'][-1]['thickness'] *= 2
    for key in ('edge_size', 'far_size', 'grade'):
        cross['mesh'][key] *= .5**level
    steps.append(ShapePanelResolutionRefinement(
        options, [ShapePanelTransmissionLineDocument.from_dict(raw)]))
controls = dict(refinements=steps, tolerances={'C0': ResolutionTolerance(.1, 0.)},
                max_solves=8)
from sipi.adaptive_shape_panel_resolution_document import AdaptiveShapePanelResolutionDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
saved = AdaptiveShapePanelResolutionDocument(base, **controls)
assert normalize_saved(saved.dumps()) == saved.dumps()
request = SavedExecutionRequest(saved.dumps(), max_evaluations=8)
assert request.to_dict()['input'] == saved.to_dict()
# receipt = request.run()  # Starts actual line batches.
```
