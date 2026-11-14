# 형상전류 제조 표본의 동시 조건 만족률

[English](../../../../../packages/sipi/shape_panel_pair_yield.md) ·
[형상전류 표본](shape_panel_pair_study.md) · [통계 계약](panel_pair_yield.md)

`ShapePanelForwardPairYieldDocument`는 차동·공통 순방향 임피던스 실수부가
각각 포함 경계 조건을 동시에 만족하는 사건을 저장합니다. 엄격한
`sipi.shape-panel-forward-pair-yield/1`의 키는 `schema`, `study`, `acceptance`,
`confidence`, `minimum_yield`입니다. 내부 문서는 명시 형상전류 study/1이어야 하며
독립 동일분포 uniform/normal 표본만 허용합니다. sweep/corners는 거부하고
벌크·고정 코팅 금속 선택은 보존합니다. 기존 수율 문서의 전류 방식을 바꾸지 않습니다.

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
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = PanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    panels_per_edge=16, ground_modes=512, interpolation_degree=16)
document = ShapePanelForwardPairStudyDocument(panel, step_fraction=1e-3)
from sipi.shape_panel_pair_yield import ShapePanelForwardPairYieldDocument

limits = {
    'differential_forward_impedance_real': {'minimum': 124., 'maximum': 130.},
    'common_forward_impedance_real': {'minimum': 41., 'maximum': 43.},
}
yield_document = ShapePanelForwardPairYieldDocument(document, acceptance=limits,
    confidence=.95, minimum_yield=.8)
request = SavedExecutionRequest(yield_document.dumps(), max_evaluations=4)
assert ShapePanelForwardPairYieldDocument.loads(yield_document.dumps()).dumps() == yield_document.dumps()
# receipt = request.run()  # Runs the four requested field extractions.
```

원래 한 행이 하나의 동시 사건이며 행 안의 변수 상관도 유지합니다. 동시 만족률은
두 개별 만족률의 곱이 아닙니다. 추출·진단 실패는 미해결 행으로 원래 분모에 남습니다.
표본 비율의 하한은 통과수/전체수, 상한은 (통과수+미해결수)/전체수입니다.
기존 Clopper–Pearson 구간은 미해결 행에 가능한 모든 판정을 포함합니다.
단측 임피던스 경계도 허용합니다. 신뢰구간 하한이 목표 이상이면 pass, 상한이
목표 미만이면 fail, 그 외는 undetermined이며 목표가 없으면 not-requested입니다.

`assess_shape_panel_pair_yield(study, acceptance=limits)`는 전계를 풀지 않고
원래 Python study 객체를 유지합니다. 기존 통계 검증기로 원표본 벡터·순서·수·
분포·행 상태를 검사하며 내부 통계용 뷰는 원행을 공유할 뿐 전류 방식을 변환하거나
다시 계산하지 않습니다. 수동 구성 행은 인증된 수치 근거가 아닙니다. 결과는
완료한 전류 기록과 부분 실패의 `cause_details`를 모두 보존합니다.

미해결 행이 있으면 공통 실행은 입력·오류·전류 근거를 버리지 않고 `incomplete`를
반환합니다. 기록·프로젝트 복원은 전계를 다시 풀지 않습니다. 전체 표본 수의
예산을 먼저 검사하고 중단 신호는 전파합니다. 파싱·조건 검사는 전계 없이 수행하며
입력과 수락 조건은 호출자의 이후 사전 변경에 영향을 받지 않습니다.

## 한계와 검증

이 신뢰구간은 지정한 독립 동일분포의 유한 영역 계산을 설명합니다. 이산화·외곽·
재료 모델·제조 모델 오차, 측정 불확도, 피팅과 적응적 설계 선택 효과를 포함하지
않습니다. 형상전류 표본 문서의 작은 영역 미수락 반례는 그대로이며 통계 계산이
성공했다고 전계가 수렴한 것은 아닙니다. 실측 생산 수율로 해석하지 않습니다.

독립 유한 이항 꼬리 역산, SciPy 정확 구간, 모든 미해결 조합, 포함 경계의 동시
사건, 변조·재정렬 행, 예산과 기록 복원을 검사합니다. 벌크·코팅 금속의 실제
독립 동일분포 기하 표본 각 4개는 균일 유전체 불변식·독립 금속 전달식·4포트
네트워크와 대조합니다. 완료 및 주입한 부분 실패 영수증은 원전류 근거를 보존합니다.
이는 모든 입력이나 다른 플랫폼의 수치 정확도 인증이 아닙니다.
