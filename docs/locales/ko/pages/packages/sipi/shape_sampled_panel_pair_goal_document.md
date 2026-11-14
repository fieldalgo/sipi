# 유한 주파수 형상전류 쌍 목표 저장

`ShapeSampledPanelForwardPairDesignDocument`는
[유한 주파수 형상전류 역산](shape_sampled_panel_pair_goal.md)을
`sipi.shape-sampled-panel-forward-pair-design/1`로 명시적으로 저장합니다.
필수 키는 `schema`, `design`, `step_fraction`입니다. `design`에는 기존
`SampledPanelForwardPairDesignDocument` 버전 1 또는 2를 넣습니다.
버전 2는 경계별 고정 코팅 금속 모델을 보존합니다. 기존 입력과 기본 전류
계산 방식은 바뀌지 않습니다.

증가하는 양의 주파수 2~64개 각각에 차동·공통 순방향 임피던스 실수부의
양의 목표와 허용차를 지정합니다. 단위는 Ω이며 키는
`differential_forward_impedance_real`, `common_forward_impedance_real`입니다.
배열 길이는 주파수 수와 같아야 하며 단일 값을 자동 복제하지 않습니다.
기준 study 주파수는 첫 표본과 같아야 합니다. 양의 유계 변수 두 개의 순서,
고정 피치·재료 변수와 전체 주파수 계약은 중첩 입력을 그대로 따릅니다.

정규화는 전계를 풀지 않습니다. 명목·초기점(미지정 시 중점)·네 모서리와
미래 체적/패널/동시 세분 입력을 검사합니다. 형상 이동 충돌과 전체 재료
주파수 범위도 검사하지만 연속 내부 영역의 모든 점이 계산 가능함을
보장하지 않습니다. 누락·추가·중복 키와 비유한 값을 거부합니다.

`solve()`는 저장된 예산·격자·목표·허용차를 직접 API에 전달합니다.
선택 결과와 세 세분 결과 모두 모든 주파수의 목표를 만족해야 하며 기존
상대 세분 기준도 그대로 적용합니다. 예산은 탐색 probe와 실패를 포함한
미캐시 전체 격자 시도 수입니다. 공통 실행의 caller 예산이 저장 예산보다
작으면 전계를 풀기 전에 거부합니다.

성공 시 선택·세분 전류 표본과 완료 이력을 보존합니다. 실패 시 result는
null이며 원 주파수 벡터·시도 수·단계·실패 변수/입력·완료 이력이 남습니다.
원인이 `ShapePanelLineError`이면 `cause_details`에 부분 전류 작업도 보존합니다.
사용자 중단은 전파합니다. `SavedExecutionRecord`는 재계산 없이 성공·실패
기록을 복원하며 기존 크기 한도·digest 검사·호스트 artifact 선언을 따릅니다.

아래 예제는 요청만 준비합니다. 반복 목표는 명시적 사용자 지정값이며 해당
기하의 달성 결과가 아닙니다. `prepared.run()`으로 실제 검색을 시작합니다.
정규화된 요청 자체는 계산 결과가 아닙니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.shape_sampled_panel_pair_goal_document import ShapeSampledPanelForwardPairDesignDocument
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
original = SampledPanelForwardPairDesignDocument(study, conductor={'kind': 'perfect'},
    frequencies=[1e9, 2e9, 4e9],
    targets=dict(zip(quantities, [[110.]*3, [40.]*3])),
    tolerances=dict(zip(quantities, [[.25]*3, [.125]*3])),
    initial=[.7e-3, .35e-3], max_evaluations=64)
saved = ShapeSampledPanelForwardPairDesignDocument(original, step_fraction=.001)
text = saved.dumps()
assert normalize_saved(text) == text
prepared = SavedExecutionRequest(text, max_evaluations=64)
assert prepared.to_dict()['input'] == saved.to_dict()
# receipt = prepared.run()  # Starts actual fields and bounded optimization.
```

유한 바닥 접지·열린 벽 기하와 유한 주파수 격자는 외곽 충분성·작은 상호항 정확도·연속 대역 경계·실측 정확도·유일해·전역 최적해를 입증하지 않습니다.
