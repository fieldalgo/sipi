# 유한 주파수의 면별 금속 쌍 목표 저장

[English](../../../../../packages/sipi/two_ground_face_sampled_pair_goal_document.md)

`TwoGroundFaceSampledForwardPairDesignDocument`는
`sipi.two-ground-face-sampled-forward-pair-design/1`을 저장한다. 템플릿/재료 입력과
물리적 면별 금속 법칙을 [직접 유한격자 목표](two_ground_face_sampled_pair_goal.md)에
연결한다. 함수를 직렬화하지 않으며 기존 스키마와 수치 기준을 바꾸지 않는다.

다음 예제는 장 계산 없이 입력을 준비하고 정규화한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_face_sampled_pair_goal_document import TwoGroundFaceSampledForwardPairDesignDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00035, upper=.0005),
        dict(name='gap', lower=.0002, upper=.0004)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
goal = TwoGroundFaceSampledForwardPairDesignDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(
        positive=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)])),
        negative=dict(zip(('bottom','top','left','right'),
            [dict(metal,conductivity=s) for s in (45e6,21e6,35e6,58e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=128,
    interpolation_degree=16,
    targets=dict(differential_forward_impedance_real=[90., 90., 90.],
                 common_forward_impedance_real=[44.5, 44.5, 44.5]),
    tolerances=dict(differential_forward_impedance_real=[.1, .1, .1],
                    common_forward_impedance_real=[.1, .1, .1]),
    initial=[.00038, .00028], max_evaluations=64)
text = goal.dumps()
assert normalize_saved(text) == text
```

`goal.solve()` 또는 `execute_saved(text, max_evaluations=64)`가 검색을 실행한다.
길이는 m, 주파수는 Hz, 목표/허용오차는 ohm이다. 엄격히 증가하는 양수 주파수
2..64개와 각 주파수의 두 명명 물리량별 양수 유한 목표·절대 허용오차가 필요하다.
study/3 또는 /4는 첫 주파수에 고정하며 양수 구간의 corner 변수 두 개를 제공한다.
기존 재료 leaf·고정 피치 바인딩을 적용한다. 검색 중 신호 면·코팅·거칠기·참조 금속은
고정한다.

정규화는 명목·초기값/중점·네 모서리를 전체 주파수와 향후 세 체적/패널/공동 세분에서
검사한다. 장 계산을 하지 않으며 모든 내부점의 유효성을 증명하지 않는다.
누락·추가·중복·비유한·잘못된 필드는 거부한다. 저장된 전체격자 시도 예산
4..10000은 호출자 한도 안에 들어야 한다. 입력 바이트 한도와 미지원 진단도 검색의
장 계산 전에 검사한다.

직접 알고리즘의 완전 복소 전진파 목표와 예약된 동결 세분 세 번을 유지한다.
모든 주파수가 개별 절대 목표와 원 상대 세분 기준 0.005를 만족해야 한다.
캐시에 없는 실패 시도도 예산에 포함한다. 실패 실행은 주파수 벡터·단계·입력·이력과
전류/유전체의 typed 원인 상세를 유지하고 중단은 전파한다. 요청·기록·프로젝트는
추가 계산 없이 복원한다. CLI는 입력 파일을 그대로 두고 결과 receipt를 쓴다.
요청 안에서 성공한 유전체 메시만 재사용하며 전체 경계 전류 재사용을 선택하지 않는다.

물리 전달 시험은 2/3.5/5 GHz·90/44.5 ohm·허용오차 0.1 ohm·초기 폭/간격
0.38/0.28 mm·시도 64회로 저장 검색 전체를 반복한다. 독립 기하 factory로 직접
검색 전체도 반복하여 결과 전체의 정확한 일치를 요구한다. 템플릿 입력은
`dielectric` 층 이름과 명시 최소각을 쓰므로 이전 직접 fixture의 `uniform` 이름과
생략된 기본값은 별도로 기록하며 입력 바이트가 같다고 하지 않는다. 이전 직접
연구의 독립 행렬·세분·유한 외곽 검사는 별도의 수치 근거로 유지한다.

별도 CLI 사례는 앞서 선택된 폭/간격 0.0004327005475196886/
0.0002901571356784889 m에서 시작해 세 세분을 포함한 네 번을 평가한다.
합성 시험은 엄격한 필드·64개 주파수·후속 주파수 재료 거부·모서리/초기 factory·
재료/고정 피치 바인딩·실패 시도·예산·기록 복원을 확인한다. 연속대역 정확도·실측
동등성·임의 외곽 적합성·플랫폼/브라우저 출시 수락을 뜻하지 않는다. 정확히 고정된
공유 기능이 필요하다.
