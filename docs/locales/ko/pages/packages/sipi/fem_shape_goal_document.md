# 저장형 FEM 전류 목표 역산

`FEMShapeLineQuantityDesignDocument`는 [유계 FEM 목표](fem_shape_goal.md)의 단일변수
생성 규칙을 재현 가능한 입력으로 저장합니다. 엄격한 5키는 `schema`, `study`,
`target`, `tolerance`, `max_evaluations`이며 schema는
`sipi.fem-shape-line-quantity-design/1`입니다. 내부
`FEMShapeLineQuantityStudyDocument`가 목표량·기하·고정 양의 주파수·유전체 모델·고정
경계 금속·메시 설정을 제공합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import FEMShapeLineQuantityStudyDocument, FEMShapeLineQuantityDesignDocument

source = ImpedanceStudyDocument(
    'stripline', dict(width=.0004, plane_spacing=.002, eps_r=4.,
                     thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
                  variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
study = FEMShapeLineQuantityStudyDocument(
    source, conductors={'signal': metal}, reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
goal = FEMShapeLineQuantityDesignDocument(study, target=70.35,
                                        tolerance=.2, max_evaluations=12)
assert FEMShapeLineQuantityDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
# design = goal.solve()
```

count=2인 sweep과 양의 구간을 가진 변수 하나를 요구합니다. 두 끝값은 탐색 구간을
정하며 예비 전계 두 번을 별도로 계산하지 않습니다. 목표 계산 전에 원 study를
실행하지 않습니다. 기존 고정 pitch·전체 적층 높이·유전체 숫자 leaf 변환으로 매
후보를 만듭니다. 금속은 고정하고 길이 0·기준 50Ω 선로를 사용하며 원 단일 또는
명시 차동/공통 전류 해석을 유지합니다. 정규화는 전계 계산 없이 수행합니다.

목표와 허용오차의 단위는 선택한 양을 따릅니다. Re Zc·Re Zdd·Re Zcc는 Ω, 감쇠는
Np/m입니다. 감쇠에만 목표 0을 허용하고 허용오차는 양수입니다. 시도 예산은 3..10000
정수이며 동결 입력 메시 세분 한 번을 예약합니다. 내부 커패시턴스·속도 풀이 수가
아닌 시도를 셉니다. 공통 실행 예산이 저장한 예산보다 작으면 풀이 전에 거절합니다.

선택·세분 결과 모두 같은 절대 허용오차를 만족해야 하고 FEM 상대 메시 변화 한계
0.005를 유지합니다. 원 전류 미분·gradient flux·금속 조건은 바꾸지 않습니다.
이분 탐색의 유일성/전역 보장 부재와 별도 외곽·물리 유효성 조건은 직접 API와 같습니다.

공통 실행은 전류 기록 둘을 포함한 전체 설계를 반환합니다. typed 목표 실패는
`status: failed`, null 결과와 전체 오류 사전(시도 횟수·성공 이력·실패 변수/입력·단계·
완료/부분 전류)을 남깁니다. 실행 기록 /1·/2와 프로젝트는 재계산 없이 영수증을
보존합니다. 취소는 전파하며 실패를 부분 수락 설계로 바꾸지 않습니다.

실제 단일·차동 저장 폭 목표를 직접 API 및 독립 특성량 제곱근과 대조하고, field-free
재료/pitch 변환과 정상·실패 기록/프로젝트 왕복을 확인합니다. 전달 전용 시험은 이미
계산한 설계를 명시적으로 재사용합니다. 다른 양의 물리 역산 검증·새 플랫폼 지원·시간
보장·실측 정확도를 추가하지 않습니다. 기존 schema와 기본값은 그대로입니다.

[English](../../../../../packages/sipi/fem_shape_goal_document.md)
