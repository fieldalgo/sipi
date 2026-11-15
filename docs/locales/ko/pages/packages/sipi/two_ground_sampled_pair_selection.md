# 여러 주파수에서 두 접지면 고정 후보 비교

[English](../../../../../packages/sipi/two_ground_sampled_pair_selection.md)

`TwoGroundSampledForwardPairSelectionDocument`는
`sipi.two-ground-sampled-forward-pair-selection/1` 입력을 저장합니다.
사전에 정한 1~32개 후보마다 고유 이름, 완전한
[주파수 표본 study](two_ground_sampled_pair_study.md), 같은 단위의 비음수 비용을
지정합니다. 모든 후보는 정확히 같은 주파수 순서와 물리량별 포함 경계를 씁니다.
기하·재료·금속·패널·iid 표본 설정은 후보별로 명시합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=17, variables=[
        dict(name='width', lower=.00043, upper=.00044),
        dict(name='gap', lower=.00028, upper=.00030)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundSampledForwardPairStudyDocument(source, frequencies=[2e9,3.5e9,5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_sampled_pair_selection import TwoGroundSampledForwardPairSelectionDocument
other = study.to_dict()
other['study']['parameters']['plane_spacing'] = .0022
other['study']['parameters']['trace_height'] = .001075
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[89.]*3, maximum=[91.]*3),
    common_forward_impedance_real=dict(minimum=[44.]*3, maximum=[46.]*3))
selection = TwoGroundSampledForwardPairSelectionDocument([
    dict(name='first', cost=1., study=study.to_dict()),
    dict(name='second', cost=1.2, study=other)], cost_unit='relative',
    acceptance=acceptance, minimum_yield=.8, confidence=.95)
assert TwoGroundSampledForwardPairSelectionDocument.loads(selection.dumps()).dumps() == selection.dumps()
```

준비·정규화는 장 계산을 하지 않습니다. `selection.analyze(max_evaluations=8)`는
계획한 여덟 표본을 모두 계산합니다. 후보당 네 표본은 입력 예시일 뿐 생산 확률
추정에 충분하다는 뜻이 아닙니다. 후보는 결과를 보기 전에 고정해야 하며 적응형
탐색·재표본 추출은 하지 않습니다. 모든 후보의 표본 생성을 첫 계산 전에 검사하고,
앞 후보가 합격하거나 풀이가 실패해도 원래 모든 표본을 전체 예산에 포함합니다.
사용자 중단은 전파하며 앞 후보를 성급히 선택한 결과로 바꾸지 않습니다.

표본 하나는 두 임피던스와 모든 지정 주파수를 함께 만족하는
[공동 사건](two_ground_sampled_pair_yield.md) 하나입니다. 기존의 보수적인 정확
부동소수점 Bonferroni 배분은 전체 오류 확률을 후보 수로 나눕니다. 주파수 수나
물리량 수로 추가 분할하지 않습니다. 후보끼리 독립일 필요는 없지만 각 후보의
표본은 명시된 iid 모델을 따라야 합니다. 후보마다 정확 Clopper–Pearson 미확정
구간을 보존합니다.

합격 인증된 후보 중 최소 비용을 선택하고 동률이면 입력 순서를 따릅니다. 더 싼
미확정 후보는 보고서에 남으며 실제로는 적합할 수도 있습니다. 모두 요청 확률에
불합격이면 none-certified, 통계적 판정이 남으면 undetermined입니다. 선택 결과는
전역·연속 최적해를 증명하지 않습니다. 요청 확률이 0이면 전부 미확정인 후보도
조건을 만족할 수 있지만 미확정 행과 [0,1] 구간을 그대로 표시합니다.

공통 실행·저장 기록·프로젝트에 모든 후보, 입력, 분류, 전류/메시 관측, 유형 있는
실패를 보존합니다. 선택 후보가 있어도 미확정 행이 있으면 실행은 incomplete입니다.
주파수 보간·연속 대역 보장·실측 수율·수치 오차 구간을 제공하지 않습니다.
물리 정확도와 해상도는 별도 조건입니다.

지원 후보 수 전체의 정확 신뢰배분, 독립 이항 구간, 동률·저가 미확정 후보·다른
표본 수·사전 거부·엄격 입력·기록/프로젝트 복원을 검사합니다. 등록한 실제 Debye
2/3.5/5 GHz 사례는 폭 구간 두 개에서 각 네 표본을 계산하고, 의도적으로 넓은
[1,1000]Ω 조건으로 선택과 근거 보존만 확인합니다. 이 범위는 설계 임피던스 사양이나
정확도 시험이 아닙니다. 원 물리 주파수 study 검증은 별도로 유지합니다. 소스와
정확한 설치 산출물을 따로 검증하며 Linux 결과를 다른 플랫폼으로 확대하지 않습니다.
