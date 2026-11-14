# 고정 금속 도금층의 저장 목표 역산

명시적 `sipi.line-quantity-design/4`는 [층상 표면 금속](layered_metal.md)을
기존 단일 변수 손실 포함 목표 탐색에 연결하며 transmission-line/7 입력을
보존합니다. 이전 1~3 버전은 line/6 및 기존 허용량을 유지하고 생성자 기본값도
버전 1 그대로입니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
         eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
goal = LineQuantityDesignDocument(source,
    conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                   reference=metal, ground_thickness=35e-6),
    quantity='impedance_real', target=50., tolerance=.5, max_evaluations=24,
    schema='sipi.line-quantity-design/4')
assert normalize_saved(goal.dumps()) == goal.dumps()
```

`goal.solve()`는 지정 구간의 기하 또는 유전체 변수 하나를 탐색합니다. 도금층
두께·전도도·투자율은 고정합니다. 단일 신호 목표는 특성 임피던스 실수부(Ω)
또는 전파 감쇠(Np/m)입니다. 쌍 신호는 명시적인 순방향 차동/공통 전류 입력의
특성 임피던스 실수부이며 비대칭 결합 행렬을 보존합니다. 유한 종단 임피던스나
삽입 손실이 아니며 두 변수 동시 탐색을 뜻하지 않습니다.

선택 입력과 별도로 세분한 메시 모두 같은 절대 허용오차를 만족해야 합니다.
입력 기록은 층 순서·재료값·원본 기하 제약을 유지합니다. 부적합 코어, 표피 깊이
위반, 목표 구간 부재, 예산 소진은 원래 시도 횟수·완료 이력·실패 단계를 남깁니다.
실패 후보를 잘라내거나 수정·교체하지 않습니다. 읽기와 예산 검사는 장을 풀지 않습니다.

외곽 유효성은 탐색의 메시 검사와 별개입니다. 시험은 유한 두께 스트립라인의
상자 두 배 검사, 직접 API 재생, 단일 2×2 전달행렬 및 쌍 신호 4×4 순방향 고유공간
비교를 포함합니다. 전달행렬 비교는 같은 추출 RLGC를 사용하므로 장 정확도의
독립 검증은 아닙니다. 국소 평면 도금 모델의 문서화된 기하 한계가 유지되며
실측 동박 정확도나 모든 기하의 수렴을 보증하지 않습니다. 결과는 구간 안의
후보이며 전역 최적해나 제조 수율 인증이 아닙니다.

[English](../../../../../packages/sipi/layered_goal.md)
