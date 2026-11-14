# 유한 주파수 해상도 수락 요청 저장

`SampledPanelResolutionYieldDocument`는 `sipi.sampled-panel-resolution-yield/1`로
명시적인 비교를 저장합니다. 필수 키 다섯 개는 `schema`, `studies`, `acceptance`,
`confidence`, `minimum_yield`입니다. 중첩 study 2–8개는 명시적인 sampled panel
pair study 버전 1 또는 2이며 서로 같은 버전이어야 합니다. 기하, 고정 금속 법칙,
재료, 주파수 벡터 순서, 제약과 표본 계획은 같고 메시·패널 설정만 달라야 합니다.

각 물리량에 주파수별 minimum/maximum 배열을 명시하며 각 주파수에는 적어도
하나의 유한 한계가 필요합니다. iid uniform/normal 표본만 허용합니다. 정규화는
전계 없이 중첩 입력을 검사하며 기존 저장 입력의 버전이나 통계 의미를 암묵적으로
바꾸지 않습니다.

`required_evaluations`는 제조 표본 수 × 지정 해상도 수이며 최대 10000입니다.
실패한 행을 포함하여 각 시도 행은 전체 주파수 batch 하나입니다. 내부 전계
풀이 수나 시간의 상한은 아닙니다. 호출 예산이 부족하거나 표본 계획 생성이
실패하면 모든 전계 계산 전에 거부하고, 사용자 중단은 전파합니다.

아래 예제는 두 표본과 두 해상도를 사용합니다. 공통 실행기가 계획한 네 batch를
명시적으로 계산하고 원래 요청과 비교 결과를 반환합니다. 작은 예제 표본만으로
높은 수율을 입증하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_resolution_yield_document import SampledPanelResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved

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
documents = [base, SampledPanelForwardPairStudyDocument.from_dict(fine)]
request = SampledPanelResolutionYieldDocument(documents, acceptance={
    'differential_forward_impedance_real': dict(minimum=[90.]*3, maximum=[130.]*3),
    'common_forward_impedance_real': dict(minimum=[20.]*3, maximum=[60.]*3)},
    confidence=.95, minimum_yield=.9)
assert request.required_evaluations == 4
saved = request.dumps()
assert normalize_saved(saved) == saved
output = execute_saved(saved, max_evaluations=4)
assert output['input'] == request.to_dict()
assert output['result']['count'] == 2
assert output['result']['resolution_count'] == 2
assert output['result']['frequencies_hz'] == [1e9, 2e9, 4e9]
assert output['error'] is None
```

오류와 실패 단계를 포함해 계획된 원래 행을 모두 보존합니다.
[유한 주파수 해상도 직접 판정](sampled_panel_resolution_yield.md)을 사용하여
모든 해상도가 통과하면 pass, 모두 실패하면 fail, 나머지는 unresolved로 둡니다.
주파수·해상도 수에 관계없이 제조 행 하나가 통계 시행 하나입니다.

미확정 행이 하나라도 있으면 공통 실행 상태는 `incomplete`입니다. 예외 없는
수치 라벨 불일치도 포함합니다. 이때 전체 비교 결과는 남고 최상위 `error`는
null이며 원래 오류는 해당 행에 보존됩니다. 미확정 행이 없으면 실행은
`complete`지만, 별도의 수율 목표 판정은 `undetermined` 또는 실패일 수 있습니다.
신뢰구간은 유한 계산 모형의 의미이며 수치 오차, 연속 대역 수락 또는 실측 생산
수율을 뜻하지 않습니다. 이 요청은 메시를 자동 세분하거나 제조 분포를 인증하지
않습니다.

엄격한 버전·중첩 키, 중복·비유한 입력 거부, 전체 계획 예산, 주파수 순서·고정
코팅 동일성, 실패 후 행 계속 처리, 호출 전송 제한과 실제 코팅 계산을 검증합니다.
두 표본의 base/joint 비교는 독립 검증된 전계 결과를 유지하며 직접·공통 실행이
같은 결과를 재현합니다.

[코팅 유한 주파수 study](layered_sampled_panel_study.md) ·
[English](../../../../../packages/sipi/sampled_panel_resolution_yield_document.md)
