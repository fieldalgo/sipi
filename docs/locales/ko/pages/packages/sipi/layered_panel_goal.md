# 코팅 패널 쌍 선로의 목표 임피던스

기존 `seek_panel_forward_pair_impedances`의 factory는 버전 7 선로를 담은
`PanelTransmissionLineDocument` 버전 2를 명시적으로 반환할 수 있습니다.
두 기하 변수를 바꿀 때 각 경계의 벌크 금속과 순서 있는 평면 코팅은 고정합니다.
기존 패널 전류, 적층 표면 임피던스와 전체 복소 특성 행렬을 사용합니다.

다음 예제는 이미 검증한 점에서 시작하며 명목, 체적만 세분, 패널만 세분,
두 축 동시 세분의 네 계산을 모두 수행합니다. 목표와 다른 점에서 실제 탐색하려면
`initial=[.7e-3,.35e-3]`, `max_evaluations=64`를 사용합니다.
길이는 m, 전도도는 S/m, 목표 임피던스는 Ω입니다.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances

MESH = dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075)


def material():
    return dict(kind='layered', conductivity=58e6, relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])


def factory(width, gap, *, box=.024, air=.010):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=gap, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, box_width=box, air_height=air)
    line = TransmissionLineDocument(CrossSectionDocument(section, mesh=MESH), [1e9],
        materials={}, length=0., conductor=dict(kind='surface-boundaries',
            conductors={t.name:material() for t in section.traces}, reference=material(),
            ground_thickness=35e-6), schema='sipi.transmission-line/7')
    return PanelTransmissionLineDocument(line, schema='sipi.panel-transmission-line/2')


goal = seek_panel_forward_pair_impedances(factory,
    [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125], initial=[.0006073049209836395, .0004082505417130786],
    max_evaluations=4)
assert len(goal.history) == 4
assert all(abs(x) <= tol for x, tol in zip(goal.residuals, goal.tolerances))
```

실제 회귀시험은 103.5177/39.0961Ω에서 시작해 절대 허용차 .25/.125Ω인
110/40Ω 목표를 탐색합니다. 선택 폭과 간격은 약 .607305/.408251mm입니다.
네 해상도 모두 원래 목표와 별도의 0.5% 세분 조건을 충족해야 하며, 동시 세분은
각 단일 축 세분과도 비교합니다. 유한 범위의 국소 탐색으로서 해의 유일성이나
전체 범위에서의 가능성을 보장하지 않습니다.

별도 검사는 선택 기하를 고정하고 동시 세분 해상도로 1·2·4GHz를 계산합니다.
상자 폭/공기 높이는 24/10, 36/15, 48/20mm이며 접지 모드는 512·768·1024입니다.
각 주파수에서 차동 값의 연속 두 변화는 각각 첫 값의 1e-4 이하여야 하고,
공통 값의 두 번째 변화는 첫 번째보다 작아야 합니다. 이 외곽 검사는 역산 API가
자동으로 수행하지 않습니다. 목표 조건은 1GHz에만 적용하며 다른 두 주파수의
목표 충족을 요구하지 않습니다.

독립 평면 전달 행렬로 코팅 임피던스를 확인합니다. 4×4 선로 전달 행렬로 전체
특성 행렬과 길이 20mm 선로의 산란 행렬을 대조하고, 같은 비영 길이에서 상호성과
수동성도 검사합니다. 이 기준은 추출된 RLGC를 재사용하므로 독립 기하 추출이나
실측 정확도 근거가 아닙니다. 수치시험 기록에는 전체 입력·RLGC·경계별 행렬·
전류 적분·탐색 이력을 보존합니다.

작은 상호 저항 항에는 기존 [패널 선로 한계](layered_panel_line.md)가 남아 있습니다.
대각 임피던스 통과로 그 항의 상대 정확도나 무한 영역 극한을 보장하지 않습니다.
코팅 잔여 코어·표피 깊이·패널 기하 제한도 유지합니다. 저장형 패널 목표 wrapper는
기존 버전 1 입력 계약을 사용하며, 이 factory 예제가 코팅 목표 저장 스키마를
추가하는 것은 아닙니다.

[역산 계약](panel_pair_goal.md) · [English](../../../../../packages/sipi/layered_panel_goal.md)
