# 신호선과 기준 도체별 금속·거칠기

[English](../../../../../packages/sipi/boundary_conductor.md)

`sipi.boundary_conductor.surface_conductor_loss_by_boundary`는 PEC 진공 전류장을
한 번 풀고 각 신호선에 별도 `SurfaceMetal`을 적용합니다. 추가 금속 하나가
**모든 기준 도체 표면을 함께** 담당합니다. 기존 1차 표면 임피던스 섭동에 경계별
재료를 적용하는 기능이며, 유한 금속 내부 확산이나 동박 면별 모델은 아닙니다.

```python
import numpy as np
from sipi import microstrip
from sipi.boundary_conductor import SurfaceMetal, surface_conductor_loss_by_boundary
from sipi.roughness import CausalHuray

section = microstrip(width=.5e-3, substrate_height=1e-3,
                     thickness=35e-6, eps_r=4.)
name = next(t.name for t in section.traces if not t.ground)
loss = surface_conductor_loss_by_boundary(section, [1e9, 4e9],
    conductors={name: SurfaceMetal(58e6, roughness=CausalHuray([.2e-6], [2.]))},
    reference=SurfaceMetal(45e6, roughness_rms=.5e-6), ground_thickness=35e-6,
    edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert loss.skin_depth.shape == (2, 2)
assert loss.boundary_labels == ("signal:"+name, "reference")
np.testing.assert_allclose(loss.resistance_parts.sum(axis=1), loss.R, rtol=1e-12)
```

## 입력과 수치적 의미

불변 객체 `SurfaceMetal(conductivity, relative_permeability=1, roughness_rms=0,
roughness=None)`를 사용합니다. 도전율은 양의 S/m, 상대 투자율은 양수입니다.
미터 단위 RMS 거칠기는 기존 Hammerstad 저항 보정만 선택합니다. 또는
`roughness_rms=0`으로 두고 `CausalHuray`, `CannonballHuray`, `GroissRMS` 중
하나를 지정합니다. 기존 매개변수 정의와 한계를 유지합니다. Groiss는 비인과적이고
Cannonball은 명시적인 10점 Rz를 요구합니다. 자동 환산이나 동박 피팅을 하지
않습니다. [거칠기 계약](roughness.md)을 참조하십시오.

`conductors`에는 접지가 아닌 모든 trace 이름과 금속을 정확히 대응시킵니다.
사전 삽입 순서와 관계없이 단면의 신호 순서를 사용합니다. `reference`는 명시적
접지 trace와 단면의 모든 접지 경계를 포함합니다. 위·아래·측면에 서로 다른
거칠기를 지정하는 기능은 아닙니다.

각 금속은 별도로 양의 주파수와 `sigma/(omega*eps0) >= 1000`을 만족해야 합니다.
메시 생성 전에 각 신호의 표피깊이가 해당 trace 최소 치수의 1/5 이하여야 합니다.
기준 도체는 입력한 실제 `ground_thickness`, 단면 폭, 명시적 접지 trace의 최소
치수 중 최솟값을 사용합니다. 신호 치수에도 단면 폭 제한을 적용합니다. 얇거나
두께가 0인 도체는 거부합니다. 신호선의 높은 도전율로 기준 도체의 잘못된
표피깊이를 숨길 수 없습니다. 이 조건은 필요조건이며 모든 곡률·거칠기·섭동
오차를 제한하지는 않습니다.

경계 b의 기존 단위 전류장으로 실수 행렬 `Q_b=integral(K_i K_j ds)`(1/m)를
계산합니다. `R=sum_b Re(Zs_b) Q_b`(Ω/m),
`L_internal=sum_b Im(Zs_b) Q_b/omega`(H/m)입니다. 공통 귀환과 상호 손실을
포함하며 하나의 평균 거칠기 계수로 대체하지 않습니다. 적분 전류 불일치가
5%를 넘으면 거부합니다. 손실의 수렴은 별도로 확인해야 합니다.

## 결과와 검증 범위

`BoundaryConductorLoss`는 읽기 전용 주파수·R·내부 L·복소
`surface_impedance`·표피깊이·저항 거칠기 계수·원래 `SurfaceCurrentFactors`를
보존합니다. 금속 배열의 모양은 `(주파수, 신호 수+1)`이며 마지막이 기준
도체입니다. `metals`는 같은 순서의 불변 입력 기록입니다. `boundary_labels`는
`signal:<이름>`, 마지막 `reference`입니다. `resistance_parts`는
`(주파수, 경계, 신호, 신호)`이고 경계 축 합은 R입니다. 일반적으로 행렬 전체에
해당하는 단일 거칠기 배율은 없습니다.

