# 유한 주파수·해상도에 걸친 공동 수락 비교

`assess_sampled_panel_pair_resolution_yield`는 이미 계산한
`SampledPanelForwardPairStudy` 결과 2–8개를 비교합니다. 명시적인 study 버전,
물리 입력, 고정 코팅, 주파수 벡터의 순서, 표본 분포·seed·변수 순서·제약이
같아야 합니다. 체적 메시와 패널 제어만 달라질 수 있으며 중복 제어는 거부합니다.
study 버전 1과 2를 지원하지만 하나의 비교에서 섞지 않습니다. 비교 함수 자체는
전계를 계산하지 않습니다.
직접 조립한 기록은 구조와 표본 대응을 검사할 뿐, 전계 풀이 또는 측정의
진위를 인증하지 않습니다.

각 해상도에서는 두 forward 임피던스가 지정한 모든 주파수의 한계를 만족해야
합니다. 해상도가 모두 통과하면 해당 표본은 pass, 모두 실패하면 fail이며,
그 밖에는 unresolved입니다. 한 해상도라도 계산에 실패하면 다른 해상도가
규격 밖이더라도 미확정으로 남깁니다. 모든 원래 행·입력·오류 단계와 해상도별
개별 판정을 그대로 보존합니다.

제조 표본 한 행이 시행 한 번입니다. 분모에 주파수 수나 해상도 수를 곱하지
않습니다. Clopper–Pearson 미확정 포락 신뢰구간은 이 유한 모형들로 평가한
지정 iid 분포의 의미만 가집니다. 이산화 오차 상한, 공유된 체계적 오차 탐지,
주파수 표본 사이의 수락, 실측 생산 수율을 보증하지 않습니다. unresolved는
판정 불일치 또는 계산 실패이며 실제 정답의 추정값이 아닙니다.

아래 예제는 study 계산을 명시적으로 수행한 뒤 비교합니다. 두 표본은 사용법을
보여주기 위한 것이며 높은 수율을 인증할 수 없습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_resolution_yield import assess_sampled_panel_pair_resolution_yield

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, box_width=6e-3, air_height=2e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=2, seed=3, variables=[
        dict(name='width', lower=.28e-3, upper=.32e-3)]))
base = SampledPanelForwardPairStudyDocument(source, conductor={'kind': 'perfect'}, frequencies=[1e9, 2e9, 4e9])
fine = base.to_dict()
for key in ('edge_size', 'far_size', 'grade'):
    fine['study']['mesh'][key] /= 2
fine['panel']['panels_per_edge'] *= 2
studies = [base.analyze(max_evaluations=2),
           SampledPanelForwardPairStudyDocument.from_dict(fine).analyze(max_evaluations=2)]
comparison = assess_sampled_panel_pair_resolution_yield(studies, acceptance={
    'differential_forward_impedance_real': dict(minimum=[90.]*3, maximum=[130.]*3),
    'common_forward_impedance_real': dict(minimum=[20.]*3, maximum=[60.]*3)},
    confidence=.95, minimum_yield=.9)
assert comparison.to_dict()['count'] == 2
assert comparison.to_dict()['resolution_count'] == 2
assert sum((comparison.passed, comparison.failed, comparison.unresolved)) == 2
assert comparison.frequencies == (1e9, 2e9, 4e9)
```

`frequencies`, `classifications`, `confidence_interval`과 중첩 수락 배열은
불변입니다. `to_dict()`는 해상도별 원래 study 입력·공동 판정, 제조 행별 라벨,
단일 분모, 유한 주파수·해상도 범위를 담습니다. 내보낸 사전을 바꿔도 원래
판정은 바뀌지 않습니다. `minimum_yield`는 신뢰구간을 사용하므로 계산이 모두
완료되어도 `undetermined`일 수 있습니다.

보존한 코팅 8표본 사례의 1·2·4 GHz 공동 한계에서는 네 해상도 모두 5개 통과,
3개 실패입니다. 이 유한 집합의 비교에는 미확정 행이 없지만, 물리 정확도나
가능한 모든 제조 기하에서의 일치를 증명하지는 않습니다. 독립 이항 꼬리 시험은
미확정 표본의 모든 완성을 포함하며, 실제 코팅 계산은 두 표본·네 해상도의
전 주파수 전계를 독립 네트워크 참조와 대조합니다.

이 직접 API는 새 저장 요청 버전을 추가하지 않으며 메시를 자동 세분하거나
기존 명목 수율 결과를 교체하지 않습니다.

[코팅 유한 주파수 study](layered_sampled_panel_study.md) ·
[단일 주파수 해상도 비교](panel_resolution_yield.md) ·
[English](../../../../../packages/sipi/sampled_panel_resolution_yield.md)

[전체 비교 저장·실행](sampled_panel_resolution_yield_document.md).
