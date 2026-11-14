# 저장 가능한 선로 해상도 평가

`sipi.line-resolution/1`은 [유한 메시·외곽 평가](line_resolution.md)의 원
선로, 명시 외곽 선로, 세분 인자, 계산 예산, 선택한 SI 허용차를 저장합니다.
내부 선로는 transmission-line/1~7이며 정규화와 사전 검사에서는 전계를 풀지
않습니다.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.line_resolution_document import LineResolutionDocument
from sipi.execution import normalize_saved

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = line.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
request = LineResolutionDocument(line,
    outer_documents=[TransmissionLineDocument.from_dict(larger)],
    tolerances={'C': ResolutionTolerance(.005, 0.)}, max_solves=3)
assert normalize_saved(request.dumps()) == request.dumps()
```

JSON 키는 `schema`, `line`, `outer_lines`, `refinement_factor`, `max_solves`,
`tolerances`입니다. 허용차 키에는 단위를 명시합니다: `R_ohm_per_m`,
`L_internal_h_per_m`, `L_external_h_per_m`, `C_f_per_m`, `C0_f_per_m`,
`G_s_per_m`. 하나 이상을 선택하고 각각 `relative`와 `absolute`를 넣습니다.
절대값은 상위 키의 SI 단위입니다. 잘못된 단위·필드·버전·중복 키·비유한
값을 거부하며 단위나 허용차 하한을 자동으로 변환하지 않습니다.

`request.analyze()`는 직접 API와 같은 평가 결과를 반환합니다.
`execute_saved(request.dumps(), max_evaluations=3)`는 입력·단계·6종 물리
행렬·선택한 차이와 허용량을 JSON으로 반환합니다. 공통 예산과 저장한
`max_solves` 모두 원+세분+외곽의 전체 선로 평가 횟수를 계산 전에 제한합니다.

결과는 `completed`와 `accepted`를 구분합니다. 계산은 끝났지만 유한 허용차를
충족하지 못하면 실행 `status='complete'`, `result.accepted=false`입니다.
전계 계산 실패는 `status='failed'`이며 완료 평가·비교와 실패 단계·정확한
입력·예외 종류·메시지를 보존합니다. 이후 계산은 실행하지 않습니다. 원본
입력은 바꾸지 않으며 사용자 중단은 그대로 전달합니다.

수락은 선택한 물리량과 입력한 주파수에만 적용합니다. 절대 오차 추정이
아니며 C 허용차를 만족했다고 R 정밀도를 보장하지 않습니다. 기존 계산법,
해결되지 않은 수렴 실패, 독립 기준 대조 조건과 다른 저장 입력은 유지합니다.

[English](../../../../../packages/sipi/line_resolution_document.md)

## 자동 세분 요청

[버전 2](adaptive_resolution_document.md)는 예산 있는 메시 자동 세분을 저장하고 예산 소진과 계산 완료 후 미수락을 구분합니다.
