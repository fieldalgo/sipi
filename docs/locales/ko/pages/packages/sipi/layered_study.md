# 고정 금속 도금층의 기하·유전체 공차 평가

명시 버전 `sipi.line-quantity-study/4`는 각 표본에 transmission-line/7을 사용합니다.
study/3의 단일 선로 실수 임피던스·감쇠와 쌍 선로 차동·공통 전방 실수 임피던스
정의를 유지하면서 [도금 표면 재료](layered_metal.md)를 보존할 수 있습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
from sipi.execution import normalize_saved

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6, eps_r=4., box_width=4e-3),
    quantity='z0', frequency=1e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=123,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.)])
study = LineQuantityStudyDocument(source, quantity='impedance_real',
    conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                   reference=metal, ground_thickness=35e-6),
    schema='sipi.line-quantity-study/4')
assessment = LineQuantityYieldDocument(study, minimum=40., maximum=60.,
    confidence=.95, schema='sipi.line-quantity-yield/3')
assert normalize_saved(assessment.dumps()) == assessment.dumps()
```

표본은 기하와 유전체 변수를 바꿉니다. **금속 도금 두께·전도도·투자율은 모든 표본에서
고정됩니다.** 금속 제조 분포 추정이나 도금 동시 피팅을 수행하지 않습니다. 각 행은
원래 표본 벡터, 생성 기하·재료, 생성에 성공한 line/7 입력, 결과 또는 실패 단계·오류를
보존합니다. 남은 코어가 표피 깊이 조건을 어기는 표본도 입력 실패 행으로 남깁니다.
다음 행을 계속 시도하며 실패를 자르거나 다시 뽑거나 제거하지 않습니다. 실패가 있는
study에는 성공한 일부 행만의 수치 요약을 만들지 않습니다.

명시 yield/3은 study/4를 허용합니다. iid 균일·정규 표본이 필요하며 정규 분포의 한
행 안에서 변수 사이 상관은 허용합니다. 미해결 행도 분모와 기존 Clopper–Pearson
구간에 포함합니다. 이 구간은 명시 분포 아래 표본 오차에 관한 것이며 실제 생산 수율,
전계 이산화·재료 피팅·모델 불확실성을 포함하지 않습니다. 실행 예산은 전계 계산 전에
검사합니다.

study/1..3은 계속 line/6을 생성합니다. yield/1은 study/1..2, yield/2는 study/1..3만
허용합니다. 기존 yield-design 후보 선택도 이전 study 계약을 유지합니다. 새 study를
읽을 수 있다는 이유로 이전 소비자의 범위를 자동 확대하지 않습니다. 저장 목표 역산의
1~3 버전도 기존 도체 형식을 유지하며, 명시 goal/4가 고정 도금층을 연결합니다.

표본 RLGC를 직접 line/7 호출로 재생하고, 단일 선로는 독립 2×2 행렬 지수와 비교합니다.
쌍 선로의 전방 입력은 실제 메시 비대칭을 보존한 4×4 전달 행렬의 성장 고유공간으로
대조합니다. 상관 표본 벡터, 실제 코어 실패, 독립 유한 이항합 구간과 이전 값의 보존도
검사합니다. 이러한 연결 검증은 도금 국소 모델의 전계·메시·외곽 검증을 대신하지 않습니다.

[명시 goal/4](layered_goal.md)는 고정 도금층의 단일 변수 목표 역산을 연결합니다.

[명시 yield-design/4](layered_selection.md)는 동시 수율 구간으로 고정 도금 후보군을 비교합니다.
