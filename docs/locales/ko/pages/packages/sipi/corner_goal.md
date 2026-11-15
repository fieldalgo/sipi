# 모서리 해상도를 지정한 목표 임피던스

`seek_corner_impedance`는 기존의 구간 제한 단일 변수 임피던스 역산에
미터 단위 `corner_size`를 명시적으로 적용합니다. `mesh` 안이 아닌
별도 인자로 지정해야 합니다. 각 평가에서 유한한 양수이며 해석된
`edge_size`보다 클 수 없습니다.

```python
from sipi import stripline, seek_corner_impedance

def section(width):
    return stripline(width=width, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)

options = dict(corner_size=2.5e-6,
    mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15),
    tolerance=.1, search_tolerance=.025, max_evaluations=12)
# result = seek_corner_impedance(section, (.00055, .00065), 44.3, **options)
```

기존 끝점 검사·부호 구간·이분법·평가 예산·계산량 정의·재료 옵션과
`return_line=True`를 그대로 적용합니다. 값을 선택한 뒤에는 저장된 기하와
선택 재료를 그대로 사용합니다. 최종 계산은 `corner_size`, `edge_size`,
`far_size`, `grade`를 모두 절반으로 줄이고 각도 설정은 유지합니다.
원래 메시 결과는 `search_tolerance`(생략하면 `tolerance`), 세분 결과는
`tolerance` 이내여야 합니다. 역산 실패나 세분 불일치의 이력도 보존합니다.

결과의 문서는 `CornerCrossSectionDocument`입니다. 내포된 원래 단면만
저장하면 모서리 목표가 빠지므로 전체 입력을 저장하세요. 재료를
대체했다면 `material_evaluation_json`도 함께 보존해야 합니다. 반환
선로 행렬은 선택된 원래 메시의 읽기 전용 사본이며 세분 메시의 행렬이
아닙니다. 선로를 요청해도 세분 결과 검증을 생략하지 않습니다.

`GoalMeshSizeLimitError`는 원래 원인·완료 이력·실패 변수와 단계·해석된
모서리 단면 입력을 보존합니다. 이 함수나 오류 처리는 메시·평가 한도를
늘리지 않습니다. 기존 `seek_impedance`와 목표 저장 스키마는 기존 메시
계약을 유지합니다. 모서리 목표 저장은 별도의 [명시적 목표 문서](corner_goal_document.md)를 사용합니다.

실제 폭과 균일 재료 역산에서 양쪽 목표 오차, 명시적 세분, 독립 이차
정전용량, 균일 유전체 임피던스 관계를 검증합니다. 이 유한 검사는 모든
팩토리의 수렴, 전역 최적값, 외곽 수렴, 도체 손실 정확도를 인증하지 않습니다.

[English](../../../../../packages/sipi/corner_goal.md)
