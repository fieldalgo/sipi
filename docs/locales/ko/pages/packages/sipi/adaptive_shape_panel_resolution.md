# 형상전류 패널·체적 메시의 유계 반복 세분

`refine_shape_panel_line_resolution`은 `ShapePanelTransmissionLineDocument`와
명시적 `ShapePanelResolutionRefinement(panel_options, outer_documents)`
2~4단계를 받습니다. 각 단계는 더 세분된 패널 설정과 해당 체적 해상도의
외곽 입력을 지정합니다. 패널 제어는 감소할 수 없고 하나 이상 증가해야 합니다.
체적 메시의 `edge_size`, `far_size`, `grade`는 같은 `refinement_factor`로
줄어듭니다. 외곽 크기·순서는 단계 사이에 고정하며 외곽의 ground modes는
증가할 수 있습니다. 기하·주파수·포트·금속·`step_fraction`은 고정합니다.
중첩 금속 입력의 두 버전을 모두 지원합니다.

모든 미래 단계·외곽·형상 이동 입력을 전계 계산 전에 검사합니다.
[기존 패널 반복 세분](adaptive_panel_resolution.md)과 같은 상태기계를 사용하며
체적/기본, 패널/기본, 동시/체적, 동시/패널 비교가 연속 두 단계에서 모두
통과해야 합니다. 중간 미달은 연속 수를 초기화합니다. 이전 동시 세분 결과를
다음 기본값으로 재사용하며 두 단계 통과 후에만 해당 단계의 외곽을 계산합니다.
외곽 미달은 즉시 중지하며 패널 세분을 계속해 숨기지 않습니다.

선택한 모든 행렬 항·주파수에 명시적 SI 허용값
`abs(a-b) <= absolute + relative * max(abs(a), abs(b))`를 적용합니다.
작은 항의 분모 하한은 없습니다. 생략한 물리량은 검사하지 않습니다.
매 추출에서 형상 미분의 두 이동폭 검사도 유지합니다. 수락은 유한 비교의
일치이며 절대오차·점근 수렴·연속 대역·물리 모델·실측 검증을 보장하지 않습니다.

`max_solves`는 8~32 정수이며 내부 패널 풀이가 아닌 전체 선로 시도 수입니다.
다음 세 번과 외곽 검사가 모두 예산 안에 들어야 다음 단계를 시작합니다.
`accepted`만 원 영역의 동시 세분 결과를 선택합니다.
`resolution-unaccepted`·`outer-unaccepted`는 완료됐지만 미수락이며,
`budget-exhausted`·`field-failed`는 미완료입니다. 사용자 중단은 전파합니다.
미수락 상태의 `selected_evaluation`은 모두 None입니다.

`AdaptiveShapePanelResolution.to_dict()`는 정확한 입력·행렬·비교·전체
형상전류 표본·종료 이유·선택 행 번호를 남깁니다. 전계 실패 시 이전 작업과
정확한 실패 입력을 보존하며 shape-line 원인이 있으면 원 전체/부분 전류
자료도 남깁니다. 이는 결과 보고서이며 실행 요청 저장 스키마는 아닙니다.

아래 예제는 두 단계 계획만 준비합니다. 느슨한 C0 10% 허용값은 제어 흐름
예시이며 저항이나 작은 상호항 정확도를 수락하는 기준이 아닙니다.
주석의 호출을 실행하면 전계를 계산합니다. 미수락 결과도 그대로 보존합니다.

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
# result = refine_shape_panel_line_resolution(base, **controls)  # Starts fields.
```

[저장 계획과 실행 기록](adaptive_shape_panel_resolution_document.md).
