# 면별 금속 단일 변수 설계 저장 입력

[English](../../../../../packages/sipi/two_ground_corner_face_line_goal_document.md)

`TwoGroundCornerFaceLineQuantityDesignDocument`는
`sipi.two-ground-corner-face-line-quantity-design/1`을 저장한다. 중첩된
[면별 단일량 연구](two_ground_corner_face_line_study.md)와 목표·절대 허용오차·최대 시도를
묶어 [직접 면별 목표](two_ground_corner_face_line_goal.md)의 재현 가능한 factory를 구성한다.
함수 자체를 직렬화하지 않는다. 기존 전체 경계 입력·실행 경로·수치 기준은 유지한다.

다음 예제는 장 계산 없이 입력 준비와 정규화를 한다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_corner_face_line_study import TwoGroundCornerFaceLineQuantityStudyDocument
source = ImpedanceStudyDocument('offset_stripline',
    dict(width=.0006, plane_spacing=.002, trace_height=.0007, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    sampling=dict(kind='sweep', count=2, variables=[
        dict(name='width', lower=.00055, upper=.00065)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundCornerFaceLineQuantityStudyDocument(source, quantity='impedance_real',
    conductors=dict(signal=dict(zip(('bottom','top','left','right'),
        [dict(metal,conductivity=sigma) for sigma in (58e6,35e6,21e6,45e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6), sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=256, interpolation_degree=24)
assert TwoGroundCornerFaceLineQuantityStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 2

from sipi.two_ground_corner_face_line_goal_document import TwoGroundCornerFaceLineQuantityDesignDocument
design = TwoGroundCornerFaceLineQuantityDesignDocument(study, target=58., tolerance=.05,
                                            max_evaluations=40)
assert TwoGroundCornerFaceLineQuantityDesignDocument.loads(design.dumps()).dumps() == design.dumps()
```

엄격한 루트 키는 schema·study·target·tolerance·max_evaluations 다섯 개다.
중첩 면별 연구는 count=2인 sweep과 양수·비퇴화 구간 하나를 제공해야 한다.
count=2는 구간 양끝을 정하며 검색 전에 그 표본을 먼저 계산하지 않는다.
study/3 또는 /4의 기하/재료 바인딩·고정 피치·접지 간격 변환을 유지한다.
선택한 물리량이 단선/쌍의 입장 조건과 단위를 정한다. 특성 임피던스 실수부는 ohm,
감쇠는 Np/m이며 감쇠만 목표 0을 허용한다. 절대 허용오차는 양수다.

명목·양끝·중점과 각각의 체적·패널·공동 세분 입력을 사전 검사한다. 구간 내부의
유효성이나 목표 도달 가능성을 보장하지 않는다. 누락/추가·중복·비유한 필드는 거부하고
전체 경계 study 객체도 거부한다. 저장 값은 분리된 스냅샷이다.

`design.solve()`와 `execute_saved(design.dumps(), max_evaluations=40)`는 같은
직접 알고리즘을 쓴다. 장 계산 전에 host 예산이 저장 예산 5..10000을 포함해야 한다.
세분용 평가 세 번을 예약하며 실패도 시도로 센다. 원 절대 목표와 모든 상대 0.005
기준을 유지한다. 동결 입력은 물리적 면·코팅·거칠기·참조 금속·유전체 바인딩을
보존한다. 숨은 선행 연구·대체 경로·재시도는 없다. 실패는 typed 원인·이력·확보한
전류/메시 관측을 보존하며 중단은 전파한다.

요청·기록·프로젝트는 다시 계산하지 않고 입력/결과를 결합하고 복원한다. 기존 CLI는
이 schema를 검증·실행하며 입력 바이트를 유지하고 결과 receipt를 쓴다.
브라우저 UI·Worker 일치·실행 파일 패키징은 별도 검증이다.

물리 저장 사례는 직접 사례와 같은 비대칭 높이 기하·2 GHz·58 ohm ±0.05·
폭 0.55–0.65 mm·패널 128→256·시도 40회다. 각 실제 장 결과를 독립 복소
sqrt(Z/Y)와 sqrt(ZY)에 1e-12로 대조하고 저장 결과를 이전 직접 결과 및 정확한
설치본 receipt와 비교한다. 별도 CLI 사례는 기록된 선택 폭 0.000590625 m를 하한,
0.00065 m를 상한으로 하여 다섯 번(양끝과 세 세분) 평가한다. 이는 저장 목표 전체
검색 시험을 대체하지 않는다. 네 물리량·엄격한 중첩·입장 조건·재료·고정 피치·실패
단계·예산·중단·프로젝트 복원도 검증한다. 실측 정확도·생산 수율·임의 외곽 적합성의
인증은 아니다.
