# 예산을 제한한 메시 자동 세분

`refine_line_resolution`은 기존 선로 계산을 단계적으로 더 세밀한 메시에서
실행합니다. 명시한 허용차를 연속 두 번의 원소별 비교가 충족해야 외곽
검사를 진행합니다. 실패 비교를 보존하며 수락을 위해 허용차를 바꾸지 않습니다.

```python
from sipi import stripline, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_resolution import ResolutionTolerance
from sipi.adaptive_line_resolution import refine_line_resolution

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                    eps_r=4., box_width=.008)
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=5e-6, far_size=.2e-3, grade=.1)), [1e9],
    materials={}, conductor={'kind': 'perfect'}, length=.02)
larger = line.to_dict()
larger['cross_section']['box']['width'] = .016
for key in ('edge_size', 'far_size', 'grade'):
    larger['cross_section']['mesh'][key] *= .5
report = refine_line_resolution(line,
    outer_documents=[TransmissionLineDocument.from_dict(larger)],
    tolerances={'C': ResolutionTolerance(.005, 0.)}, max_levels=3, max_solves=6)
accepted_input = report.selected_evaluation
```

외곽 템플릿은 일반 [해상도 평가](line_resolution.md)와 같이 첫 세분 메시
설정을 사용합니다. 인접 메시 비교가 연속 두 번 통과하면 이 템플릿의 메시
설정만 선택한 단계의 값으로 바꿉니다. 각 외곽을 원 영역의 선택된 세분
결과와 비교합니다. 외곽 기준 미충족 시 `outer-unaccepted`로 정지하며,
물리 경계를 이동하거나 외곽 차이를 감추려고 메시만 계속 줄이지 않습니다.

`max_levels`는 2~8, `max_solves`는 4~16입니다. 전체 선로 평가를 한 번씩
세고 기존 결과는 재사용합니다. 다음 세분 계산 전에 그 계산과 모든 필수
외곽 검사를 남은 예산으로 할 수 있는지 확인합니다. 기존 메시 자원 한도도
유지합니다. 솔버·준비 단계 실패는 정확한 시도 입력과 단계를 남기며 사용자
중단은 그대로 전달합니다.

`stop_reason`은 `accepted`, `mesh-unaccepted`, `outer-unaccepted`,
`budget-exhausted`, `field-failed` 중 하나입니다. 뒤 두 경우는 `completed`가
거짓이며 계산이 완료돼도 수락하지 못할 수 있습니다. `outer_completed`로
외곽 비교가 모두 수행됐는지 별도로 확인합니다. `evaluations`와 `comparisons`는
완료 결과와 원소별 차이·허용량을 보존합니다. `mesh_levels`는 실패 시도를
포함한 세분 단계 수입니다. 수락했을 때 `selected_evaluation`은 원 영역의
선택된 세분 결과이며, 아니면 `None`이고 전체 이력은 계속 남습니다.

수락은 선택한 물리량과 입력 주파수에만 해당합니다. 두 유한 비교가 절대
오차·점근 수렴·선택하지 않은 작은 상호 항·실측 정확도를 보증하지 않습니다.
기존 추출 방법, 물리 입력, 저장 요청 스키마와 수치 시험 기준은 유지합니다.
명시 예산을 사용하는 별도 Python API입니다.

[English](../../../../../packages/sipi/adaptive_line_resolution.md)
