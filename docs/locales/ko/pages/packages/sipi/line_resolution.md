# 명시적 메시·외곽 평가

`assess_line_resolution`은 저장 선로를 원 메시, 세분 메시, 명시적으로
확장한 외곽에서 계산합니다. 선택한 양과 허용차에 대한 유한 변화의 일치
여부를 보고합니다. 절대 정확도를 인증하거나 검사 통과를 위해 계산을
바꾸지 않습니다.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import assess_line_resolution, ResolutionTolerance

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
base = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = base.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
outer = TransmissionLineDocument.from_dict(larger)
report = assess_line_resolution(base, outer_documents=[outer], max_solves=3,
    tolerances={'C': ResolutionTolerance(relative=.005, absolute=0.)})
assert report.completed
accepted_for_capacitance = report.accepted
```

선로는 이미 확정한 메시 기본값을 저장합니다. `edge_size`, `far_size`,
`grade`만 `refinement_factor`(기본 0.5)로 줄입니다. 각 외곽 입력은 이 세분
설정을 동일하게 사용하고 신호·내부 계면·재료·주파수·포트를 보존해야 합니다.
열린 옆면의 폭 또는 열린 윗면 아래 마지막 층의 높이만 늘릴 수 있습니다.
영역 축소나 물리적 접지벽·접지면 이동은 계산 전에 거부합니다.

`R`(ohm/m), `L_internal`·`L_external`(H/m), `C`·`C0`(F/m), `G`(S/m) 중
하나 이상을 선택하고 각 양에 `ResolutionTolerance`를 명시합니다.
모든 주파수·행렬 원소에
`abs(b-a) <= absolute + relative*max(abs(a), abs(b))`를 적용합니다.
두 허용차가 모두 0이면 정확한 일치를 요구합니다. 작은 상호 항도 개별
검사하며 임의의 분모 하한을 넣지 않습니다. 절대 허용차는 선택한 양의 SI
단위입니다. 선택하지 않은 양은 평가하지 않으며 C의 일치가 R의 일치를
뜻하지 않습니다.

첫 `comparisons`는 원 메시와 세분 메시를 비교하고 이후 항목은 각 외곽과
세분 결과를 비교합니다. 읽기 전용 `differences`와 `allowances`에 모든
행렬 원소를 남깁니다. `evaluations`에는 단계별 정확한 입력 JSON과 기존
선로 결과가 남으며 원본 입력은 바뀌지 않습니다.

`completed`는 요청한 계산이 모두 끝났다는 뜻입니다. `accepted`는 선택한
비교 조건까지 모두 충족해야 참입니다. 계산이 끝나도 수락하지 못할 수
있습니다. 솔버 실패 시 후속 계산을 중단하고 완료 결과와 `failure.stage`,
`input_json`, `kind`, `message`를 보존합니다. `max_solves`는 원·세분을
포함한 전체 선로 평가 횟수이며 계산 전에 검사합니다. 내부 선형 해법 횟수를
별도로 세지 않습니다. 사용자 중단은 그대로 전달합니다.

유한 변화는 점근 수렴, 재메시 잡음 제거, 미표본 주파수의 정확도를 보증하거나
독립 전계·실측 대조를 대체하지 않습니다. 이번 Python API는 새 저장 요청
스키마를 추가하거나 기존 실행 기본값을 바꾸지 않습니다.

[English](../../../../../packages/sipi/line_resolution.md)
