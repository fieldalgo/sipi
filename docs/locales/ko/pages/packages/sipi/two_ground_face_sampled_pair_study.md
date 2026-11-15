# 유한 주파수의 면별 금속 제조 표본

[English](../../../../../packages/sipi/two_ground_face_sampled_pair_study.md)

`TwoGroundFaceSampledForwardPairStudyDocument`는
`sipi.two-ground-face-sampled-forward-pair-study/1`을 저장한다. 순서가 있는
기하/유전체 표본을 [면별 금속 선로](two_ground_face_panel_line.md)의 명시적으로
증가하는 양수 주파수 2..64개에 연결한다. 각 제조 행은 전체 격자에서 같은 기하/재료
표본을 쓰며 물리적 면의 금속·코팅·거칠기와 참조 법칙을 유지한다. Re(Zdd)와
Re(Zcc)는 각각 Ic=0, Id=0인 전진파 입력의 값이며 독립 전파 모드 임피던스가 아니다.

다음 예제는 계산 없이 입력을 준비한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_face_sampled_pair_study import TwoGroundFaceSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='corners', variables=[
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
assert len(study.samples()) == 2
```

`study.analyze(max_evaluations=2)` 또는 공통 `execute_saved`가 계산한다.
길이는 m, 주파수는 Hz, 결과는 ohm이다. 원 study는 첫 주파수에 고정한다.
study/3·/4의 기존 기하/재료 바인딩·고정 피치·seed·corner/sweep/IID·상관 의미를
유지한다. 표본 유전체 모델의 주파수 의존성도 유지한다. 주파수별 재추출이나
자동 세분·실패 행 재시도는 하지 않는다.

예산은 개별 주파수 대신 실패를 포함한 전체 제조 행 수를 센다. 2..10000을
허용하며 부족하면 장 계산 전에 거부한다. 명목 전체격자 정규화는 장 계산 없이
수행하지만 모든 표본의 유효성을 증명하지 않는다. 추가·누락·중복·잘못된·비유한
필드는 거부한다. 한 주파수의 실패로 해당 행 전체가 unknown이 된다. 유효하지
않거나 중복/상관된 행도 원래 순서와 표본 값을 유지한다.

행마다 확정된 재료·정확한 선로 입력·실패 단계·typed 원인과 확보한 전류/메시
증거를 보존한다. 이후 행은 계속 계산하고 중단은 전파한다. 모든 행이 성공해야만
요약 통계를 제공하며 이는 명시된 표본 집합을 기술한다. 생산 수율·신뢰 구간·
연속대역 성능을 보장하지 않는다. 요청 안의 성공한 유전체 메시는 재사용할 수 있으나
전체 경계 전류 캐시는 선택하지 않는다. 기존 단일 주파수 방법과 저장 스키마는 유지한다.

공통 요청·결과 기록·프로젝트·CLI 파일은 완료 또는 미완료 실행을 보존한다.
결과를 복원해도 계산하지 않는다. 호출자 예산·입력 바이트 한도·미지원 진단의
장 계산 전 검사도 유지한다.

물리 시험은 폭0.43/0.44mm 두 끝점, 간격0.28mm·접지 간격2mm·두께50µm·
높이0.975mm·상자8mm를 사용한다. 2/3.5/5GHz의 균일 유전체는 eps_inf3·
강도0.7·pole1GHz이다. 두 신호의 면별 전도율 배치는 반대이며 양쪽 접지는58MS/m이다.
각 격자를 별도 단일 주파수 RLGC와1e-12로, 전류/메시 identity와 정확히 대조하고
독립 복소 행렬 전진파 값은1e-10으로 검사한다. 기존 Debye C/G-C0 및 외부L
불변식도 유지한다.

두 끝점 모두 별도 [유한 해상도 평가](two_ground_face_resolution.md)를 수행한다.
패널64/128·모드128/256·degree16·독립 체적 설정 절반·공동 세분과16/32mm 상자
512/1024모드를 사용한다. R·내부/외부L·C·G·C0 모든 원소에 상대0.01/절대0을
적용하고 판정 전에 관측을 기록한다. 합성 시험은 독립 모드/통계 기준·64주파수·상관·
실패 단계·면/코팅 보존·재료 바인딩·예산·CLI 복원을 확인한다. 임의 상자·모든 재료·
연속대역·실측 정확도·다른 플랫폼을 검증하는 것은 아니다.

[격자 전체 공동 IID 판정](two_ground_face_sampled_pair_yield.md)
