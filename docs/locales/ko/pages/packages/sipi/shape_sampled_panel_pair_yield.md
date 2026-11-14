# 형상전류 주파수 격자의 동시 조건 만족률

[English](../../../../../packages/sipi/shape_sampled_panel_pair_yield.md) ·
[주파수 격자 표본](shape_sampled_panel_pair_study.md) · [기존 신뢰구간 계약](sampled_panel_pair_yield.md)

`ShapeSampledPanelForwardPairYieldDocument`는 제조 행마다 요청한 **모든 주파수**의
차동·공통 임피던스 조건을 **모두** 만족하는 하나의 사건을 저장합니다. 엄격한
`sipi.shape-sampled-panel-forward-pair-yield/1` 키는 `schema`, `study`,
`acceptance`, `confidence`, `minimum_yield`입니다. 내부 shape-grid study/1은
독립 동일분포 uniform/normal만 허용하고 sweep/corners는 거부합니다. 벌크·고정
코팅 재료와 계산 방식은 명시적으로 유지합니다. 두 물리량의 최소·최대 조건은
주파수 격자 길이와 같은 배열이어야 하며 각 주파수에 한쪽 이상의 경계가 필요합니다.
스칼라 조건의 암묵적인 반복 적용은 거부합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = SampledPanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    frequencies=[1e9, 2e9, 4e9], panels_per_edge=16,
    ground_modes=512, interpolation_degree=16)
document = ShapeSampledPanelForwardPairStudyDocument(panel, step_fraction=1e-3)
from sipi.shape_sampled_panel_pair_yield import ShapeSampledPanelForwardPairYieldDocument

limits = {
    'differential_forward_impedance_real': {'minimum': [65.,65.,65.], 'maximum': [75.,75.,75.]},
    'common_forward_impedance_real': {'minimum': [21.,21.,21.], 'maximum': [26.,26.,26.]},
}
yield_document = ShapeSampledPanelForwardPairYieldDocument(document, acceptance=limits,
    confidence=.95, minimum_yield=.8)
request = SavedExecutionRequest(yield_document.dumps(), max_evaluations=4)
assert ShapeSampledPanelForwardPairYieldDocument.loads(yield_document.dumps()).dumps() == yield_document.dumps()
# receipt = request.run()  # Four original rows, each evaluated on the complete grid.
```

주파수 점 수와 관계없이 원래 행 하나가 Bernoulli 시행 하나입니다. 행 안의 변수·
주파수·물리량 상관을 보존하며 동시 확률은 개별 만족률의 곱이 아닙니다. 전체 격자의
실패도 미해결 행 하나로 원분모에 남습니다. 기존 정확 Clopper–Pearson 구간이
미해결 행의 모든 가능한 판정을 포함하고 포함 경계·단측 경계·목표의
pass/fail/undetermined 의미를 유지합니다.

`assess_shape_sampled_panel_pair_yield`는 전계를 풀지 않고 원래 study 객체를
보존합니다. 통계용 뷰로 기존 행·격자 검증기를 재사용할 뿐 전류 방식을 바꾸거나
재계산하지 않습니다. 결과에 완료한 전류 기록과 부분 실패 상세가 남습니다.
수동 구성한 행은 독립 인증된 전계가 아닙니다. 미해결 행이 있으면 공통 실행은
`incomplete`를 반환하며 요청·기록·프로젝트 복원은 전계 없이 수행합니다.
행 단위 예산을 추출 전에 검사하고 중단 신호를 전파합니다.

독립 이항 꼬리 역산과 SciPy 정확 구간으로 통과수·미해결 조합·경계를 검사합니다.
전체 동시 사건과 개별 만족률을 구분하고 주파수가 9개 또는 64개여도 제조 표본 수를
늘리지 않는지 확인합니다. 벌크·코팅 금속의 실제 독립 동일분포 각 4행을 세 주파수의
Debye 격자에서 계산하여 독립 재료·네트워크 기준 및 완료·부분 실패 기록과 대조합니다.

결과는 지정한 유한 격자와 분포만 설명합니다. 주파수 사이 값, 외곽·메시 오차,
피팅 재료 불확도, 적응적 선택이나 실측 생산 수율을 보장하지 않습니다. 기존 작은
영역 미수락 사례는 통계 계산이 완료되어도 미수락이며 기존 수율 스키마가 이 방식을
암묵적으로 선택하지 않습니다.
