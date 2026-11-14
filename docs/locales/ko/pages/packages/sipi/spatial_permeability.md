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

## volume-line v4의 이름별 자기 재료 저장

`VolumeLineDocument`의 `relative_permeability`에 매핑을 전달하면
`sipi.volume-line/4`를 선택합니다. 객체에는 정확히 다음 네 필드가 필요합니다.

- `signals`: 각 신호 이름에 대한 양의 실수.
- `ground`: 모든 생성 plate와 명시적 접지 trace의 공통 값.
- `nonmetal`: 모든 비전도 삼각형의 공통 값.
- `cores`: 명시적 코어 이름별 값. 해당 금속의 기본값보다 우선합니다.

기본 전도도도 이름별 `signals`·`ground` 객체여야 합니다. `metal_cores`는 v3의
좌표·전도도 계약으로 저장합니다. v4는 빈 코어 매핑도 허용하며 JSON에 명시적으로
남깁니다. `signals` 안의 `ground`·`nonmetal` 같은 이름도 일반 신호 이름입니다.
삼각형 번호를 저장하지 않고 새 메시마다 이름으로 재료를 배정합니다.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.volume_line import VolumeLineDocument
from sipi.execution import normalize_saved, execute_saved

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., box_width=.002, air_height=.5e-3)
doc = VolumeLineDocument(
    CrossSectionDocument(section), [0, 1e3, 1e4], materials={}, length=.1,
    conductivity=dict(signals={'signal': 20e6}, ground=58e6),
    relative_permeability=dict(signals={'signal': 5.}, ground=3., nonmetal=1.,
                               cores={'signal': 2.}),
    metal_cores={'signal': dict(conductivity=58e6, vertices=[
        [-.18e-3, .52e-3], [.18e-3, .52e-3],
        [.18e-3, .58e-3], [-.18e-3, .58e-3]])},
    mesh=dict(ground_thickness=.1e-3, padding=.002, metal_size=25e-6,
              far_size=.25e-3, grade=.1, min_angle=28.),
)
text = doc.dumps()
assert doc.to_dict()['schema'] == 'sipi.volume-line/4'
assert normalize_saved(text) == text
assert execute_saved(text)['status'] == 'complete'
```

빠지거나 추가된 이름·필드, 배열 값, 잘못된 계수, 맞지 않는 스키마 버전은
메시 생성 전에 거부합니다. 스칼라 투자율은 기존 버전을 계속 선택하며 그
버전들은 이 객체를 묵시적으로 허용하지 않습니다. v4는 이름 없는 재료를
추정하거나 스칼라 전도도를 자동 변환하지 않습니다. 공통 실행기와 회로의
`kind='volume-line'` 입력이 같은 문서를 재생합니다. 표피 깊이 해상도 부족은
계속 오류입니다. 저장/직접 R/L/C/G/S/J, 재메시 재료 배정, DC 면적 저항, 회로
응답 및 균일 v2와 정규화 1e-13 일치를 검사합니다. 위 해석식·독립 전계 기준도
그대로 유지합니다.

이 저장 형식의 비금속 투자율은 한 값입니다. 서로 다른 여러 자기 유전체
영역은 정합 메시의 직접 요소장 입력을 사용해야 합니다. 분산·비선형·손실
자기 모델을 추가하는 형식은 아닙니다.
