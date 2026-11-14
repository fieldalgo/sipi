# 형상전류 해상도 비교 저장

`ShapePanelResolutionDocument`는 [분리 해상도 비교](shape_panel_resolution.md)를
`sipi.shape-panel-resolution/1`로 저장합니다. 필수 키는 `schema`, `line`,
`refined_panel`, `outer_lines`, `tolerances`, `refinement_factor`, `max_solves`의
일곱 개입니다. 고정 코팅 금속을 포함하는 명시 형상전류 선로만 받습니다.
알 수 없는 키·누락·중복·비유한 JSON 값은 거부합니다.

허용값 키는 SI 단위의 `R_ohm_per_m`, `L_internal_h_per_m`,
`L_external_h_per_m`, `C_f_per_m`, `G_s_per_m`, `C0_f_per_m`입니다.
각각 명시적인 `relative`, `absolute`를 가집니다. 정규화는 필드를 풀지 않고
전체 계획을 검사하며 허용값이나 적용 범위를 자동 선택하지 않습니다.
형상 미분폭 비율은 모든 단계에서 고정됩니다.

저장 `max_solves`와 호출자의 `max_evaluations`는 모두 **선로 전체 평가 횟수**를
제한합니다. 기본·세분 네 단계와 모든 외곽 입력이 두 예산에 들어가야 필드를
풉니다. 내부 공유 패널 호출 횟수가 아니며, 단독 저장 선로의 주파수 개수
제한과도 다릅니다.

공통 실행과 `SavedExecutionRequest`는 다음 결과를 보존합니다.

- 비교 완료는 `status: complete`, 결과, null 오류를 반환합니다.
  `accepted: false`도 완료된 평가이며 검사 통과를 뜻하지 않습니다.
- 필드 실패는 `status: failed`, null 결과를 반환합니다. 형식 있는 오류의
  `partial_assessment`에 이전 평가·원래 단계/입력/원인·완료 또는 부분 전류
  표본·두 미분폭 진단을 보존합니다.
- 중단은 전파하고 입력·예산 오류는 필드 계산 전에 거부합니다.

두 결과 모두 `SavedExecutionRecord`에 저장하고 계산 없이 불러오거나 준비할
수 있습니다. 많은 전류 표본에는 기존 기록 크기 제한이 적용됩니다.
아티팩트 선언은 호스트의 주장이지 정확도나 실행 사실의 인증이 아닙니다.
예제는 전송 동작을 보여주려고 C0에만 느슨한 10% 허용값을 사용합니다.
저항·외곽 영역 충분성·정확도를 검증하는 예제가 아닙니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_panel_resolution_document import ShapePanelResolutionDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest
from sipi.line_resolution import ResolutionTolerance

section = CrossSection([Layer('uniform', .002, 4.2, tan_delta=.02)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=0.)
base = ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(
    line, panels_per_edge=16, ground_modes=512, interpolation_degree=16))
fine = dict(panels_per_edge=32, ground_modes=1024, interpolation_degree=16)
raw = base.to_dict()
raw['line']['panel'] = dict(fine, ground_modes=2048)
cross = raw['line']['line']['cross_section']
cross['box']['width'] *= 2
cross['layers'][-1]['thickness'] *= 2
for key in ('edge_size', 'far_size', 'grade'):
    cross['mesh'][key] *= .5
outer = ShapePanelTransmissionLineDocument.from_dict(raw)
saved = ShapePanelResolutionDocument(base, refined_panel_options=fine,
    outer_documents=[outer], tolerances={'C0': ResolutionTolerance(.1, 0.)},
    max_solves=5)
text = saved.dumps()
assert normalize_saved(text) == text
receipt = SavedExecutionRequest(text, max_evaluations=5).run()
out = receipt['execution']
assert out['status'] == 'complete' and out['error'] is None
assert out['result']['completed'] and out['result']['accepted']
assert len(out['result']['evaluations']) == 5
assert len(out['result']['evaluations'][0]['current_solver']['samples']) == 13
```

[English](../../../../../packages/sipi/shape_panel_resolution_document.md)
