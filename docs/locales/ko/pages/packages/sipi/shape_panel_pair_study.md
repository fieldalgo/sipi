# 명시 형상전류를 사용하는 제조 공차 표본

[명시 동시 조건 만족률](shape_panel_pair_yield.md)은 표본의 전류 근거를 그대로 보존합니다.

[English](../../../../../packages/sipi/shape_panel_pair_study.md) ·
[전류 방식](shape_panel_line.md) · [기존 표본 계약](panel_pair_study.md)

`ShapePanelForwardPairStudyDocument`는 쌍 선로 제조 표본에 정전용량 형상미분
전류를 명시적으로 선택합니다. 엄격한 `sipi.shape-panel-forward-pair-study/1`
JSON의 루트 키는 `schema`, `study`, `step_fraction`뿐입니다. 내부
`PanelForwardPairStudyDocument`는 버전 1 또는 고정 코팅 경계용 버전 2입니다.
기존 문서의 계산 방식은 유지합니다. 기하·재료 변수 순서, 상관, 고정 피치,
난수 시드와 명목 메시 제어를 보존하며 한 양의 주파수에서 서로 다른 여기 정의의
차동·공통 순방향 임피던스 실수부를 계산합니다. 비대칭 교차항도 유지합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.shape_panel_pair_study import ShapePanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = PanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    panels_per_edge=16, ground_modes=512, interpolation_degree=16)
document = ShapePanelForwardPairStudyDocument(panel, step_fraction=1e-3)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
assert ShapePanelForwardPairStudyDocument.loads(document.dumps()).dumps() == document.dumps()
assert len(document.samples()) == 3
# receipt = request.run()  # Runs all three field extractions.
```

정규화는 전계 계산 없이 명목 단면의 이동 경계를 검사하며 모든 표본의 유효성을
미리 보장하지 않습니다. 중복을 포함한 원래 표본을 순서대로 한 번씩 시도합니다.
잘못된 기하·재료·이동 경계는 실패 행으로 남기고 후속 행을 계속 계산합니다.
전체 표본 수가 정수 2..10000인 `max_evaluations` 안에 들어야 전계 계산을
시작합니다. 예산은 개별 패널 풀이가 아니라 선로 추출 횟수이며, 한 표본에
여러 내부 전류 풀이가 포함됩니다.

완료한 추출의 전체 `current_solver` 기록은 후속 진단이 실패해도 보존합니다.
형상 선로 실패의 단계별 부분 근거는 `cause_details`에, 일반 오류는 단계·종류·
메시지에 보존합니다. 얻지 못한 근거는 null입니다. 실패 행도 원래 분모에 남고
하나라도 실패하면 전체 기술통계 요약은 null입니다. 표본을 버리거나 다시 뽑지
않습니다. 공통 실행은 실패 행이 있으면 전체 행과 함께 `incomplete`를 반환하고,
요청·기록·프로젝트를 저장하고 복원할 때 재계산하지 않습니다.

이 결과는 기술통계이며 생산 수율 보증이 아닙니다. 기존 쌍 수율 저장 문서는
이 스키마를 암묵적으로 받지 않습니다. 명목 메시·패널 제어·상대 이동폭은 표본
전체에서 고정하지만 기하 메시는 다시 생성합니다. 표본마다 해상도를 자동
인증하지 않으며 바닥 접지·열린 상부/측면·이동 경계 제한이 그대로 적용됩니다.

## 검증 범위

독립 모달 구성과 통계로 순서·상관·중복·고정 피치·실패·예산을 검사합니다.
벌크 및 고정 코팅 금속의 실제 진공 유전체 모서리 조합 각 4개로 C=C0, G=0,
외부 LC, 독립 금속 전달식과 4포트 행렬지수를 검사합니다. 선택한 두 조합은
패널·체적·동시 세분과 유한 외곽 관측을 따로 남깁니다. 전체 행렬 비교는 작은
상호항이나 절대 오차의 상한이 아니며 모든 표본·재료·기하·주파수의 인증이 아닙니다.

최초 8/16/32 mm 외곽은 저항 변화 0.1% 기준을 **충족하지 않습니다**. 첫 변화는
약 0.55%, 0.60%이며 이 결과는 미수락 반례로 남깁니다. 별도 32/64/128 mm
전류 전용 비교는 같은 전체 행렬 기준을 충족하고 128 mm의 모드·패널 세분도
독립 대조합니다. 큰 영역 검사는 유전체 체적 메시를 계산하거나 원래 작은
영역 선로의 모든 항을 인증하지 않습니다. 기술통계 분석은 요청한 유한 영역의
결과를 반환하며 수렴한 결과로 바꾸어 표시하지 않습니다.
