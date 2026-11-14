# 형상전류 쌍 임피던스 역산 저장

`ShapePanelForwardPairDesignDocument`는 명시적으로 선택한
[형상전류 쌍 역산](shape_panel_pair_goal.md)을
`sipi.shape-panel-forward-pair-design/1`로 저장합니다. 필수 키는 `schema`,
`design`, `step_fraction`입니다. `design`은 기존
`PanelForwardPairDesignDocument` 버전 1 또는 2이며, 버전 2는 고정 경계별
코팅 금속을 유지합니다. 기존 저장 입력과 기본 추출 방식은 바꾸지 않습니다.

정규화는 필드를 풀지 않습니다. 기본값과 초기값/중점 외에 네 변수 경계 조합,
각각의 체적·패널·동시 세분 입력도 형상전류 문서로 검사합니다. 미계산 경계
조합에서 미분용 도체 이동이 충돌해도 거부합니다. 이러한 유한 검사가 연속
범위의 모든 점이나 미래 메시·필드 계산의 유효성을 보증하지는 않습니다.
알 수 없는 키·누락·중복·비유한 입력도 중첩 계약에 따라 거부합니다.

`solve()`는 중첩 저장 평가 예산을 사용합니다. 공통 실행은 호출자
`max_evaluations`가 저장 예산보다 작으면 필드 전에 거부하고 탐색 예산을
조용히 줄이지 않습니다. 예산은 탐침·실패를 포함한 캐시되지 않은 선로 전체
평가 횟수이며 내부 패널 풀이·실행 시간이 아닙니다. 원래 두 목표 허용값과
세 독립 세분 검사 모두 필요합니다. 외곽 영역 검증은 별도입니다.

실행 성공은 선택·세분 전류 표본, 전체 입력 이력과 목표를 보존합니다.
실패한 목표는 null 결과와 평가 횟수·단계·실패 변수/입력·완료 이력이 있는
형식 있는 오류를 반환합니다. 원인이 `ShapePanelLineError`이면 `cause_details`에
완료·부분 전류 작업을 보존합니다. 실패를 수락된 설계로 해석하지 않습니다.
중단은 전파합니다. `SavedExecutionRecord`는 두 영수증 모두 저장하고 필드 없이
불러오기/준비를 합니다. 기존 기록 크기 제한과 호스트 아티팩트 선언 의미를 유지합니다.

예제는 필드를 풀지 않고 요청을 준비·정규화합니다. 실제 범위 제한 풀이를
시작하려면 `prepared.run()`을 호출합니다. 정규화 성공은 수렴이나 정확도 통과가 아닙니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.pair_line_goal_document import ForwardPairDesignDocument
from sipi.panel_pair_goal_document import PanelForwardPairDesignDocument
from sipi.shape_panel_pair_goal_document import ShapePanelForwardPairDesignDocument
from sipi.execution import normalize_saved
from sipi.execution_request import SavedExecutionRequest

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         air_height=.01, box_width=.024),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))
quantities = ('differential_forward_impedance_real',
              'common_forward_impedance_real')
original = ForwardPairDesignDocument(study, conductor={'kind': 'perfect'},
    targets=dict(zip(quantities, [110., 40.])),
    tolerances=dict(zip(quantities, [.25, .125])),
    initial=[.7e-3, .35e-3], max_evaluations=64)
saved = ShapePanelForwardPairDesignDocument(
    PanelForwardPairDesignDocument(original), step_fraction=.001)
text = saved.dumps()
assert normalize_saved(text) == text
prepared = SavedExecutionRequest(text, max_evaluations=64)
assert prepared.to_dict()['input'] == saved.to_dict()
# receipt = prepared.run()  # Starts actual fields and bounded optimization.
```

[English](../../../../../packages/sipi/shape_panel_pair_goal_document.md)
