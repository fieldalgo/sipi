# 면별 금속 주파수격자의 공동 IID 판정

[English](../../../../../packages/sipi/two_ground_face_sampled_pair_yield.md)

`TwoGroundFaceSampledForwardPairYieldDocument`는
`sipi.two-ground-face-sampled-forward-pair-yield/1`을 저장한다.
[면별 금속 제조격자](two_ground_face_sampled_pair_study.md)의 모든 주파수에서
두 전진파 임피던스 실수부에 명시한 포함 경계를 평가한다. 제조 행 하나가 시행 하나다.
주파수/물리량의 모든 한도를 만족해야 한다. 주파수 수가 표본 수를 늘리지 않으며
주변 수락 비율을 곱하지 않는다.

다음 예제는 장 계산 없이 입력을 준비하고 검사한다.

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

from sipi.two_ground_face_sampled_pair_yield import TwoGroundFaceSampledForwardPairYieldDocument
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[100.]*3, maximum=[103.]*3),
    common_forward_impedance_real=dict(minimum=[50.]*3, maximum=[52.]*3))
assessment = TwoGroundFaceSampledForwardPairYieldDocument(study,
    acceptance=acceptance, confidence=.95, minimum_yield=.8)
assert TwoGroundFaceSampledForwardPairYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

`assessment.analyze(max_evaluations=4)`는 모든 세 주파수에서 제조 행 네 개를
실행한다. 경계 단위는 ohm이며 각 물리량의 minimum/maximum 배열을 명시해야 한다.
모든 위치에 유한 경계가 하나 이상 필요하고 한쪽 경계가 없으면 `None`을 쓴다.
스칼라 값의 자동 확장·주파수 보간·솔버 수치 기준 완화는 없다. 이 수락 한도는 명시한 공동
사건이며 장 정확도 기준과 별개다.

명시 모델의 IID uniform 또는 normal 추출만 허용하며 seed를 가진 변수들은
한 행 안에서 상관될 수 있다. corners·sweep·다른 방법은 거부한다. 실패 격자는
원래 분모 안의 unresolved 시행 하나다. 기존 정확 Clopper–Pearson envelope는
unknown 라벨의 가능한 모든 완성을 포함한다. 전부 unknown이면 [0,1]이다.
최소 확률 목표는 신뢰 하한이 목표 이상일 때만 pass, 상한이 목표 미만이면 fail,
나머지는 undetermined다. 네 표본은 전달 예시이며 생산 특성화가 아니다.

`assess_two_ground_face_sampled_pair_yield(result, acceptance=..., confidence=.95)`는
장 계산 없이 기존 면별 연구를 검사한다. source/grid·행 순서·표본 값·물리량·
완료/실패 구조를 확인하고 다른 연구 방법/행 타입은 거부한다. 수동으로 만든 장 값의
진실성을 인증하지 않는다. 원래 행·typed 원인·확정 재료·전류/메시 증거를 결과에
보존한다. 호출자 예산과 실패는 원 study를 따르고 중단은 전파한다. 미확정 시행이
있으면 저장 실행은 incomplete다. 통계 계산이 complete여도 최소 확률 목표를
통과했다는 뜻은 아니다. CLI/요청/기록/프로젝트는 다시 계산하지 않고 이 구분을 유지한다.

등록 물리 예제는 앞선 study의 Debye 모델·폭0.43–0.44mm·간격0.28mm·
2/3.5/5GHz를 사용한다. 시험 전에 모든 주파수의 공동 사건을 Zdd100–103ohm·
Zcc50–52ohm으로 고정했고 uniform 네 표본·seed19·신뢰도0.95·요청 확률0.8을
사용한다. 독립적인 원소별 분류와 정확 이항 구간으로 출력을 검사한다. 앞선 끝점의
메시/패널/외곽 및 독립 장 검증은 별도 근거이며 이 분류는 모든 무작위 행의 수치
불확도를 추정하지 않는다. 합성 시험은 포함/단측 한도·행내 상관·unknown의 모든
가능한 완성·잘못된 행·IID 입장 조건·최소 확률 판정·실패 CLI 복원을 확인한다.

구간은 명시 모델에서 IID로 추출했다는 조건을 전제한다. 잘못된 분포·장/모델 오차·
연속 주파수·선택 편향·실측 생산 수율·브라우저/플랫폼 검증을 포함하지 않는다.
