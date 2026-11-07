# 신호 도체의 면별 표면 손실

[English](../../../../../packages/sipi/face_conductor.md)

`sipi.face_conductor`는 유한 두께의 직사각형·사다리꼴 신호 `Trace`의
bottom/top/left/right에 각각 기존 `SurfaceMetal` 법칙을 적용합니다.
접지면과 명시적인 ground trace는 여전히 하나의 공통 금속을 사용합니다.
한 번의 진공 PEC 전류 풀이를 적분하고 각 면의 기여를 남깁니다.
고주파 표면 섭동 모델이며 벌크 도금·금속 내부 확산 모델은 아닙니다.

```python
import numpy as np
from sipi import microstrip
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, surface_conductor_loss_by_face

section = microstrip(width=.5e-3, substrate_height=.5e-3, thickness=35e-6,
                     eps_r=4., air_height=1e-3, box_width=4e-3)
smooth = SurfaceMetal(58e6)
faces = TraceFaceMetals(bottom=SurfaceMetal(58e6, roughness_rms=.5e-6),
                       top=smooth, left=smooth, right=smooth)
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={"signal": faces}, reference=smooth, ground_thickness=35e-6,
    edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert result.boundary_labels == ("signal:signal:bottom", "signal:signal:top",
    "signal:signal:left", "signal:signal:right", "reference")
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

면 이름은 단면의 전역 좌표입니다. bottom/top은 수평이고 left/right는
`top_width`가 다른 사다리꼴의 기울어진 옆면을 따릅니다.
`TraceFaceMetals.uniform(metal)`은 네 면에 같은 법칙을 지정합니다.
mapping은 모든 신호 이름과 네 면을 빠짐없이 지정해야 합니다.
임의 polygon 신호와 두께 0 도체는 거부하며 이 API는 reference 면을 나누지 않습니다.

## 물리 계약·진단

각 면에는 [기존 표면 금속 법칙](boundary_conductor.md)의 전도도·상대 투자율과
smooth/Hammerstad RMS/Groiss RMS/causal Huray/Cannonball Huray를 적용합니다.
이는 명시한 모델 입력이며 Ra/Rq/Rz 변환이나 실제 동박과의 동등성을 추정하지 않습니다.
면마다 다른 금속을 지정했다고 실현 가능한 벌크 재료 적층이 검증되는 것은 아닙니다.
국소 표면 임피던스 근사를 지정하는 계약입니다.

메시를 만들기 전에 각 면의 skin depth가 해당 도체의 최소 두께/면 폭의 1/5 이하인지
검사합니다. reference는 입력 ground thickness·계산영역 폭·모든 ground trace의
최소 치수를 사용합니다. 양의 주파수와 기존 good-conductor 검사도 유지합니다.
이 필요조건만으로 곡률·거칠기 크기·모델 정확도가 보장되지는 않습니다.

단위 신호 전류 Ki에 대해 면별 `Q_face[i,j] = integral(Ki*Kj ds)`를 1/m로 계산합니다.
각 신호 금속 edge의 두 끝점을 메시 경계 허용오차로 검사하여 네 면 중 정확히
하나에 배정하고 모든 면이 비어 있지 않은지 확인합니다. 모호하거나 빠진 분할은
거부합니다. 면별 전류곱과 적분 전류의 합은 원래 도체 전체 값과 일치해야 합니다.
진공 풀이 한 번으로 기존 C0·외부 L·도체 전체 전류 flux 검사를 보존합니다.
flux 불일치 5% 초과는 거부합니다. 이는 전류 gradient 진단이며 저항 정확도 5% 보장이 아닙니다.

주파수 f에서 `R = sum(Re(Zs_face)*Q_face)`는 ohm/m,
내부 `L = sum(Im(Zs_face)*Q_face)/(2*pi*f)`는 H/m입니다.
표면 손실에 의한 전류 재분포를 새로 풀지는 않습니다. 공통 reference 항을 포함하며
R·내부 L의 상호 성분을 보존하므로 서로 독립인 스칼라 전선 손실로 바꾸지 않습니다.

신호 N개에는 면/reference 항 P=4N+1개가 있습니다. frequency·R·내부 L shape은
(F,)·(F,N,N)·(F,N,N)이고, skin_depth·roughness_factor·복소 surface_impedance는
(F,P)입니다. factors.parts는 (P,N,N), factors.current_integrals는 (P,N),
resistance_parts는 (F,P,N,N)입니다. 저장 배열은 읽기 전용 snapshot입니다.
factors.base는 분할 전 도체별 적분을, C0·L_external·names·current_error는 같은
진공 모델을 보존합니다. 호출자가 직접 만든 dataclass는 실제 추출/기하 유효성의 증거가 아닙니다.

`result.network(C=..., G=..., length=..., z_ref=...)`는 같은 기하의 유전체 행렬과
외부+내부 L을 기존 RLGC solver로 결합합니다. 기하·도체 순서·주파수 일치는 호출자 책임입니다.
[저장 선로 버전4](face_line.md)는 이 배정을 기록하고 유전체 추출과 하나의 메시·C0를 공유합니다.
기존 도체별 저장 계약은 유지합니다.

## 검증·한계

독립 scikit-fem 진공 gradient·면별 전력 적분과 `1e-10`, 모든 기존 거칠기 계열에서
동일 면 법칙과 도체 전체 모델의 일치를 `1e-12`로 검사합니다.
넓은 중앙 stripline은 Qbottom=Qtop≈1/(4w), Qreference≈1/(2w) 해석값과
서로 다른 면 저항률의 R/내부 L을 5% 기준으로 확인합니다. 사다리꼴 결합 사례의
mesh/계산영역 R 변화는 별도로 5% 이하를 요구하며 분할 합·상호성/PSD·수동 network를
검사합니다. 한 면의 거칠기 변경도 보존된 해당 면의 전력 기여와 비교합니다.
입력 mapping·미지원 기하·skin-depth·전류 flux 오류는 거부합니다.

명시한 모델·기하의 검증이며 모든 입력의 정확도 상한, reference 면별 동박,
실측 거칠기·금속 내부 확산·앱 연결·새 플랫폼 수락을 주장하지 않습니다.
사용할 실제 기하·주파수에서 메시와 외곽 영역을 각각 세분해 확인해야 합니다.
