# 2D 전류 확산의 영역별 선형 투자율

`conductor_impedance(..., relative_permeability=mu_r)`는 기존 양의 스칼라 또는
메시 삼각형마다 양의 유한 실수 하나를 갖는 배열을 받습니다. 배열은 **비전도
공간을 포함한 모든 삼각형**을 덮습니다. 전도도와 투자율은 독립 입력입니다.
재료는 선형·등방성·주파수 불변이며 자기 손실은 없습니다. 전도도에 의한 Joule
손실은 계산합니다. 음수·0·복소수·불리언·비유한 값이나 잘못된 배열 모양은
전계 조립 전에 거부합니다.

메시는 재료 계면에 정합해야 합니다. `mu = mu_0*mu_r`를 사용하여
`K = integral (1/mu) grad(Az) dot grad(test)`를 조립하고 같은 강성행렬로 자기
에너지를 계산합니다. 약형이 재료 경계의 자속 연속을 처리하며 인위적인 포트나
전류 제약을 추가하지 않습니다. 신호와 공통 귀환의 지정 순전류는 유지합니다.
전체 인덕턴스에는 금속 내부와 외부 자기 에너지가 모두 포함됩니다.

```python
import numpy as np
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., box_width=.002, air_height=.5e-3)
volume = mesh_conductor_section(
    section, ground_thickness=.1e-3, padding=.002,
    metal_size=25e-6, far_size=.25e-3, grade=.1,
    metal_cores={'signal': [(-.18e-3, .52e-3), (.18e-3, .52e-3),
                            (.18e-3, .58e-3), (-.18e-3, .58e-3)]},
)
sigma = np.zeros(volume.mesh.num_triangles)
sigma[volume.signals['signal']] = 20e6
sigma[volume.core_triangles['signal']] = 58e6
sigma[volume.ground] = 58e6
mu_r = np.ones(volume.mesh.num_triangles)
mu_r[volume.signals['signal']] = 5.
mu_r[volume.core_triangles['signal']] = 2.
result = volume.impedance([0, 1e3, 1e4], conductivity=sigma,
                          relative_permeability=mu_r)
assert max(result.magnetic_energy_error) < 1e-9
```

예제의 계수는 명시적으로 지정한 예시이며 실측으로 보정한 재료 법칙이
아닙니다. 히스테리시스·포화·주파수 의존성·복소 투자율·텐서 투자율을 가진
자성 도금층은 이 모델의 범위 밖입니다. 상수를 배정하는 것만으로 실제 도금층의
물리 정확성이 검증되지는 않습니다.

양의 주파수에서 표피 깊이 기준은 금속 삼각형 **같은 위치의** `mu[t]*sigma[t]`를
사용합니다. `skin_depth`는 금속 내 최솟값이고 `max_edge_over_skin_depth`는
각 요소의 국소 비율 중 최댓값입니다. 독립적인 전역 최댓값끼리 곱하면 재료가
반상관된 유효 사례를 잘못 거부할 수 있습니다. 비금속 투자율은 장을 바꾸지만
금속 표피 기준에는 들어가지 않습니다. DC 저항은 전도도·면적으로 결정됩니다.
같은 정합 체적 메시의 C/G는 투자율에 따라 변하지 않습니다. 전류·전력·자기
에너지 보존과 별도로 메시 및 외곽 수렴 검사가 필요합니다.

`VolumeLineDocument` v1/v2/v3는 계속 스칼라 투자율만 받습니다. 메시 인덱스
배열은 직접 API 입력이며 이식 가능한 재료 저장 형식이 아닙니다.

## 검증

`test_spatial_permeability.py`는 동축 중심/귀환의 상대투자율 2/5, 전도도
58/20 MS/m, 간극 상대투자율 3을 독립 원통 Bessel 해와 100 Hz·10 kHz·100 kHz에서
비교합니다. 반지름은 .5/1.5/2 mm, 원주 256분할, 반경 16/32/64분할입니다.
R/L/Z 오차는 감소하고 마지막에 1% 미만이어야 하며, 해석적 DC 자기 에너지는
.1% 이내여야 합니다. 자기 외곽을 3→6 mm로 키울 때 장이 가두어진 이 기하의
Z 변화는 1e-9 미만이어야 합니다. 이 기준은 해당 사례에 한정하며 임의 자성
재료나 경계의 정확도를 주장하지 않습니다.

독립 scikit-fem 증대 연립방정식과 같은 메시의 Z/Az/Jz를 정규화 1e-9로
비교합니다. 균일 스칼라/배열 1e-13 비교, 국소 표피 기준, DC 에너지 단조성,
C/G 불변, 수동 네트워크 및 잘못된 계수도 검사합니다. 기존 스칼라 경로의
연산과 수치 기준은 보존합니다.

[English](../../../../packages/sipi/spatial_permeability.md)
