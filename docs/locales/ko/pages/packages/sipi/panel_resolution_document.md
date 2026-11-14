# 패널 해상도 요청 저장

`PanelResolutionDocument`는 기존 [항별 패널 평가](panel_resolution.md)를
엄격한 `sipi.panel-resolution/1`로 저장합니다. 키는 `schema`, `line`,
`outer_lines`, `refined_panel`, `refinement_factor`, `max_solves`,
`tolerances`입니다. 내부 선로는 패널 선로 버전 1 또는 2이며 선택한 방법과
물리 문제를 모두 보존해야 합니다. 정규화 중 전계 계산은 하지 않습니다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_resolution_document import PanelResolutionDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.execution import execute_saved

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
request = PanelResolutionDocument(base, refined_panel_options=fine,
    outer_documents=[PanelTransmissionLineDocument.from_dict(raw)],
    tolerances={"C0": ResolutionTolerance(.005, 0.)}, max_solves=5)
text = request.dumps()
assert PanelResolutionDocument.loads(text).dumps() == text
response = execute_saved(text, max_evaluations=5)
assert response["status"] == "complete"
assert response["result"]["expected_evaluations"] == 5
```

허용차 키는 SI 물리량을 명시합니다. `R_ohm_per_m`, `L_internal_h_per_m`,
`L_external_h_per_m`, `C_f_per_m`, `G_s_per_m`, `C0_f_per_m` 중 선택하며
각각 `relative`, `absolute`가 필요합니다. 단위 추정·전체 행렬 정규화·작은
항의 분모 하한은 없습니다. 미지원·누락·중복 키와 비유한 값을 거부합니다.

`max_solves`는 5–16이며 네 가지 분리 축 평가와 모든 외곽 입력을 수용해야
합니다. 공통 `max_evaluations`도 전체 선로 평가 횟수를 제한합니다. 두 예산을
모두 전계 계산 전에 확인합니다. 세분 패널 제어와 외곽 물리 조건은 직접
API와 같으며 기하·재료·제어값을 임의로 고치지 않습니다.

결과에는 정확한 패널 선로 입력·주파수·신호 순서·여섯 물리량·비교 인덱스·차이·
허용량이 보존됩니다. 계산이 끝나도 `accepted=false`일 수 있으며 이 경우
`status=complete`, 실행 오류 없음으로 반환합니다. 전계 예외는 `status=failed`와
부분 결과를 남기고 정확한 입력·단계·오류를 `error`에도 보존합니다. 사용자
중단은 전파합니다. 소비자는 계산 완료와 조건 수락을 모두 확인해야 합니다.

기본·체적만 세분·패널만 세분·동시 세분·외곽 평가는 구분됩니다. 동시 세분은
각 단독 세분과 별도로 비교하고 외곽은 동시 세분과 비교합니다. 이 유한한
항별 차이는 절대 오차·무한 외곽·실측 정확도를 인증하지 않습니다. 기존 패널
기하·금속·준 TEM 제한도 적용됩니다.

[English](../../../../../packages/sipi/panel_resolution_document.md)