`loss.network(C=..., G=..., length=..., z_ref=...)`는 R/내부 L을 같은 진공장의
외부 L과 합칩니다. C/G는 **같은 기하**에 해당해야 합니다. 별도 입력 행렬이
실제로 메시와 일치하는지 자동 추론하지 않습니다. 외부는 비자성이며 도체별
투자율은 금속 반공간 법칙에만 작용합니다. 결과 객체 자체는 정확도 인증이 아닙니다.

서로 다른 금속의 평행판을 정확한 전류 및 독립 scikit-rf 표면 법칙과 `1e-10`에
대조합니다. 동축선은 경계별 전류 계수와 합성 임피던스가 세분에 따라 개선되어
최종 2% 이내여야 합니다. 같은 금속으로 지정하면 지원되는 모든 거칠기 법칙에서
기존 공통 금속 API와 `1e-12` 이내로 일치해야 합니다. 결합 PCB 사례는 서로 다른
대각 손실·상호/귀환 항·PSD·상호성/수동성, 메시 세분과 횡방향 박스 폭 2배 변경을
5% 기준으로 검사합니다. 이는 제한된 수렴 시험이며 보편적인 손실 오차 한계나
모든 외곽 방향의 수렴을 뜻하지 않습니다. 경험적 동박 정확도·실제 거친 기하·
도체 면별 지정·Gradient 모델은 범위 밖입니다. 앱 연결은 엔진 API와 별도입니다.

## 같은 메시를 쓰는 저장 선로

`TransmissionLineDocument`의 `sipi.transmission-line/3`은
`conductor.kind="surface-boundaries"`를 추가합니다. conductor 필드는 정확히
`kind`, `conductors`, `reference`, `ground_thickness`입니다. 이름으로 지정한
각 신호와 기준 금속은 정확히 `conductivity`, `relative_permeability`, 명시적인
`roughness` 객체를 요구합니다. 거칠기는 smooth, Hammerstad, Groiss,
causal-Huray, Cannonball-Huray 중 하나입니다. 기본 금속이나 누락된 신호를 추정하지 않습니다.

```python
from sipi import CrossSectionDocument
from sipi.line_model import TransmissionLineDocument
from sipi.execution import execute_saved

geometry = CrossSectionDocument(section,
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
model = TransmissionLineDocument(geometry, [1e9, 4e9], materials={}, length=.03,
    schema="sipi.transmission-line/3",
    conductor=dict(kind="surface-boundaries", ground_thickness=35e-6,
        conductors={name: dict(conductivity=58e6, relative_permeability=1.,
            roughness=dict(kind="causal-huray", radii_m=[.2e-6], surface_ratios=[2.]))},
        reference=dict(conductivity=45e6, relative_permeability=1.,
            roughness=dict(kind="hammerstad", rms_m=.5e-6))))
saved = model.dumps()
report = execute_saved(saved)
parts = report["result"]["conductor_boundaries"]
assert parts["labels"] == ["signal:"+name, "reference"]
np.testing.assert_allclose(np.array(parts["resistance_ohm_per_m"]).sum(axis=1),
                           report["result"]["R_ohm_per_m"], rtol=1e-12)
```

정규화에서 요청한 모든 금속과 주파수의 조건을 메시 생성 전에 검사합니다.
해석은 메시 하나와 같은 진공 C0/전류 계수를 유전체·도체 계산에 공유합니다.
R/L/G/C와 S의 단위 및 포트 순서는 그대로입니다. 기존 network/circuit의
`kind="transmission-line"` 입력 안에 이 문서를 넣을 수 있습니다. 버전 1·2의
계약과 생성자 기본 버전 1은 유지합니다. 버전 3도 perfect 금속과 버전 2의
공통 surface 기록을 허용합니다.

공통 실행은 도체별 모델에만 `conductor_boundaries`를 추가합니다. 경계 이름,
`skin_depth_m`, `roughness_factor`, 복소 `surface_impedance_ohms`,
`resistance_ohm_per_m` 기여를 보존합니다. 각 금속 기록은 정규 입력에도 남습니다.
저장 재생을 별도 도체/유전체 API와 RLGC 상대 `1e-10`, S 절대 `1e-10`에 대조하고,
메시 한 번 사용 및 종단 회로 재생을 검사합니다. 이 조합으로 물리적 유효범위를
확대하거나 앱의 고정 엔진을 변경하지 않습니다.
