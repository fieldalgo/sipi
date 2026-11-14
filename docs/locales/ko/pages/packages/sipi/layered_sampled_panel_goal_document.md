# 코팅 선로의 유한 주파수 목표 저장

명시적 `sipi.sampled-panel-forward-pair-design/2` 입력은 유한 주파수 벡터에서
line/7의 고정 금속 법칙과 panel-line/2 전류 방법을 보존합니다. 생성자에
`schema='sipi.sampled-panel-forward-pair-design/2'`를 지정합니다.
기본값은 버전 1이며 기존 line/6 금속 계약을 유지합니다. 코팅 FEM 목표로
암묵적으로 변환하지 않습니다.

필드는 `schema`, `study`, `conductor`, `panel`, `frequency_hz`, `targets_ohm`,
`tolerances_ohm`, `initial`, `max_evaluations`의 9개입니다. 두 목표 맵에는
`differential_forward_impedance_real`, `common_forward_impedance_real`이
모두 필요하며 각각 주파수마다 양의 유한값 하나를 지정합니다. 전체 복소 혼합
특성 행렬의 대각 실수부이며 허수부나 분리된 모드의 목표가 아닙니다.

```python
import numpy as np
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
         substrate_height=.5e-3, eps_r=4., tan_delta=.02,
         left_thickness=35e-6, right_thickness=50e-6,
         box_width=.024, air_height=.010),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.4e-3, upper=.9e-3),
        dict(name='gap', lower=.2e-3, upper=.6e-3)]))

def metal():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])

dd = 'differential_forward_impedance_real'
cc = 'common_forward_impedance_real'
request = SampledPanelForwardPairDesignDocument(study,
    conductor=dict(kind='surface-boundaries',
        conductors={'positive':metal(), 'negative':metal()}, reference=metal(),
        ground_thickness=35e-6),
    frequencies=[1e9,2e9,4e9], targets={dd:[110.]*3, cc:[40.]*3},
    tolerances={dd:[.25]*3, cc:[.125]*3},
    initial=[.0006050501120606677,.0004089487094424394], max_evaluations=4,
    schema='sipi.sampled-panel-forward-pair-design/2')
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] == 'complete' and output['error'] is None
result = output['result']
assert result['evaluations'] == 4
assert np.all(abs(np.asarray(result['residuals_ohm'])) <= result['tolerances_ohm'])
```

예제는 검증한 후보에서 시작하여 명목·체적만 세분·패널만 세분·동시 세분을
수행합니다. [직접 API 계약](layered_sampled_panel_goal.md)의 실제 탐색에는
`initial=[.7e-3,.35e-3]`, `max_evaluations=64`를 사용하며 공통 실행의 예산도
저장 예산 이상으로 지정합니다. 실패 시도까지 포함해 한 시도는 전체 주파수
배치이며 내부 전계 풀이 수나 시간의 상한이 아닙니다. 세분 시도 3개를 예약합니다.

파싱은 전계를 계산하지 않습니다. 증가하는 양의 주파수 2~64개, 첫 주파수와
study 기준 주파수의 일치, 엄격한 키·유한값, 명목·초기값/중점·네 모서리 입력과
각 미래 세분을 검사합니다. 전체 주파수 벡터가 각 재료의 허용 대역과 코팅·코어·
표피 깊이 조건에 들어야 합니다. 이 유한 사전 검사는 변수 범위의 모든 내부점이나
주파수 사이의 유효성을 보장하지 않습니다.

고정 피치·재료 수치 변수·변수 순서는 원래 study 의미를 유지합니다. 코팅은
고정 정보이며 새로 표본화하거나 최적화하는 변수가 아닙니다. 공통 실행은 예산
부족과 진단 옵션 덮어쓰기를 풀이 전에 거부합니다. 배치 실패에는 단계·전체
주파수·시도 입력·완료 이력·원래 원인을 보존합니다.

검증에는 버전 분리·전 주파수 사전 검사·각 세분 단계 실패·고정 피치/재료 변수,
실제 코팅 배치와 직접/공통 실행의 정확 재생을 포함합니다. 기존 버전 1의 정규
입력과 실제 저장 실행 하나의 불변성도 대조합니다. 별도 전달 행렬로 코팅·전체
특성 행렬·비영 길이 네트워크를 확인합니다. 유한 외곽과 작은 상호 항의 한계는
직접 API와 같으며 저장 계약이 연속 대역이나 실측 정확도를 추가 보증하지 않습니다.

[단일 주파수 목표 저장](layered_panel_goal_document.md) ·
[English](../../../../../packages/sipi/layered_sampled_panel_goal_document.md)
