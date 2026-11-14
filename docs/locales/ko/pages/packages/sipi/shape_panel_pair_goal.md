# 명시 형상전류 쌍 선로 임피던스 역산

`seek_shape_panel_forward_pair_impedances`는 [정전용량 형상미분 전류](panel_shape_conductor.md)를
기존 범위 제한 2변수 탐색에 연결합니다. factory는
`ShapePanelTransmissionLineDocument`를 반환해야 합니다. 기존 패널·체적 선로
역산을 자동 전환하지 않습니다. 기존 경계별 금속과 고정 코팅은 원래 재료·표피
깊이 규칙을 유지합니다.

목표는 전체 복소 특성 행렬로 구한 실수 순방향 차동·공통 임피던스(Ω)입니다.
전력 쌍대 좌표 Vd=V1−V2, Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2에서
각각 Ic=0, Id=0으로 여기합니다. 모드 크기나 종단 입력 임피던스가 아닙니다.

factory는 양의 범위 안 두 변수·순서 있는 신호 두 개·고정 양의 주파수 하나·
길이 0을 사용합니다. 탐색 중 패널 수·접지 모드 수·보간 차수·`step_fraction`은
고정됩니다. 최적화·캐시·예산은 [패널 쌍 역산](panel_pair_goal.md)과 같습니다.
`max_evaluations`(정수 4–10000)는 실패·최적화 탐침을 포함한 캐시되지 않은
선로 전체 평가 횟수입니다. 내부 패널 풀이·시간·메모리의 한도가 아닙니다.

선택 입력을 고정한 뒤 체적 메시 제어 반감·패널 수 두 배·둘 다 적용한 세 번의
실제 평가를 예약합니다. 접지 모드·보간·형상 미분폭은 유지합니다. 탐색 필드를
풀기 전 후속 입력도 검사합니다. 네 결과 모두 원래 두 목표의 절대 허용값을
만족해야 합니다. 각 세분 결과는 기본값 대비 0.5% 이내이고, 동시 세분은 각각의
단독 세분 대비도 0.5% 이내여야 합니다. 초기값이 목표를 맞춰도 네 평가가 필요하며
실패한 목표를 수락된 설계로 반환하지 않습니다.

`ShapePanelForwardPairDesign`은 선택·세분 전체 결과와 새 형상문서 접근자를
보존합니다. `to_dict()`는 그 네 결과의 모든 전류 표본·두 미분폭 진단을 담고,
탐색 이력에는 완료한 입력·임피던스를 담습니다. 이는 보고서이며 factory나 요청의
새 저장 스키마가 아닙니다. `ForwardPairGoalError`는 평가 횟수·완료 이력·단계·
실패 변수/입력·원래 예외 연결을 보존합니다. 원인이 `ShapePanelLineError`이면
그 예외의 `to_dict()`에서 완료·부분 전류를 확인할 수 있습니다. 중단은 전파합니다.
기존 방식·JSON 입력·수치 수락 기준은 유지합니다.

예제는 목표 허용 범위 밖에서 시작합니다. 길이는 m, 전도도는 S/m, 허용값은 Ω입니다.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.shape_panel_pair_goal import seek_shape_panel_forward_pair_impedances
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument

def line(width, gap):
    section = asymmetric_coupled_microstrip(
        left_width=width, right_width=.5e-3, gap=gap,
        substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6,
        box_width=24e-3, air_height=10e-3)
    def surface(conductivity, rms):
        return dict(conductivity=conductivity, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    conductor = dict(kind='surface-boundaries',
        conductors={'positive': surface(58e6, .5e-6),
                    'negative': surface(35e6, 1e-6)},
        reference=surface(58e6, 0.), ground_thickness=35e-6)
    return TransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(
            edge_size=2.5e-6, far_size=.25e-3, grade=.075)),
        [1e9], materials={}, conductor=conductor, length=0.,
        schema='sipi.transmission-line/6')

goal = seek_shape_panel_forward_pair_impedances(
    lambda width, gap: ShapePanelTransmissionLineDocument(
        PanelTransmissionLineDocument(line(width, gap))), [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[.7e-3, .35e-3],
    max_evaluations=64)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
for refinement in goal.refinements:
    assert np.all(abs(np.array(refinement.evaluation.impedances)-goal.targets) <= goal.tolerances)
assert 4 < len(goal.history) <= 64
assert len(goal.to_dict()['current_solver']['samples']) == 13
```

유한 패널·메시 비교 통과가 외곽 충분성·절대 정확도·유일해·전역 최적점을 보증하지 않습니다. 하부 접지·열린 외벽의 볼록 도체 범위를 유지합니다. 선택 기하의 유한 외곽 검사는 별도이며 작은 상호 손실 항은 자체 해상도 평가가 필요합니다.

[English](../../../../../packages/sipi/shape_panel_pair_goal.md)
