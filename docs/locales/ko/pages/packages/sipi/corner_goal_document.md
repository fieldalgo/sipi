# 모서리 해상도를 명시한 임피던스 역산 저장

`CornerImpedanceDesignDocument`는 범위가 있는 임피던스 역산 입력과 별도
모서리 목표를 함께 저장합니다. 엄격한 `sipi.corner-impedance-design/1`
JSON의 키는 `schema`, `design`, `corner_size` 세 개입니다. 내포된 기존
목표 문서 버전 1–4의 단위, 기하·재료 변수, 계산량, 허용오차와 평가
예산을 유지합니다. 모서리 목표는 미터 단위의 유한 양수이며 해석된
edge 크기 이하여야 합니다.

```python
from sipi import ImpedanceDesignDocument, CornerImpedanceDesignDocument
from sipi.execution import normalize_saved

design = ImpedanceDesignDocument(
    'stripline', dict(width=.0006, plane_spacing=.002, eps_r=4.,
                     thickness=.0004, box_width=.008),
    variable='width', bounds=[.00055, .00065], target=44.3,
    tolerance=.1, search_tolerance=.025, max_evaluations=12,
    mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15))
saved = CornerImpedanceDesignDocument(design, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.solve()
```

불러오기와 정규화는 장 풀이 없이 입력을 검사하며 접근자는 분리된
사본을 반환합니다. 실행은 [명시적 모서리 역산](corner_goal.md)을
사용합니다. 선택된 입력을 유지한 채 edge·far·grade·corner를 절반으로
줄이는 필수 세분 검사를 수행합니다. 원래 메시와 세분 메시의 목표
오차가 각각 기존 허용오차를 만족해야 합니다. 범위가 있는 단일 변수
역산이며 전역 최적화를 의미하지 않습니다.

공통 저장 실행기, 요청, 실행 기록, 프로젝트에서 이 스키마를 사용할
수 있습니다. 호스트 평가 예산은 풀이 전에 검사합니다. 성공 결과는
선택된 모서리 단면 문서와 세분 이력을 담습니다. 실패한 역산은 유형과
이력을 보존하고 메시 한도 실패는 해당 입력·단계·시도 횟수·원인도
보존합니다. 기록을 다시 열어도 장을 다시 풀지 않습니다. 모서리 목표를
수정하면 현재 결과 연결은 해제하고 과거 기록은 유지합니다. 실행 기록에는
실제 계산물의 해시를 제공해야 하며 입력만으로 계산 빌드를 식별할 수는 없습니다.

기존 목표·단면 스키마는 메시 딕셔너리 안의 corner 키를 계속 거부합니다.
재현 가능한 모서리 역산에는 이 명시적 문서를 사용하세요. 실제 폭·재료
역산은 직접 API와 정확히 같은 결과를 내며 저장 전달 검사는 측정 결과를
명시적으로 재사용합니다. 이 검사는 모든 기하의 수렴, 외곽 독립성,
도체 손실 정확도나 새로운 플랫폼 지원을 인증하지 않습니다.

[English](../../../../../packages/sipi/corner_goal_document.md)
