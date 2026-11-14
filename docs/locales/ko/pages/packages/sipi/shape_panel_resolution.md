# 형상전류 선로의 분리 해상도 검사

`assess_shape_panel_line_resolution`은 명시 저장 형상전류 선로를 패널·체적 메시·
외곽 축으로 나누어 평가합니다. 원본 다음에 체적만 세분, 패널만 세분, 동시 세분,
명시 외곽 순서로 풉니다. volume/base·panel/base·joint/volume·joint/panel 네 비교를
각각 수행하고 모든 외곽 결과를 joint와 비교합니다.

선택한 `R`, `L_internal`, `L_external`, `C`, `G`, `C0`에
`ResolutionTolerance(relative, absolute)`를 지정합니다. 절대 허용값은 해당 SI
단위입니다. 모든 주파수의 모든 항이
`abs(a-b) <= absolute + relative * max(abs(a), abs(b))`를 만족해야 합니다.
작은 상호 항의 분모 하한은 없으며, 선택하지 않은 물리량은 평가하지 않습니다.
유한 관측의 일치는 절대 정확도 보증이 아닙니다.

필드 계산 전에 전체 계획을 검사합니다. 패널 제어는 명시하며 어떤 값도 줄이지
않고 하나 이상 늘려야 합니다. 체적 메시의 `edge_size`, `far_size`, `grade`만
`refinement_factor`로 줄입니다. 외곽 문서는 joint의 메시·패널 해상도와 물리 기하·
재료·포트 조건을 유지하고 접지 Fourier 모드는 늘릴 수 있습니다. 열린 옆·윗면의
패딩만 확대하며 물리 계면·도체를 움직이지 않습니다. `step_fraction`은 전 과정에서
같아야 하며 각 선로는 두 차분폭 검사도 계속 수행합니다.

`max_solves`는 정수 5~16으로, 외곽을 포함한 **전체 선로 평가 횟수**를 셉니다.
저장 선로 하나의 주파수 개수 예산이나 내부 공유 패널 풀이 횟수와 다릅니다.
예산 부족은 필드 전에 거부하고, 각 단계는 한 번씩 실행합니다. 허용차·물리 기하·
솔버 제어를 자동으로 바꾸지 않습니다.

결과는 `completed`와 `accepted`를 구분합니다. 완료됐지만 미수락이면 모든 비교를
보존합니다. 필드 실패는 후속 단계를 중단하고 이전 평가·실패 입력·단계를 남깁니다.
저장 형상전류 선로의 오류는 완료·부분 전류 이력도 `failure.details`에 보존하며,
이 속성을 읽으면 독립 복사본을 반환합니다. 중단은 전파합니다. 해당 방법의 전류
표본과 오류 세부 기록에는 결과의 `to_dict()`를 사용합니다. 기존의 일반 행렬 전용
해상도 직렬화 함수는 변경하지 않습니다.

아래 예시는 제어 흐름 확인을 위해 C0만 느슨한 10% 허용값으로 선택합니다.
저항·상호 항·물리 정확도를 검증하는 예시가 아닙니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_panel_resolution import assess_shape_panel_line_resolution
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
result = assess_shape_panel_line_resolution(base, refined_panel_options=fine,
    outer_documents=[outer], tolerances={'C0': ResolutionTolerance(.1, 0.)},
    max_solves=5)
assert result.completed and result.accepted
assert len(result.evaluations) == len(result.comparisons) == 5
assert len(result.to_dict()['evaluations'][0]['current_solver']['samples']) == 13
```

실제 legacy·코팅 선로의 다섯 단계, 균질 유전체와 독립 금속·네트워크 항등식,
작은 상호 항과 허용값 0의 미수락, 네 축 논리표, 마지막 주파수, 모든 실패 단계를
검사합니다. 기존 추출 기본값·저장 스키마·수치 수락 기준은 유지합니다.
이 직접 API에 역산이나 수율 연구를 추가하지 않습니다.

[JSON 저장과 실행 영수증](shape_panel_resolution_document.md).
