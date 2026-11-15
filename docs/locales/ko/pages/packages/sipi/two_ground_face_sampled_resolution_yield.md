# 명시 해상도 사이의 면별 금속 공동 판정

[English](../../../../../packages/sipi/two_ground_face_sampled_resolution_yield.md)

`assess_two_ground_face_sampled_pair_resolution_yield`는 완료된
[면별 금속 주파수 연구](two_ground_face_sampled_pair_study.md) 2..8개를 장 재계산 없이 비교한다.
모든 입력·순서 있는 주파수·면별/접지 금속 법칙·재료 모델·표본 사양이 같아야 한다.
명시한 체적 메시와 패널 제어만 달라질 수 있고 중복 제어 조합은 거부한다.
상자나 접지면을 바꾸면 물리 입력 변경이므로 여기서는 거부한다.
[유한 외곽 일치](two_ground_face_resolution.md)는 별도로 평가한다.

다음 예제는 네 가지 명시 계획만 준비하며 실행하지 않는다.

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

from sipi.two_ground_face_sampled_resolution_yield import assess_two_ground_face_sampled_pair_resolution_yield
plans = []
for phase in ('base', 'volume', 'panel', 'joint'):
    raw = study.to_dict()
    raw['study']['sampling']['count'] = 2
    if phase in ('volume', 'joint'):
        for key in ('edge_size', 'far_size', 'grade'):
            raw['study']['mesh'][key] *= .5
    if phase in ('panel', 'joint'):
        raw['panel'].update(panels_per_edge=128, ground_modes=256)
    plans.append(TwoGroundFaceSampledForwardPairStudyDocument.from_dict(raw))
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
assert len(plans) == 4 and all(len(p.samples()) == 2 for p in plans)
```

각 계획을 `p.analyze(max_evaluations=2)`로 명시 실행한 뒤 네 연구 결과를
`assess_two_ground_face_sampled_pair_resolution_yield`에 전달하고
`acceptance=acceptance`, `confidence=.95`, `minimum_yield=.8`을 지정한다.
직접 판정 함수는 장을 풀거나 메시를 선택하지 않는다.

행의 사건은 모든 제공 주파수에서 두 임피던스 한도를 모두 만족하는 것이다.
제조 표본 하나는 모든 해상도에서 pass일 때 pass, 모두 fail일 때 fail,
나머지는 원래 장 계산 실패를 포함해 unresolved다. 예제 분모는 두 표본이며
여덟 평가나 24개 주파수 점이 아니다. 기존 정확 이항 envelope는 unknown 라벨의
모든 가능한 완성을 포함한다. 각 해상도의 입력 아래 원래 행·값·실패·전류 관측·메시를
그대로 보존한다. 입력/행 검증은 구조 검사이며 수동 장 자료의 진실성을 인증하지 않는다.

등록 Debye 예제는 폭0.43–0.44mm uniform·간격0.28mm·seed19·두 표본·
2/3.5/5GHz를 쓴다. 기본64패널/128접지모드/차수16에서 체적은edge/far/grade를
절반으로, 패널은128/256/16으로, joint는 두 축을 함께 바꾼다.
R/내부L/외부L/C/G/C0 여섯 행렬 모두 기본 대 각 세분 및 joint 대 각 독립 축에
상대1%·절대0의 원소별 유한 비교를 적용하며 바닥값은 없다. 독립 행렬제곱근으로
전진 임피던스를1e-10에서 검사하고 균일 Debye C/G·진공LC 불변식도 별도로 검사한다.
Zdd100–103/Zcc50–52ohm 한도는 공동 사건이며 장 정확도 허용오차가 아니다.
독립 원소별 분류와 이항 구간으로 결합 판정을 확인한다.

두 표본은 전달 예시일 뿐이다. 일치는 공통 계통오차를 검출하거나 이산화 오차를
경계 짓지 않으며 점근 수렴·주파수 사이 수락·실측 생산 수율을 인증하지 않는다.
자동 세분·상자 변경·적응적 표본·플랫폼 수락은 없다. 합성 시험은 두/세 해상도의
전체 진리표·unknown의 가능한 완성·최대 여덟 해상도에서 같은 분모·바뀐 물리/다른
전류 방법 거부·원실패 보존·불변 결과를 확인한다.
