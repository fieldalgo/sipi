# 코팅 패널 쌍 선로 공차와 동시 수락

명시적인 `sipi.panel-forward-pair-study/2`는 기존 쌍 선로 표본 계산을
line/7·panel-line/2에 연결합니다. 최상위 키는 `schema`, `study`,
`conductor`, `panel`입니다. 신호 및 기준 경계마다 벌크 금속과 순서 있는
평면 코팅은 고정합니다. 기하·지원 유전체 재료 변수는 기존 study의 의미를
유지합니다. 코팅 두께를 새로운 확률 변수로 추가한 것은 아닙니다.

요청한 표본을 순서대로 모두 시도하고 한 추출에서 Re(Zdd)·Re(Zcc)를 구합니다.
두 값을 독립 전파 모드로 해석하지 않습니다. 중복도 별도 행으로 남으며,
실패 단계·입력을 보존하고 이후 표본도 계속 계산합니다. 실패한 쌍의 일부 값만
성공으로 남기지 않으며 모든 행이 완료되어야 기술통계를 제공합니다.
표본을 잘라내거나 다시 뽑지 않습니다.

명시적인 `sipi.panel-forward-pair-yield/2`는 버전 2 패널 study만 받고,
버전 1은 기존 버전 1 입력을 유지합니다. 각 제조 표본에서 두 임피던스가 모두
포함 경계값을 만족해야 합격이며, 주변 합격률 두 개의 곱으로 계산하지 않습니다.
IID uniform·normal 표본만 허용하고 한 표본 안 변수의 상관관계는 허용합니다.
실패한 쌍도 원래 분모에 미해결로 남습니다. 기존 Clopper–Pearson 구간은
미해결 행의 가능한 모든 합격·불합격 조합을 포함하며 전계·재료·분포 오차를
포함하지 않습니다.

다음은 저장 실행을 보여주는 두 표본 예제이며 높은 생산 수율의 근거가 아닙니다.
길이는 m, 표준편차는 해당 변수 단위, 전도도는 S/m, 임피던스 한계는 Ω입니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_pair_yield import PanelForwardPairYieldDocument
from sipi.execution import execute_saved

width, gap = .0006073049209836395, .0004082505417130786
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=width, right_width=.5e-3, gap=gap,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='normal', count=2, seed=3,
        correlation=[[1., .5], [.5, 1.]], variables=[
            dict(name='left_width', mean=width, std=10e-6),
            dict(name='gap', mean=gap, std=5e-6)]))
metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
              dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
study = PanelForwardPairStudyDocument(source,
    conductor=dict(kind='surface-boundaries', conductors=dict(positive=metal, negative=metal),
                   reference=metal, ground_thickness=35e-6),
    schema='sipi.panel-forward-pair-study/2')
request = PanelForwardPairYieldDocument(study, acceptance={
    'differential_forward_impedance_real': dict(minimum=109., maximum=111.),
    'common_forward_impedance_real': dict(minimum=39.75, maximum=40.25)},
    confidence=.95, minimum_yield=.9, schema='sipi.panel-forward-pair-yield/2')
output = execute_saved(request.dumps(), max_evaluations=2)
assert output['status'] == 'complete' and output['result']['count'] == 2
assert output['result']['event'] == 'both-paired-forward-impedance-limits'
```

정규화는 전계 계산 없이 명목 금속·패널 조건을 검사합니다. 전계 계산 전에
표본 전체와 필요한 예산을 정합니다. 각 표본의 코팅 코어·표피 깊이·패널 기하
조건도 충족해야 하며 명목 조건의 유효성이 모든 난수 표본을 보장하지 않습니다.
기존 버전 1 정규화 입력과 수치 동작은 그대로 유지합니다.

수치 회귀는 제시한 평균에서 표준편차 폭 10µm·간격 5µm, 상관계수 .5,
seed 3인 normal 8개 표본을 사용합니다. 각 행을 독립 코팅 전달·전체 특성·
20mm 산란 기준과 비교합니다. 체적만·패널만·동시 세분을 나누어 각 순방향
대각 값의 변화가 0.5% 이하여야 하며 동시 세분은 각 단일 축과도 비교합니다.
이 수치 검사는 제조 허용 범위와 다릅니다. 올바르게 계산된 표본도 목표 범위를
벗어날 수 있습니다. 전체 전계 입력·행렬·전류 적분과 표본 순서를 보존합니다.

고정된 이 8개 표본에서 명목·패널 세분은 6개, 체적·동시 세분은 7개가 합격합니다.
한 차동 값이 108.9822Ω에서 109.0205Ω으로 바뀌며 109Ω 하한을 넘습니다.
따라서 0.5% 수치 변화 조건을 충족해도 규격 경계 근처의 합격 라벨이 안정적이라고
보장하지 않습니다. 명목 95% 구간 약 [.3491, .9681]은 이 이산화 불확실성을
포함하지 않습니다.

study API는 모든 행을 자동 세분하거나 외곽 오차를 보증하지 않습니다.
평균 기하에는 [코팅 쌍 역산](layered_panel_goal.md)의 별도 유한 영역 관측이
있지만 모든 표본의 외곽 수렴을 확정하지 않습니다. 작은 상호 저항 및 실측
정확도 한계도 유지합니다. 통계 구간은 제시한 표본 모델에 대한 것이며 실측
생산 수율을 뜻하지 않습니다.

[쌍 표본 계산](panel_pair_study.md) · [동시 수락](panel_pair_yield.md) ·
[English](../../../../../packages/sipi/layered_panel_study.md)
