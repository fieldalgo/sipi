# 명시 패널 전류를 사용하는 두 임피던스 목표

[유한 주파수 두 목표 역산](sampled_panel_pair_goal.md)은 지정한 모든 주파수에서 두 목표를 검증합니다.

[저장형 패널 역산](panel_pair_goal_document.md)은 명시 설정과 공통 실행 실패를 보존합니다.

[English](../../../../../packages/sipi/panel_pair_goal.md) · [패널 선로](panel_line.md) · [기존 선로 목표](pair_line_goal.md)

`seek_panel_forward_pair_impedances`는 `PanelTransmissionLineDocument`를 반환하는
factory의 양수 매개변수 두 개를 조절합니다. 기존 선로 역산의 계산 방법은 바꾸지 않습니다.
입력은 신호 두 개, 양수 주파수 한 개, 길이 0이어야 합니다. 탐색 도중 신호 순서와 이름,
주파수, 변당 패널 수, ground modes, 보간 차수를 고정합니다.

목표는 완전한 복소 forward 특성 임피던스로 계산한 `(Re(Zdd), Re(Zcc))`이며 단위는 Ω입니다.
Vd=V1−V2, Id=(I1−I2)/2, Vc=(V1+V2)/2, Ic=I1+I2를 사용합니다.
차동과 공통 목표는 각각 별개의 Ic=0, Id=0 입사 조건이고 비대각 결합을 보존합니다.
모드 임피던스의 크기나 유한 선로의 종단 입력 임피던스가 아닙니다.

## 탐색과 수락

범위·목표·허용치는 유한한 양수 쌍입니다. 각 범위는 엄격히 증가하며 초기값은 닫힌 범위
안에 있어야 합니다. 생략하면 중간값으로 시작합니다. 매개변수 단위는 factory가 정하며,
목표 허용치는 절대 Ω입니다. 기존 정규화 bounded least-squares의 범위 1% probe,
xtol=ftol=1e-4, gtol=1e-3을 재사용합니다.

`max_evaluations`는 4~10000 정수입니다. 캐시에 없는 factory·검증·추출·진단 시도는
실패나 optimizer probe도 포함해 셉니다. 캐시 hit는 시도를 추가하지 않고 잔차 복사본을
반환합니다. 예산은 내부 field solve·메모리·실행 시간을 제한하지 않으며 전체 결과를 캐시합니다.

선택한 물리 입력을 동결하고 다음 세 검증에 각각 한 번의 시도를 예약합니다.

| 단계 | 체적 메시 | 경계 패널 |
|---|---|---|
| `volume-refinement` | edge/far/grade를 각각 절반 | 그대로 |
| `panel-refinement` | 그대로 | 변당 패널 수 두 배 |
| `joint-refinement` | 세 설정을 각각 절반 | 변당 패널 수 두 배 |

세 검증에서 ground modes와 보간 차수는 그대로이며 factory를 다시 부르지 않습니다.
각 탐색 field solve 전에 후속 세분 입력의 정규화와 기존 패널 자원 제한을 검사합니다.
메시 생성·skin-depth 조건·field solve 성공을 미리 보장하는 검사는 아닙니다.

원입력과 세 세분 결과 모두 두 목표의 원래 절대 허용치를 만족해야 합니다. 각 세분의
원결과 대비 변화는 0.5% 이하, joint와 각 단독 세분의 차이도 0.5% 이하이어야 합니다.
초기값이 목표를 맞춰도 네 번 계산합니다. optimizer 성공 표시만으로 수락하지 않습니다.

불변 보고서는 매개변수·목표·허용치·원입력/세분 snapshot·전체 결과·완료 이력을
보존합니다. 문서 접근자는 새 문서를 반환합니다. `to_dict()`는 직렬화 가능한 보고서이며
새 저장 요청 스키마나 Python factory 직렬화 형식이 아닙니다.

`ForwardPairGoalError`는 완료 이력·실제 시도 수·단계·실패 매개변수·가능한 입력 JSON·
원인 종류와 원래 예외를 보존합니다. 세분 목표/수렴 실패에는 해당 완료 행도 남깁니다.
부분 성공 결과는 반환하지 않습니다. 입력/해상도를 수정해 다시 실행하며 예외의 이력을
수락된 설계로 해석하지 않습니다.

유일해·전역 최적해·일반적인 가능성·연속성·외곽 오차 상한·실측/full-wave 정확도는
보증하지 않습니다. 외곽 검증은 자동으로 수행하는 세 세분 검사와 별도입니다.

## 예제

수락한 점에서 시작해도 네 평가를 모두 수행합니다. 목표 밖에서 탐색하려면
`initial=[.7e-3,.35e-3]`, `max_evaluations=64`를 사용합니다. 길이는 m, 전도도는 S/m, 허용치는 Ω입니다.

```python
import numpy as np
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.panel_pair_goal import seek_panel_forward_pair_impedances
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

goal = seek_panel_forward_pair_impedances(
    lambda width, gap: PanelTransmissionLineDocument(line(width, gap)), [[.4e-3, .9e-3], [.2e-3, .6e-3]], [110., 40.],
    tolerances=[.25, .125],
    initial=[0.000603169086210573, 0.00040941866189257275],
    max_evaluations=4)
assert np.all(abs(np.array(goal.residuals)) <= goal.tolerances)
for refinement in goal.refinements:
    assert np.all(abs(np.array(refinement.evaluation.impedances)-goal.targets) <= goal.tolerances)
assert len(goal.history) == 4
```

## 검증과 한계

해를 아는 결합 모드 회로로 두 매개변수 해·무손실 한계·매개변수 단위 배율을 검증합니다.
시험 전용 scikit-rf 2.2.0으로 모드 특성 임피던스를 독립 계산합니다. 오류 시험은 각 세분과
정지점의 목표 미달을 포함해 원래 원인과 시도 수를 보존하는지 확인합니다.

예제의 비균일·비대칭 단면은 초기 (.7,.35) mm에서 (110,40) Ω을 (.25,.125) Ω 허용치로
탐색합니다. 세 가지 독립 세분을 모두 요구합니다. 선택 원입력과 각 세분의 전체 특성 행렬은
균형화한 2N 전압/전류 고유공간 기준과 1e-10 이내로 대조합니다. 추출 RLGC를 재사용하므로
독립 기하 추출 검증은 아닙니다.

별도 사전 등록한 유한 외곽 연구는 선택 매개변수와 joint 세분 설정을 유지하며 .5/1/2 GHz,
box/air 24/10·36/15·48/20 mm를 확인했습니다. 각 값은 (110,40) Ω에서 (.5,.25) Ω 이내,
상대 변화 0.5% 이내이며 각 주파수의 두 물리량 모두 연속 외곽 절대 변화가 감소했습니다.
이 유한 사례로 임의 입력의 단조 수렴·연속 주파수 대역·무한 영역 오차 상한을 보증하지
않습니다. API의 자동 외곽 검증이 아닙니다. 기존 저장 스키마와 기본 계산 방법은 그대로입니다.
