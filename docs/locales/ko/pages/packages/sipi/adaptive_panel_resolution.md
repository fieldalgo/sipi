# 패널·체적 메시의 제한된 적응 세분

`refine_panel_line_resolution`은 사용자가 명시한 2~4개 세분 단계를 실행합니다.
각 `PanelResolutionRefinement(panel_options, outer_documents)`는 다음 패널 설정과
그 단계의 세분 메시를 사용하는 외곽 문서를 지정합니다. 모든 계획을 전계 계산 전에
검사합니다. 패널 설정은 감소할 수 없고 하나 이상 증가해야 합니다. 체적 메시의
edge_size, far_size, grade는 같은 refinement_factor로 감소합니다. 외곽의 물리 크기와
순서는 단계마다 같아야 하며, 그 단계의 패널 설정을 유지하되 ground_modes는 늘릴 수
있습니다. 재료·도체·포트·주파수는 보존합니다. 두 패널 선로 스키마를 지원합니다.

단계마다 체적만, 패널만, 둘 다 세분한 세 결과를 계산합니다. 이전 단계의 공동 세분
결과를 다음 기준으로 재사용합니다. 체적/기준, 패널/기준, 공동/체적, 공동/패널의
네 비교가 모두 통과해야 합니다. 두 연속 단계가 통과한 뒤 해당 단계의 외곽들을
별도로 계산합니다. 중간 실패는 연속 횟수를 초기화하고 외곽 불일치는 즉시 종료합니다.

선택한 양의 SI 단위로 `ResolutionTolerance(relative, absolute)`를 지정합니다.
모든 주파수·행렬 원소에서 `abs(a-b) <= absolute + relative * max(abs(a), abs(b))`를
검사하며 작은 상호 성분의 분모를 임의로 키우지 않습니다. 선택하지 않은 양은
검사하지 않습니다. 두 번의 유한 차이 수락도 절대오차 상한·점근 수렴·연속 대역 보장·
실측 정확도를 뜻하지 않습니다.

max_solves는 8~32 정수로 전체 선로 평가 횟수입니다. 내부 선형 풀이 횟수가 아닙니다.
다음 세 평가와 모든 외곽 평가가 예산에 들어가야 단계가 시작됩니다. 불변 결과는
실제 입력·결과·비교를 모두 보존합니다. accepted만 원래 영역의 공동 세분 결과를
selected_evaluation으로 선택합니다. resolution-unaccepted와 outer-unaccepted는
실행 완료·미수락이고 budget-exhausted와 field-failed는 실행 미완료입니다. 미수락이면
선택 결과는 None입니다. 실패 입력과 앞선 결과를 보존하며 사용자 중단은 전파합니다.
물리 입력이나 허용차를 자동 수정하지 않습니다. 사용하지 않을 후속 명시 단계도
사전 검사하지만 전계 계산은 하지 않습니다.

아래 예제는 제어 흐름을 보이기 위해 C0만 느슨한 10% 관측 허용차로 검사합니다.
저항이나 작은 상호 성분의 정확도 수락 근거가 아닙니다. 물리 수락 기준은 별도로
정하고 미수락 결과도 보존해야 합니다.

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
result = refine_panel_line_resolution(base, refinements=steps,
    tolerances={'C0': ResolutionTolerance(.1, 0.)}, max_solves=8)
assert result.completed and result.accepted and result.outer_completed
assert result.selected_evaluation is result.evaluations[6]
assert len(result.evaluations) == 8
```

검증은 기존/고정 코팅 입력, 균일 유전체 불변식, 독립 코팅 전달행렬과 네트워크 식,
실제 저항 미수락, 두 연속 네 비교·초기화·정확한 예산·실패·중단을 포함합니다.
이 API는 추출 방법이나 기존 수치 기준을 바꾸지 않으며 앞선 표면전류 정확도 실패를
해결한 것으로 취급하지 않습니다.
