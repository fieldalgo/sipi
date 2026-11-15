# 면별 금속 주파수·해상도 판정 저장

[English](../../../../../packages/sipi/two_ground_face_sampled_resolution_yield_document.md)

`TwoGroundFaceSampledResolutionYieldDocument`는
`sipi.two-ground-face-sampled-resolution-yield/1`을 저장한다.
최상위 다섯 키는 `schema`, `studies`, `acceptance`, `confidence`, `minimum_yield`다.
[직접 해상도 판정](two_ground_face_sampled_resolution_yield.md)의 계약을 유지한다.
물리가 같은 면별 금속 IID 연구2..8개·서로 다른 메시/패널 제어·하나의 제조 분모를
쓰고 해상도 불일치/실패 격자는 unresolved로 남긴다. 중첩 버전·면별/접지 법칙·
순서 있는 주파수 배열·표본 사양을 명시적으로 보존한다.

다음 예제는 장 계산 없이 base/joint 저장 계획을 준비한다.

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

from sipi.two_ground_face_sampled_resolution_yield_document import TwoGroundFaceSampledResolutionYieldDocument
saved = TwoGroundFaceSampledResolutionYieldDocument([plans[0], plans[3]],
    acceptance=acceptance, confidence=.95, minimum_yield=.8)
assert saved.required_evaluations == 4
assert TwoGroundFaceSampledResolutionYieldDocument.loads(saved.dumps()).dumps() == saved.dumps()
```

`saved.analyze(max_evaluations=4)`는 예정된 전주파수 행 네 개를 실행한다.
첫 장 계산 전에 모든 문서·IID 조건·서로 다른 제어·전체 예정 예산을 검사한다.
총10000행을 넘을 수 없고 주파수 점이 시행 수를 늘리지 않는다. 첫 연구 전에
표본 생성을 검사한다. 실패는 원래 행과 typed 원인을 보존하고 후속 예정 행도
실행하며 중단은 전파한다. 이 제한은 내부 풀이 수·메모리·실행 시간을 경계 짓지 않는다.

저장 요청과 CLI도 명시 평가 예산·입력 바이트·diagnostic 제한을 사용한다.
지원하지 않는 diagnostic과 부족한 예산은 장 계산 전에 거부한다. 통계 계산 완료가
확률 목표 통과를 뜻하지 않는다. 미확정 분류가 있으면 incomplete이며 해상도 간
판정 불일치에 가짜 장 오류를 만들지 않는다. 기록/프로젝트는 모든 입력·행·원인을
재계산 없이 복원한다. JSON 중복 키·비유한 값·다른 source 방법·물리 입력 변경은 거부한다.

등록 물리 예제는 직접 판정의 seed19 폭 표본 두 개·2/3.5/5GHz와 base/joint 제어를
재사용한다. 추출된 네 행을 독립 행렬제곱근 전진 임피던스와 비교한 뒤 공통 실행에서
포착한 선로 결과를 정확히 재현한다. 별도 근거 대조로 직접 판정의 원래 base/joint
입력·값·전류·메시와 일치하는지 검사한다. 소스와 정확 설치본은 독립 실행한다.
CLI 시험은 완료 및 실패 행 기록을 프로젝트 재열기까지 보존하는지 검사한다.

고정된 평가 모델의 비교이며 이산화 오차 경계·연속 대역 수락·실측 생산 수율·
다른 플랫폼 수락을 뜻하지 않는다. 수치/외곽 검사와 제조 분포의 타당성은 별도 조건이고
이 작은 표본 예제는 생산 연구가 아니다.
