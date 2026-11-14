# 코팅 제조 표본의 유한 주파수 평가

명시적 `sipi.sampled-panel-forward-pair-study/2`는 line/7의 고정 코팅과
panel-line/2 전류 방법을 보존합니다. 하나의 제조 기하·재료 표본을 주어진
전체 주파수 벡터에서 평가합니다. 기본값 버전 1과 기존 금속 계약은 유지하며,
버전 2도 `schema`, `study`, `conductor`, `panel`, `frequency_hz`의 5개 필드를
사용합니다.

명시적 `sipi.sampled-panel-forward-pair-yield/2`에는 버전 2 study가 필요합니다.
필드는 기존과 같은 `schema`, `study`, `acceptance`, `confidence`,
`minimum_yield`입니다. 한 제조 표본의 두 실수부 임피던스가 모든 지정 주파수의
경계를 포함한 조건을 충족해야 합격입니다. 통계의 시행 수는 iid 표본 수이며
여기에 주파수 수나 평가량 수를 곱하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.sampled_panel_pair_yield import SampledPanelForwardPairYieldDocument
from sipi.execution import execute_saved, normalize_saved

width, gap = .0006050501120606677, .0004089487094424394
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=width, right_width=.5e-3, gap=gap, substrate_height=.5e-3,
         eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='normal', count=2, seed=3, correlation=[[1.,.5],[.5,1.]], variables=[
        dict(name='left_width', mean=width, std=10e-6),
        dict(name='gap', mean=gap, std=5e-6)]))

def metal():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])

study = SampledPanelForwardPairStudyDocument(source, frequencies=[1e9,2e9,4e9],
    conductor=dict(kind='surface-boundaries',
        conductors={'positive':metal(), 'negative':metal()}, reference=metal(),
        ground_thickness=35e-6), schema='sipi.sampled-panel-forward-pair-study/2')
request = SampledPanelForwardPairYieldDocument(study, acceptance={
    'differential_forward_impedance_real': dict(minimum=[109.]*3, maximum=[111.]*3),
    'common_forward_impedance_real': dict(minimum=[39.75]*3, maximum=[40.25]*3)},
    confidence=.95, minimum_yield=.9, schema='sipi.sampled-panel-forward-pair-yield/2')
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=2)
assert output['status'] == 'complete' and output['error'] is None
result = output['result']
assert result['count'] == 2 and result['frequencies_hz'] == [1e9,2e9,4e9]
assert all(len(row['values_ohm']) == 3 for row in result['rows'])
assert result['goal_status'] == 'undetermined'
```

예제의 두 표본은 실행을 보여주며 생산 수율 90%의 근거가 아닙니다. 계산이
완료되어도 통계적 목표는 미확정일 수 있습니다. 정확 이항 구간은 원래 미해결
행을 원래 분모에 포함한 범위를 사용합니다. 이는 주어진 분포와 수치 모델에
조건부인 결과로서 기하 추출·이산화·실측 오차 상한이 아닙니다. 1GHz에서 합격한
표본이 4GHz에서 공동 조건을 벗어날 수 있습니다.

study는 기존 sweep/corners/uniform/correlated-normal 계획을 지원하고 iid 수율은
uniform/normal만 받습니다. 첫 주파수는 study 기준 주파수와 일치해야 하며,
양수·증가 순서인 2~64개 전체 벡터에 대해 명목 재료 대역·코팅/코어·표피 깊이·
패널 허용 조건을 검사합니다. 모든 표본 벡터는 전계 계산 전에 생성하며 주파수별로
다시 뽑지 않습니다. 각 행은 실제 매개변수·재료 평가·정확한 입력·전체 주파수×2
결과를 보존합니다. 실패한 배치의 일부 값만 합격 처리하지 않고 후속 행도 계속
시도합니다. 잘라내기나 실패 행 제거로 분포를 바꾸지 않습니다. 기술 통계는 모든
행이 완료된 경우에만 주파수별로 제공합니다.

`max_evaluations`는 제조 표본의 전체 주파수 배치를 셉니다. 예산 부족은 전계
계산 전에 거부하며 실패한 행도 원래 위치를 유지합니다. 내부 전계 풀이 수·시간·
메모리의 상한은 아닙니다. 코팅 적층은 고정 정보이며 코팅 두께 확률변수를 추가한
계약은 아닙니다. 고정 피치와 유전체 재료 수치 변수는 기존 source 규칙을 따릅니다.

기존 고정 후보 선택은 명시한 버전 2 study를 하위 입력으로 보존할 수 있습니다.
후보군 예산과 동시 신뢰구간 배분은 계속 후보 수와 제조 표본 수를 기준으로 하고
주파수 수를 추가로 곱하지 않습니다. 모든 입력에 명시한 버전을 남기며 기본 전류
방법을 바꾸지 않습니다.

수치 검증은 고정된 상관 표본 8개를 1·2·4GHz에서 명목·체적만 세분·패널만 세분·
동시 세분으로 관측합니다. 표본의 최소·최대 폭 두 지점은 동시 세분 상태에서
별도로 유한 외곽을 검사합니다. 기존 대각 임피던스 세분·외곽 조건을 그대로 두고
작은 상호 행렬 항도 별도 보존합니다. 각 배치에 독립 코팅 전달·전체 특성 행렬·
20mm 네트워크 기준을 적용합니다. 회귀시험은 첫 두 행과 외곽 두 끝점을 재계산하고,
통계·배치 전체 실패·정확한 공통 재생·설치 입력을 확인합니다. 이 유한 관측이
무한 정규분포의 모든 꼬리를 검증하거나 명목 수율 구간에 수치 오차를 포함하지는
않습니다.

[고정 주파수 코팅 공차](layered_panel_study.md) ·
[코팅 주파수 벡터 목표](layered_sampled_panel_goal_document.md) ·
[English](../../../../../packages/sipi/layered_sampled_panel_study.md)
