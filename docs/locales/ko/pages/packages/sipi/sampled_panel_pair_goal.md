# 유한 주파수 표본의 두 임피던스 목표

[English](../../../../../packages/sipi/sampled_panel_pair_goal.md) ·
[단일 주파수 패널 역산](panel_pair_goal.md) · [패널 선로 계약](panel_line.md)

`sipi.sampled_panel_pair_goal.seek_sampled_panel_forward_pair_impedances`는
양의 범위가 정해진 두 매개변수를 조절하여 지정 주파수마다 전체 복소 특성행렬의
`Re(Zdd)`와 `Re(Zcc)`를 동시에 맞춥니다. 혼합 좌표는 기존 전력 보존 전압·전류
규약을 따르며 결합 항을 유지합니다. 기존 역산 API를 변경하지 않습니다.

엄격하게 증가하는 양의 주파수 2..64개(Hz)와 정확한 `(N, 2)` 모양의 양의 유한
목표·절대 허용치(ohm)를 받습니다. 행은 주파수 순서, 열은 차동·공통 순서입니다.
자동 확장은 없습니다. factory는 길이 0, 순서가 정해진 신호 2개, 정확한 주파수
배열을 가진 `PanelTransmissionLineDocument`를 반환해야 합니다. 탐색 중 신호 이름과
패널 설정은 고정됩니다. 패널 선로의 기하·금속·재료·표피 깊이·자원 제한도 유지합니다.

범위 내 두 변수 최소제곱 탐색은 주파수 우선 순서로 정규화한 잔차를 사용합니다.
`max_evaluations`는 4..10000의 정수이며 캐시되지 않은 주파수 묶음 시도 수입니다.
실패한 factory·추출·탐색점도 세고 검증용 3회를 예약합니다. 내부 장 계산 수나
시간·메모리 상한이 아닙니다. 묶음이 실패하면 일부 주파수만 성공한 이력을 만들지
않습니다. 캐시 잔차는 복사해서 반환합니다.

선택 입력을 동결한 뒤 factory를 다시 부르지 않고 체적 edge/far 크기·grading 절반,
도체 패널 수 두 배, 둘 다 적용한 입력을 각각 검사합니다. ground modes와 보간 차수는
고정됩니다. 탐색 계산 전에 후속 세분 입력도 모두 허용되는지 확인합니다. 기본 및 세
세분 결과의 모든 주파수·두 양이 원래 절대 허용치를 만족해야 합니다. 기본 대비 및
동시 세분과 각 단일 축 세분 사이 상대 변화도 0.005 이하여야 합니다. 최적화기의 성공
표시만으로 결과를 수락하지 않습니다. 범위 내 국소 탐색이며 전역 최적화 보장이 아닙니다.

`SampledPanelForwardPairDesign`은 주파수, 매개변수, 목표·허용치 행렬, 완료 이력,
선택 입력, 전체 물리 결과 및 세 가지 세분 결과를 보존합니다. `to_dict()`는 입력과
잔차를 JSON 호환 값으로 반환합니다. `SampledPanelForwardPairGoalError`에는 주파수,
완료 이력, 실제 시도 수, 단계, 실패 매개변수, 가능한 입력과 원인 예외가 남습니다.
잘못된 제어 입력은 factory 호출 전에 거부합니다. 이번 API는 새 저장 요청 형식이나
공통 실행 분기를 추가하지 않습니다.

## 재현 가능한 재료 예제

이미 목표를 만족하는 초기 재료를 사용합니다. 구성식은 기하의 진공 정전용량을 공유하므로
분산 재료의 스케일링과 동결 검증 근거이며, 독립 기하 정확도·매개변수 유일성 또는
잘못된 초기값에서 최적점을 찾았다는 근거가 아닙니다.

```python
import numpy as np
from sipi import coupled_microstrip, CrossSectionDocument
from sipi.constants import mu_0, epsilon_0
from sipi.dielectric import DebyeDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal import seek_sampled_panel_forward_pair_impedances

frequencies = np.array([0.5e9, 1e9, 2e9])

def factory(strength, pole_hz):
    section = coupled_microstrip(width=0.3e-3, gap=0.2e-3,
        substrate_height=0.5e-3, eps_r=4, thickness=35e-6,
        air_height=2e-3, box_width=6e-3)
    material = DebyeDielectric(3.0, (strength,), (pole_hz,))
    line = TransmissionLineDocument(
        CrossSectionDocument(section,
            mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1)),
        frequencies, materials=dict(substrate=material, air=material),
        length=0, conductor=dict(kind="perfect"),
        schema="sipi.transmission-line/6")
    return PanelTransmissionLineDocument(line)

# Uniform material invariant; the initial material already meets these targets.
c0 = panel_surface_current_factors(factory(0.7, 1e9).line.cross_section.section).C0
epsilon = 3.0 + 0.7 / (1 + 1j * frequencies / 1e9)
z = np.array([np.sqrt(mu_0 * epsilon_0 / e) * np.linalg.inv(c0) for e in epsilon])
a = np.array([[1.0, -1.0], [0.5, 0.5]])
targets = np.diagonal(a @ z @ a.T, axis1=1, axis2=2).real
goal = seek_sampled_panel_forward_pair_impedances(
    factory, [[0.5, 0.9], [0.8e9, 1.2e9]], frequencies, targets,
    tolerances=targets * 0.005, initial=[0.7, 1e9], max_evaluations=4)
report = goal.to_dict()
assert report["evaluations"] == 4
assert len(report["refinements"]) == 3
```

## 검증과 유효 범위

독립 모드 해석식·실제 scikit-rf 모드 선로, 매개변수 단위 변경, 캐시·Jacobian 순서,
실패 탐색점·묶음, 엄격한 메타데이터, 경계값·예산 및 모든 세분 수락 조건을 검사합니다.
비대칭 손실 단면은 틀린 폭·간격에서 시작하여 0.5/1/2 GHz의 110/40 ohm 목표,
절대 허용치 0.5/0.25 ohm과 세 가지 세분을 확인합니다. 독립 balanced 2N 고유공간과
1e-10 이내에서 일치합니다. 세 외곽 영역에서 같은 목표·상대 변화 0.005 이하 및
6개 양 모두의 연속 절대 변화 감소를 검사합니다. 균일 Debye 재료는 전체 복소 해석
행렬을 1e-10, C/G 구성식을 1e-12로 대조하고 도체 R이 0임을 확인합니다.
물리 단면 검사와 재료 불변식 검사는 별개입니다.

유한 주파수 검사는 그 사이 주파수, 임의 단면, 실측 정확도나 제조 수율을 보증하지
않습니다. 외곽 수렴은 별도 검증 연구이며 모든 API 요청에 자동 적용되지 않습니다.
브라우저·Worker·데스크톱 패키징, 시간 제한·취소 동작 보장은 추가하지 않습니다.
