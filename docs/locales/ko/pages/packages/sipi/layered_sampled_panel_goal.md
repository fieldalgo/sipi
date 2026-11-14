# 코팅 쌍 선로의 유한 주파수 공동 역산

`seek_sampled_panel_forward_pair_impedances`에 코팅 금속 line/7을 담은
명시적 panel-line/2 factory를 사용할 수 있습니다. 하나의 폭·간격이 주어진
모든 주파수에서 전체 복소 특성 행렬의 차동·공통 실수부 목표를 충족해야 합니다.
각각 공통 전류가 0인 Re(Zdd), 차동 전류가 0인 Re(Zcc)이며 허수부는 목표가 아닙니다.
각 금속의 순서 있는 코팅과 벌크 특성은 탐색 내내 고정합니다.

예제는 검증한 후보에서 시작하면서도 네 가지 독립 해상도 검사를 수행합니다.
목표와 다른 지점에서 실제 탐색하려면 `initial=[.7e-3,.35e-3]`,
`max_evaluations=64`를 사용합니다. 예산의 한 시도는 주어진 전체 주파수 벡터를
계산하며 내부 전계 풀이 수·메모리·시간을 제한하지 않습니다. SI 단위와 Ω 절대
허용차를 사용합니다.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances
import numpy as np

MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def factory(width, gap, *, box=.024, air=.010):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=gap, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, box_width=box, air_height=air)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9,2e9,4e9],
        materials={}, length=0., conductor=dict(kind='surface-boundaries',
            conductors={t.name:material() for t in section.traces}, reference=material(),
            ground_thickness=35e-6), schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, schema='sipi.panel-transmission-line/2')


goal = seek_sampled_panel_forward_pair_impedances(factory,
    [[.4e-3, .9e-3], [.2e-3, .6e-3]], [1e9,2e9,4e9],
    [[110.,40.]]*3, tolerances=[[.25,.125]]*3,
    initial=[.0006050501120606677, .0004089487094424394], max_evaluations=4)
assert len(goal.history) == 4
assert np.all(abs(np.asarray(goal.residuals)) <= goal.tolerances)
```

이 계약은 증가하는 양의 주파수 2~64개를 받습니다. 예제는 1·2·4GHz 모두에
110/40Ω 목표와 .25/.125Ω 허용차를 동시에 적용합니다. 최초 기하는 1GHz에서
약 103.52/39.10Ω로 목표를 벗어나며, 선택 폭·간격은 약 .605050/.408949mm입니다.
시험은 실제 유한 범위 탐색을 요구하고 모든 시도 입력과 완료 결과를 보존합니다.
최적화기가 성공을 반환해도 모든 목표를 충족하지 않으면 실패합니다.

명목·체적만 세분·패널만 세분·동시 세분 각각에서 모든 주파수 목표를 충족해야
합니다. 동시 세분과 두 개별 세분의 비교를 포함해 기존 0.5% 변화 기준도
유지합니다. 코팅 깊이·잔여 코어·패널 기하 허용 조건은 각 배치의 전계 계산 전에
적용합니다. 실패에는 정확한 단계·주파수 벡터·시도 입력을 남깁니다.

별도 회귀시험은 선택 기하와 동시 세분 해상도를 고정하고 상자 폭/공기 높이
24/10·36/15·48/20mm, 접지 모드 512·768·1024를 사용합니다. 모든 주파수에서
차동 값의 연속 두 변화가 각각 첫 값의 1e-4 이하여야 하며, 공통 값의 두 번째
변화는 첫 번째보다 작아야 합니다. API가 이 외곽 검사를 자동으로 실행하지는
않습니다. 유한한 관측의 통과는 무한 영역 오차 상한이 아닙니다.

독립 평면 전달 행렬로 코팅을 확인하고 전체 4×4 전달 행렬로 특성 행렬과 20mm
선로의 산란 행렬을 대조합니다. 같은 비영 길이에서 상호성과 수동성도 확인합니다.
이 대조는 추출 RLGC를 재사용하므로 독립 기하 추출이나 실측 정확도 검증을 뜻하지
않습니다. 작은 상호 저항 항에는 별도의 정확도 한계가 남아 있습니다.

출력은 명시한 주파수와 유한 범위의 국소 탐색만 설명합니다. 주파수 사이의 값,
연속 대역의 가능성, 전역 최적해나 생산 수율을 보장하지 않습니다. 기존 단일
주파수 API와 저장 계약의 의미는 유지합니다.

[버전 2 저장 요청](layered_sampled_panel_goal_document.md)은 코팅 factory 입력과
전체 주파수 배치 예산을 공통 실행에서도 보존합니다.

[단일 주파수 코팅 역산](layered_panel_goal.md) ·
[유한 주파수 계약](sampled_panel_pair_goal.md) ·
[English](../../../../../packages/sipi/layered_sampled_panel_goal.md)
