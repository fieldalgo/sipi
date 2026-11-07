# 유손실 차동 순방향 임피던스 목표

[저장 /2](differential_goal_document.md)는 이 API를 JSON 요청으로 연결합니다.

[English](../../../../../packages/sipi/differential_line_goal.md) · [목표 API](line_goal.md) · [순방향 행렬](characteristic.md)

`differential_forward_impedance_real`은 순서가 있는 두 신호와 고정된 양수 주파수
하나에서 Re(Zdd)[ohm]를 목표로 합니다. 비대칭 기하·유전체·금속 법칙을 포함한
전체 유손실 순방향 특성 행렬을 사용합니다. u=[1,-1]이면 Zdd=u Zc u^T입니다.
좌표는 Vd=V1−V2, Vc=(V1+V2)/2, Id=(I1−I2)/2, Ic=I1+I2입니다.
입력 단면에서 Ic=0이므로 Vd=Zdd Id, Vc=Zcd Id가 됩니다. 일반적으로 공통
전압은 0이 아닙니다.

명시한 순방향 전류 입력 조건이며 독립 차동 고유모드, 유한 선로 종단 입력
임피던스 또는 전파 중 Ic=0 유지를 뜻하지 않습니다. 절댓값을 취하거나 교환
대칭으로 투영하지 않습니다. 실수부 목표는 허수부를 제한하지 않으므로 보존된
복소 행렬과 결합도 확인하세요. 기존 상호성·수동성·조건수 검사를 유지하며
진단 실패를 유효한 후보로 다루지 않습니다.

다음 예제는 중심 피치 0.95mm를 유지하며 첫 번째 폭을 바꿉니다. 두 신호의
두께·전도도·거칠기는 서로 다릅니다.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.line_goal import seek_line_quantity

def pair(width):
    section = asymmetric_coupled_microstrip(left_width=width, right_width=.5e-3,
        gap=.95e-3-(width+.5e-3)/2, substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6, air_height=5e-3, box_width=12e-3)
    def metal(sigma, rms):
        return dict(conductivity=sigma, relative_permeability=1.,
                    roughness=dict(kind='hammerstad', rms_m=rms))
    cross = CrossSectionDocument(section,
        mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075))
    return TransmissionLineDocument(cross, [1e9], materials={}, length=0.,
        schema='sipi.transmission-line/3', conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6))

goal = seek_line_quantity(pair, [.2e-3, 1e-3], 100.,
    quantity='differential_forward_impedance_real', tolerance=.5, max_evaluations=24)
assert max(abs(goal.residual), abs(goal.refined_residual)) <= .5
mixed = goal.result.characteristic().mixed_mode()
assert goal.value == mixed.z_characteristic[0, 0, 0].real
assert abs(mixed.z_characteristic[0, 1, 0]) > 1
selected_input = goal.document.dumps()
```

신호 순서와 주파수가 고정되고 길이는 0입니다. 양수 bounds, 실패를 포함한
시도 예산, 전체 입력 이력과 고정 입력 세분은 [단일 선로 목표](line_goal.md)와
같습니다. 원래 메시와 제어값을 절반으로 줄인 메시가 모두 목표 허용오차를
만족해야 합니다. 이분법은 유한 구간 탐색이며 전역 최적·단조성·연속성 증명이
아닙니다. 외곽 수렴은 별도 확인합니다. 선택 `TransmissionLineDocument`는
저장할 수 있지만 factory 자체는 직렬화하지 않습니다. 저장 스키마
`line-quantity-design/1`과 `line-quantity-study/1`은 단일 신호 전용을 유지하며
이 차동 물리량을 거부합니다.

비대칭 100Ω 사례는 원래·세분·box와 air 확장의 잔차 0.5Ω 이하, 외곽 변화
0.5% 미만, 재생 RLGC/Zc 일치 1e−10을 요구합니다. 알려진 비직교 변환을 사용한
독립 scikit-rf 단일 모드들과 별도 2N 전신방정식 순방향 고유공간은 각각
Zc/Zdd 상대 일치 1e−10을 요구합니다. 후자는 균형화한 전압·전류 블록 행렬의
양수 위상 근을 사용하며 제품의 Schur 제곱근 구현과 구분됩니다. 대칭 모드와
무손실 비대칭 순방향 한계도 1e−10으로 검사합니다. 이 대수·수치 검증은 새로운
실측 기하 정확도·full-wave 유효성·앱·Windows 수락을 뜻하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_differential_line_goal.py tests/sipi/test_line_goal.py tests/sipi/test_line_goal_document.py tests/sipi/test_line_study.py tests/sipi/test_characteristic_matrix.py tests/sipi/test_mixed_characteristic.py
```
