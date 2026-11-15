# 주파수 표본 전체의 고정 면별 금속 후보 선택

[English](../../../../../packages/sipi/two_ground_face_sampled_pair_selection.md)

`TwoGroundFaceSampledForwardPairSelectionDocument`는
`sipi.two-ground-face-sampled-forward-pair-selection/1`을 저장한다.
1..32개의 미리 고정한 명명 후보마다 완전한
[면별 금속 주파수 연구](two_ground_face_sampled_pair_study.md)와 한 단위의 비음수 비용을 제공한다.
주파수 벡터와 수락 배열은 정확히 같아야 한다. 금속 면·기준 접지·재료·패널 설정·
IID 표본 모델은 명시적으로 유지한다. 아래 준비는 장을 풀지 않는다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='uniform', count=4, seed=19, variables=[
        dict(name='width', lower=.00043, upper=.00044)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundFaceSampledForwardPairStudyDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(
        positive=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)])),
        negative=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (45e6,21e6,35e6,58e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
assert TwoGroundFaceSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_face_sampled_pair_selection import TwoGroundFaceSampledForwardPairSelectionDocument
candidates = []
for index, (lower, upper) in enumerate(((.00043, .000435), (.000435, .00044))):
    raw = study.to_dict()
    raw['study']['sampling']['variables'] = [dict(name='width', lower=lower, upper=upper)]
    candidates.append(dict(name='fixed-'+str(index), cost=index+1., study=raw))
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
selection = TwoGroundFaceSampledForwardPairSelectionDocument(candidates,
    cost_unit='relative', acceptance=acceptance, minimum_yield=.1, confidence=.9)
assert TwoGroundFaceSampledForwardPairSelectionDocument.loads(selection.dumps()).dumps() == selection.dumps()
```

`selection.analyze(max_evaluations=8)`은 계획한 여덟 행 모두를 계산한다.
첫 장 계산 전에 모든 후보와 표본 생성을 검사한다. 예산에는 모든 예정 행을 포함한다.
앞선 적격 후보를 찾더라도 전체 후보 평가를 멈추지 않는다. 실패는 원래 분모의
미확정 행으로 남으며 후속 후보도 실행한다. 중단은 부분 선택을 반환하지 않고 전파한다.

각 행은 두 물리량과 모든 제공 주파수의 [공동 사건](two_ground_face_sampled_pair_yield.md) 하나다.
기존 보수적인 정확 부동소수 Bonferroni 할당은 family 오류 예산을 후보 수로 나눈다.
주파수나 물리량 수로 나누지 않는다. 후보끼리는 종속되어도 되지만 각 후보의 행은
명시한 IID uniform/normal 모델을 따라야 한다. 각 후보는 unknown 라벨의 가능한
모든 완성을 포함하는 정확 Clopper–Pearson 구간을 유지한다.

적격 고정 후보 중 최소 비용을 선택하고 동률이면 원래 순서를 쓴다. 더 싼 미확정
후보도 보존되며 실제로 적격일 수 있다. 모든 후보가 확률 목표에 실패해야
`none-certified`이며 통계적 미확정이 남으면 `undetermined`다. 확률 목표가 0이면
전부 unknown인 후보도 적격일 수 있으나 unknown 행과 [0,1] 구간을 지우지 않는다.
선택은 명시 모델·유한 후보에 조건부이며 전역 또는 연속 최적해가 아니다.

물리 시험은 계산 전에 예제의 두 폭 분포를 고정한다. 각 네 표본·seed19·Debye 재료·
2/3.5/5GHz와 역순으로 배치한 면별 전도도58/35/21/45MS/m를 사용한다.
모든 주파수에서 Zdd100–103ohm·Zcc50–52ohm을 만족해야 한다.
family 신뢰도0.9는 후보 신뢰도0.95를 할당한다. 요청 확률0.1은 계약 예시이며
생산 목표가 아니다. 독립 분류와 이항 구간으로 적격 여부·비용 선택을 결정한다.
앞선 끝점 장·메시·패널·외곽 검증은 별도 근거이며 모든 무작위 행의 오차 추정이 아니다.

CLI·저장 요청·기록·프로젝트는 모든 후보 입력·시도·분류·전류/메시 근거·typed 실패를
보존한다. unknown 행이 있으면 선택에 성공해도 실행은 incomplete다. 기록 복원은
재계산하지 않는다. 독립 구간·후보 사이 종속·서로 다른 표본 수·동률·더 싼 unknown
후보·사전 예산·엄격한 source 타입·잘못된 입력·중단을 검사한다. 적응적 재표본·
연속 대역 보장·실측 생산 수율·플랫폼 수락을 뜻하지 않는다.
