# 모서리 해상도를 명시한 FEM 선로 목표 저장

`CornerFEMShapeLineQuantityDesignDocument`는
`sipi.corner-fem-shape-line-quantity-design/1`의 `schema`, `design`,
`corner_size` 세 키를 저장합니다. 내부의 기존 FEM 목표는 양수 범위의 변수
하나, count=2 sweep, 물리량, 목표값, 허용 오차와 평가 예산을 유지합니다.
별도 모서리 크기는 미터 단위의 유한 양수이며 nominal 해석 edge 크기보다
클 수 없습니다. 입력 정규화는 장을 풀지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi import (FEMShapeLineQuantityStudyDocument,
                  FEMShapeLineQuantityDesignDocument,
                  CornerFEMShapeLineQuantityDesignDocument)
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.0004, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008),
    quantity='z0', frequency=2e9, materials={},
    mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.00039, upper=.00041)]))
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))
study = FEMShapeLineQuantityStudyDocument(source,
    conductors=dict(signal=metal), reference=metal,
    ground_thickness=35e-6, quantity='impedance_real')
design = FEMShapeLineQuantityDesignDocument(study,
    target=70.35, tolerance=.2, max_evaluations=12)
saved = CornerFEMShapeLineQuantityDesignDocument(design, corner_size=2.5e-6)
assert normalize_saved(saved.dumps()) == saved.dumps()
# result = saved.solve()
```

각 매개변수에서 기존 기하 또는 유전체 숫자 잎 변환을 다시 평가합니다.
고정 피치·높이와 경계 금속의 의미를 유지하며 원본 study 표본을 먼저 풀지
않습니다. factory 결과는 길이 0, 주파수 하나의 명시적 corner FEM 선로입니다.

직접 corner 목표 API가 세분 평가 한 번을 예약합니다. 선택한 물리 입력을
동결하고 edge, far, grade, corner를 절반으로 줄입니다. 기존 절대 목표 오차와
0.005 상대 메시 변화 기준을 모두 적용합니다. 단일 선로의 실수 임피던스·감쇠,
쌍 선로의 차동·공통 순방향 실수 임피던스는 기존 입사 조건을 유지합니다.
유한 구간 역산은 전역 최적화나 일반 정확도 인증이 아닙니다.

공통 실행기는 계산 전에 내부 목표 예산을 확인합니다. 요청·기록·프로젝트는
선택·세분 입력, 탐색 이력과 단계 오류의 부분 전류 근거를 보존합니다.
기록을 다시 열어도 재계산하지 않습니다. 모서리 설정을 변경하면 현재 결과
연결만 무효화하고 과거 기록은 남깁니다. 호스트 예산은 선로 평가 횟수이며
각 평가에는 여러 장 풀이가 포함됩니다. 목표의 진단 요청은 거부합니다.

검증 범위는 엄격한 입력 해석, 재료·고정 피치 변환, 계산 전 예산,
기존 저장 계약 및 실제 단일·쌍 선로 목표와 직접 API 결과 대조입니다.
소스와 설치 산출물을 별도로 확인합니다. 모든 기하, 작은 상호 손실의 수렴,
새 플랫폼 또는 배포 프로그램을 인증하지 않습니다. 기존 스키마가 암묵적인
corner 키를 거부하는 동작은 그대로입니다.

[English](../../../../../packages/sipi/corner_fem_goal_document.md)
