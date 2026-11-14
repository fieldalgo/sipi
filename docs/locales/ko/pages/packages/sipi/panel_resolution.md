# 패널 선로의 항별 해상도 검사

[저장 요청](panel_resolution_document.md)은 같은 분리 축 결과를 공통 실행에 보존합니다.

`assess_panel_line_resolution`은 패널 제어값·유전체 체적 메시·유한 외곽을
따로 비교합니다. 패널 선로의 두 버전을 모두 받으며 선택한 전류 방식을
보존합니다. 요청한 허용차를 전체 행렬 규준으로 대체하지 않습니다.

세분할 패널 제어값 세 개와 명시적인 확장 외곽 문서를 제공합니다. 어떤
패널 제어값도 줄어들 수 없고 적어도 하나는 증가해야 합니다. 체적 세분은
`edge_size`, `far_size`, `grade`를 줄입니다. 외곽 문서는 동시 세분 메시·패널
수·보간 차수를 사용하며 접지 모드 수는 유지하거나 늘릴 수 있습니다.
물리 계면·신호 기하·금속·유전체·주파수·포트를 보존해야 합니다. 실제 접지면을
옮기는 것을 외곽 세분으로 처리하지 않습니다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution import assess_panel_line_resolution
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import resolution_record

section = CrossSection([Layer("uniform", .002, 4.)],
    [Trace("signal", 0., .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={"kind": "perfect"}, length=.02)
base = PanelTransmissionLineDocument(line, panels_per_edge=16)
fine = dict(panels_per_edge=32, ground_modes=1024, interpolation_degree=12)
raw = base.to_dict()
raw["panel"] = dict(fine, ground_modes=2048)
cross = raw["line"]["cross_section"]
cross["box"]["width"] *= 2
cross["layers"][-1]["thickness"] *= 2
for key in ("edge_size", "far_size", "grade"):
    cross["mesh"][key] *= .5
report = assess_panel_line_resolution(base, refined_panel_options=fine,
    outer_documents=[PanelTransmissionLineDocument.from_dict(raw)],
    tolerances={"C0": ResolutionTolerance(.005, 0.)}, max_solves=5)
saved_report = resolution_record(report)
assert report.completed
```

전체 선로 계산은 기본·체적만 세분·패널만 세분·동시 세분·각 외곽을 한 번씩
수행합니다. 체적·패널 결과는 각각 기본과, 동시 세분은 체적·패널 각각과,
외곽은 동시 세분과 비교합니다. `reference_index`, `evaluation_index`가 이
구분을 보존합니다. 외곽 문서는 하나 이상이어야 하며 `max_solves`가
`4 + len(outer_documents)`를 수용하는지 전계 계산 전에 검사합니다. 상한은 16입니다.

[SI 허용차 계약](line_resolution.md)에 따라 R·내부 L·외부 L·C·G·C0 중
하나 이상을 선택합니다. 모든 주파수와 행렬 원소에서
`abs(b-a) <= absolute + relative*max(abs(a), abs(b))`를 검사합니다.
작은 상호항에 임의 분모 하한을 두지 않습니다. 비교 미충족은 기록에 남기고
나머지 계획된 평가는 계속합니다. 전계 실패는 후속 평가를 중단하며 정확한
입력·단계·오류를 보존합니다. 사용자 중단은 전파합니다. `completed`와
`accepted`는 별개이므로 전체 계산이 끝나도 요청 조건은 미충족일 수 있습니다.

결과는 `PanelResolutionAssessment`이며 `resolution_record`로 일반 JSON 호환
결과를 저장할 수 있습니다. 실행 요청은 위에 연결한 `PanelResolutionDocument`
래퍼로 저장합니다. 입력 기록에 패널 설정과 내부 선로가 모두 포함됩니다. 기존
선로 해상도 저장 요청은 그대로 유지됩니다.

결과는 유한 차이이며 절대 전계 오차 상한이나 무한 영역 한계가 아닙니다.
허용차 추정·물리 영역 자동 확장·재료 피팅·실측 정확도 인증을 하지 않습니다.
[작은 상호 저항 관측](layered_panel_line.md)은 전체 행렬 변화만으로 모든
용도의 정밀도를 판정할 수 없는 이유를 보여 줍니다.

[English](../../../../../packages/sipi/panel_resolution.md)
