# 제한된 패널 세분 계획 저장

`AdaptivePanelResolutionDocument`는 명시적인
`sipi.adaptive-panel-resolution/1` 계약을 저장합니다. 최상위 여섯 키는 schema,
line, refinements, tolerances, refinement_factor, max_solves입니다.
2~4개의 각 단계는 refined_panel과 outer_lines 두 키만 가집니다.
중첩 패널 선로 /1·/2의 도체 방법을 보존합니다. 허용차 키는 SI 단위의
R_ohm_per_m, L_internal_h_per_m, L_external_h_per_m, C_f_per_m,
G_s_per_m, C0_f_per_m 중 선택하며 relative와 absolute를 명시합니다.
알 수 없는 키·빠진 키·중복 키·비유한 JSON 숫자를 거부합니다.

정규화는 전체 계획을 전계 계산 없이 검증합니다. 직접 API의 두 세분 축,
두 연속 수락, 물리 입력 보존, 독립 외곽 검사와 유한 차이의 한계를 유지합니다.
호출 예산이 7+외곽 개수보다 작으면 계산 전에 거부하고, 그 외에는 저장 예산과
호출 예산 중 작은 값을 사용합니다. 계획·메시·허용차를 암묵적으로 수정하지
않습니다. 기존 panel-resolution/1과 line-resolution 문서는 그대로입니다.

execute_saved는 완료한 입력·결과·비교를 모두 보존합니다. 전계 실패는 failed와
정확한 오류·부분 결과를, 예산 소진은 failed와 ResolutionBudgetExceeded·부분 결과를
반환합니다. 계산 완료·수치 미수락은 complete/error null/accepted false입니다.
수락된 결과만 selected_evaluation_index를 가집니다. refinement_levels, stop_reason,
outer_completed로 종료 상태를 구분합니다. 사용자 중단은 전파하며, 결과에는 수락
대상으로 선택하지 않은 양도 포함해 지원하는 모든 SI 행렬을 보존합니다.

다음 실행 예제는 저장·재생을 보이기 위해 C0만 느슨한 10% 관측 허용차로 선택합니다.
물리 정확도·저항 수락·연속 대역 수렴·절대오차 상한을 증명하는 예제가 아닙니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_panel_resolution import (
    PanelResolutionRefinement, refine_panel_line_resolution,
)

section = CrossSection([Layer('uniform', .002, 4.2)],
    [Trace('left', -.0003, .0005, .0002, thickness=35e-6),
     Trace('right', .0003, .0005, .0002, thickness=35e-6)], .004)
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={}, conductor={'kind': 'perfect'}, length=0.)
base = PanelTransmissionLineDocument(line, panels_per_edge=8)
steps = []
for level in (1, 2):
    raw = base.to_dict()
    options = dict(base.panel_options, panels_per_edge=8 * 2**level)
    raw['panel'] = dict(options, ground_modes=1024)
    cross = raw['line']['cross_section']
    cross['box']['width'] *= 2
    cross['layers'][-1]['thickness'] *= 2
    for key in ('edge_size', 'far_size', 'grade'):
        cross['mesh'][key] *= .5**level
    steps.append(PanelResolutionRefinement(
        options, [PanelTransmissionLineDocument.from_dict(raw)]))
from sipi.adaptive_panel_resolution_document import AdaptivePanelResolutionDocument
from sipi.execution import normalize_saved, execute_saved

request = AdaptivePanelResolutionDocument(base, refinements=steps,
    tolerances={'C0': ResolutionTolerance(.1, 0.)}, max_solves=8)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=8)
assert output['status'] == 'complete' and output['error'] is None
assert output['result']['accepted']
assert output['result']['selected_evaluation_index'] == 6
assert len(output['result']['evaluations']) == 8
```
