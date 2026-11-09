# 유한 주파수 두 목표의 저장 입력

[English](../../../../../packages/sipi/sampled_panel_pair_goal_document.md) ·
[직접 다주파수 API](sampled_panel_pair_goal.md) · [단일 주파수 저장 역산](panel_pair_goal_document.md)

`SampledPanelForwardPairDesignDocument`는 명시적 패널 전류 요청을
`sipi.sampled-panel-forward-pair-design/1`로 저장합니다. 기존 템플릿·재료 입력 계약과
직접 다주파수 API를 재사용하며 callback은 저장하지 않습니다.

최상위 키는 정확히 `schema`, `study`, `conductor`, `panel`, `frequency_hz`,
`targets_ohm`, `tolerances_ohm`, `initial`, `max_evaluations`입니다. 중첩 study는
study/3 또는 /4, `z_diff_forward`, corners 방식의 순서가 정해진 양의 범위 변수
2개여야 합니다. 기하·재료 leaf, 고정 피치·평면 간격의 기존 의미를 보존합니다.
여기서 corners는 탐색 범위를 정의하며 사전 공차·통계 계산을 실행하지 않습니다.

`frequency_hz`는 엄격하게 증가하는 양의 Hz 표본 2..64개입니다. 중첩 study의
`material_evaluation.frequency_hz`는 첫 표본과 정확히 같아야 합니다. 기존 study
계약을 유지하는 명시 기준점이며 자동으로 바꾸지 않습니다. 실제 후보 선로·재료는
전체 요청 주파수에서 평가하고, 표 재료 범위 이탈은 장 계산 전에 거부합니다.

목표와 허용치는 각각 `differential_forward_impedance_real`,
`common_forward_impedance_real` 두 이름만 가집니다. 각 값은 주파수마다 하나씩
있는 양의 유한 ohm 배열입니다. 스칼라 자동 확장이나 사전의 키 순서에 의존하는
해석은 없습니다. `initial`은 중앙값을 뜻하는 null 또는 변수 순서의 두 값입니다.
예산은 4..10000 정수입니다. panel에는 `panels_per_edge`, `ground_modes`,
`interpolation_degree`만 있으며 기존 기능·자원 제한은 유지합니다.

정규화는 명목, 초기점 또는 중앙값, 네 꼭짓점의 전체 주파수 선로와 체적·패널·동시
세분 입력을 메시나 장 계산 없이 검사합니다. 범위 내부 전체의 유효성이나 물리적인
표피 깊이 조건을 보증하지 않습니다. 사전 검사는 시도 예산 밖에서 수행합니다.

`solve()`는 직접 API의 전체 이력·동결 선택 입력·세 가지 검증 결과를 보존합니다.
`execute_saved()`는 저장 예산이 호출자 예산을 넘으면 계산 전에 거부하며 예산을
임의로 줄이지 않습니다. 예산은 실패와 탐색점을 포함한 주파수 묶음 시도 수이며
내부 장 계산 수·시간·메모리 상한이 아닙니다. 성공하면 직접 보고서를 반환합니다.
목표 계산 실패는 `status="failed"`, `result=null`과 두 양의 이름·단위·전체 주파수,
원래 단계·원인·시도 수·실패 매개변수, 가능한 입력 및 완료 묶음을 보존합니다.
일부 주파수만 성공한 묶음을 만들지 않습니다. 잘못된 저장 입력은 계산 전에 예외를
냅니다. diagnostic 옵션은 기존처럼 최상위 선로에 한정하며 이전 저장 계약은 유지합니다.

## 재현 가능한 저장 재료 예제

목표에 맞는 균일 Debye 초기값에서 시작하여 두 지역의 `eps_inf` leaf를 각각 정의합니다.
재료 해석식은 기하의 진공 정전용량을 공유하므로 독립 기하·역산 유일성 근거가 아닙니다.
기본 계산과 세 가지 세분을 포함한 네 묶음을 모두 실행합니다.

```python
import numpy as np
from sipi import coupled_microstrip
from sipi.constants import mu_0, epsilon_0
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.panel_conductor import panel_surface_current_factors
from sipi.sampled_panel_pair_goal_document import SampledPanelForwardPairDesignDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = np.array([0.5e9, 1e9, 2e9])
parameters = dict(width=0.3e-3, gap=0.2e-3, substrate_height=0.5e-3,
    eps_r=4, thickness=35e-6, air_height=2e-3, box_width=6e-3)
material = DebyeDielectric(3.0, (0.7,), (1e9,))
study = ImpedanceStudyDocument("coupled_microstrip", parameters,
    quantity="z_diff_forward", frequency=float(frequencies[0]),
    materials=dict(substrate=material, air=material),
    mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1),
    material_variables={
        "eps_substrate": dict(region="substrate", path=["eps_inf"]),
        "eps_air": dict(region="air", path=["eps_inf"])},
    sampling=dict(kind="corners", variables=[
        dict(name="eps_substrate", lower=2.0, upper=4.0),
        dict(name="eps_air", lower=2.0, upper=4.0)]))

# Uniform material reference at an already matched initial point.
c0 = panel_surface_current_factors(coupled_microstrip(**parameters)).C0
epsilon = 3.0 + 0.7 / (1 + 1j * frequencies / 1e9)
z = np.array([np.sqrt(mu_0 * epsilon_0 / e) * np.linalg.inv(c0) for e in epsilon])
a = np.array([[1.0, -1.0], [0.5, 0.5]])
targets = np.diagonal(a @ z @ a.T, axis1=1, axis2=2).real
quantities = ("differential_forward_impedance_real", "common_forward_impedance_real")
request = SampledPanelForwardPairDesignDocument(study,
    conductor=dict(kind="perfect"), frequencies=frequencies.tolist(),
    targets=dict(zip(quantities, targets.T.tolist())),
    tolerances=dict(zip(quantities, (targets * 0.005).T.tolist())),
    initial=[3.0, 3.0], max_evaluations=4)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["evaluations"] == 4
```

## 검증과 유효 범위

독립 모드 해석식과 직접 API 대조, 엄격한 JSON·복사 격리, 전체 주파수의 표 재료
범위, 고정 피치 재료 치환, 사전·상위 예산, 모든 실패 세분 단계 및 4묶음 예산에서
9주파수의 초기 일치점을 검사합니다. 실제 저장 기하로 검증된 다주파수 선택점과
세 가지 동결 세분을 재현하며 독립 balanced 2N 특성행렬과 1e-10 이내로 일치합니다.
저장된 균일 Debye 재료는 전체 복소 해석행렬 1e-10, C/G 스케일링 1e-12, R=0을 검사합니다.

직접 API의 외곽 연구는 별도이며 정규화가 외곽 수렴을 자동 보증하지 않습니다.
연속 대역, 임의 단면, 역산 유일성, 실측 정확도나 제조 수율의 근거가 아닙니다.
전송 방식과 독립적인 저장 요청이며 브라우저·Worker·EXE 연결이나 새 플랫폼 지원을
뜻하지 않습니다.
