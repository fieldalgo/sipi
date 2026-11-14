# 고정된 수치 해상도 사이의 동시 수락 비교

[비교 요청 저장](panel_resolution_yield_document.md)은 전체 평가 계획을 보존합니다.

`assess_panel_pair_resolution_yield`는 이미 계산한 `PanelForwardPairStudy`
2~8개를 전계 계산 없이 비교합니다. 모든 입력의 버전·전류 방법, 물리 기하,
고정 금속, 유전체 모델, 주파수, 제약조건, IID 표본 규칙은 같아야 합니다.
체적 메시와 패널 설정만 달라질 수 있습니다. 중복 설정은 거부하며 해상도
순서가 세분 순서라고 가정하지 않습니다. 외곽 상자 변경, 다른 물리 설계,
다른 난수 표본은 이 비교 계약에 포함되지 않습니다.

제조 표본마다 기존 두 임피던스 조건을 모든 해상도에서 평가합니다.
모두 합격이면 `pass`, 모두 불합격이면 `fail`, 라벨이 다르거나 원래 계산
실패가 하나라도 있으면 `unresolved`입니다. 이는 유한 관측의 일치 여부이며
검증된 연속해의 판정이 아닙니다. 원래 결과·단계·오류와 해상도별 판정을
그대로 보존합니다.

분모는 표본 수이며 표본 수에 해상도 수를 곱하지 않습니다. 표본 비율 범위는
전원 일치 합격 수/n부터 (합격+미확정)/n까지입니다. 기존 Clopper–Pearson
미해결 구간으로 고정된 평가 모델의 신뢰 한계를 구하며, 검증된 이산화 오차
상한을 포함하지 않습니다. 모든 해상도에 공통인 체계적 오류는 이 비교로
검출할 수 없습니다. 이 비교나 명목 IID 구간은 실측 생산 수율의 근거가 아닙니다.

다음 두 표본 예제는 사용 흐름을 보여줍니다. 비교 자체는 전계를 풀지 않으며
앞선 두 study 분석에서 명시적으로 계산합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_resolution_yield import assess_panel_pair_resolution_yield

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, box_width=6e-3, air_height=2e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=2, seed=3, variables=[
        dict(name='width', lower=.28e-3, upper=.32e-3)]))
base = PanelForwardPairStudyDocument(source, conductor={'kind': 'perfect'})
fine = base.to_dict()
for key in ('edge_size', 'far_size', 'grade'):
    fine['study']['mesh'][key] /= 2
fine['panel']['panels_per_edge'] *= 2
studies = [base.analyze(max_evaluations=2),
           PanelForwardPairStudyDocument.from_dict(fine).analyze(max_evaluations=2)]
comparison = assess_panel_pair_resolution_yield(studies, acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=130.),
    'common_forward_impedance_real': dict(minimum=20., maximum=60.)},
    confidence=.95, minimum_yield=.9)
assert comparison.to_dict()['count'] == 2
assert comparison.to_dict()['resolution_count'] == 2
assert sum((comparison.passed, comparison.failed, comparison.unresolved)) == 2
```

`assessments`는 해상도별 원래 판정을 보존합니다. `classifications`,
`confidence_interval`과 바깥 tuple은 변경할 수 없습니다. `to_dict()`에는
각 원입력·판정, 표본별 해상도 라벨, 단일 분모와 유한 해상도 범위를 명시합니다.
선택적인 `minimum_yield`는 이 보수적 구간으로 판단하며 `undetermined`로
남을 수 있습니다. 기존 study나 yield 결과를 자동으로 대체하지 않습니다.

보존한 코팅 8개 표본에서 네 해상도의 합격 수는 6·7·6·7개입니다.
한 표본이 차동 하한 109Ω을 넘나듭니다. 비교 결과는 합격 6개·불합격 1개·
미확정 1개로, 비율 범위 [.75, .875], 95% 신뢰 구간 약 [.3491, .9968]입니다.
원래 명목 결과는 8개 중 6개와 기존 구간을 유지합니다. 제시한 모델·유한
해상도의 관측이며 물리 오차나 생산 합격을 인증하는 결과가 아닙니다.

검증은 전체 동시 판정 진리표, 독립 유한 이항 꼬리 확률 역산, 미해결 행의
모든 가능한 완료 개수, 물리·입력 동일성, 규격 경계의 실제 코팅 전계를 포함합니다.
보존한 qualification 32개 전계는 정확한 입력 해시로 재생하고, 작은 실제 회귀는
두 표본을 네 해상도에서 별도로 다시 계산합니다. 이 직접 API는 저장 요청을
추가하거나 메시를 자동 선택하지 않습니다.

[코팅 공차](layered_panel_study.md) · [IID 동시 수락](panel_pair_yield.md) ·
[English](../../../../../packages/sipi/panel_resolution_yield.md)
