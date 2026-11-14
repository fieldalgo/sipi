# 2D 금속의 명시적 코어·도금 계면

`mesh_conductor_section(..., metal_cores={name: vertices})`는 기존 유한 두께
trace 안에 재료 계면을 넣습니다. trace는 **완성된 도체의 외곽**이며, 엄격히
내부에 놓인 단순 다각형 `vertices`가 코어를 정의합니다. 나머지 금속은 도금층입니다.
두께나 모서리 offset을 추정하지 않고 도체를 확장하거나 도금 공정을 해석하지
않습니다. 직사각형·사다리꼴·다각형 trace와 명시적 접지 trace에 코어를 둘 수
있으며 자동 생성된 귀환 판은 균일하게 유지합니다.

계면은 외곽과 닿거나 밖으로 나가면 안 됩니다. 좌표는 단면과 같은 m 좌표계이고
마지막 점에 첫 점을 반복하지 않습니다. 기존 trace 이름만 허용합니다. 잘못된
이름·다각형·비유한 값·boolean·경계 접촉은 메시 생성 전에 거부합니다. 매우 작은
형상은 공용 메셔의 해상도·크기 제한을 따릅니다.

```python
import numpy as np
from sipi import microstrip
from sipi.conductor_mesh import mesh_conductor_section

section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                     eps_r=4., tan_delta=.02, box_width=.002, air_height=.5e-3)
core = ((-.18e-3, .52e-3), (.18e-3, .52e-3),
        (.18e-3, .58e-3), (-.18e-3, .58e-3))
volume = mesh_conductor_section(
    section, metal_cores={'signal': core}, ground_thickness=.1e-3,
    padding=.002, metal_size=25e-6, far_size=.25e-3, grade=.1,
    dielectric_interfaces=True,
)
sigma = np.zeros(volume.mesh.num_triangles)
sigma[volume.signals['signal']] = 20e6   # coating conductivity, S/m
sigma[volume.core_triangles['signal']] = 58e6
sigma[volume.ground] = 58e6
result = volume.impedance([0, 1e3, 1e4, 1e5], conductivity=sigma, keep_fields=True)
assert max(result.current_error) < 1e-10
```

메시는 코어와 금속 외곽 양쪽 경계에 정합됩니다. `volume.signals[name]`은
**코어와 도금층 전체**이고, 선택적 읽기 전용 `core_triangles` 매핑은 코어의
삼각형 부분집합입니다. 전체 trace 집합에서 이를 빼면 도금층입니다. 접지 trace
코어도 공통 `ground` 전류 그룹에 포함됩니다. 계면에 별도 전압이나 포트를
만들지 않으며 같은 종방향 E 상수 아래에서 장 풀이가 전류를 재분배합니다.
기하 계면과 재료 계수는 별도 입력입니다.

유전체 추출에서는 코어와 도금층 전체를 도체로 제거합니다. 따라서 같은 메시에서
코어 전도도가 외부 전기 기하·C/G를 바꾸지 않습니다. 계면을 추가해 메시를 새로
만들면 이산화는 바뀔 수 있으므로 메시와 외곽 수렴을 따로 확인해야 합니다.
균일 투자율과 기존 good-conductor·국소 표피 깊이·전류·Joule 전력·자기에너지
기준을 모두 유지합니다. `metal_cores=None` 및 `{}`는 기존 메시 경로입니다.
기존 volume-line v1/v2 JSON은 이 내부 계면을 저장하지 않으며 이름별 도체
내부를 균일 재료로 정의합니다.

## 검증 범위

`test_metal_cores.py`는 정확한 코어·도금 면적과 계면 둘레, DC 저항
`1/sum(sigma*area)`+귀환 저항, 국소 DC 전류밀도, 사다리꼴·다각형·접지 코어,
예약 이름처럼 보이는 trace 이름, 입력 불변성과 잘못된 코어 거부를 검사합니다.
독립 scikit-fem P1 증대 계는 반환된 core 인덱스 대신 물리 좌표 마스크를 쓰며
Z/Jz/Az 정규화 차이 1e-9를 검사합니다.

예제의 .4×.1 mm 도체, 사방 20µm 도금층, 코어/도금 58/20 MS/m와 귀환
58 MS/m에서 metal 25→12.5µm 및 별도 far/grade 절반 세분 시 DC/1/10/100kHz
R 상대 변화는 8.69e-6, L은 .002308로 각각 .01 기준을 통과했습니다.
fine 메시 padding 2→4mm의 L 변화는 .01194(.02 기준), 같은 메시 독립 Z/J/A
차이는 최대 1.89e-14입니다. 이는 명시한 사례의 검증이며 임의로 얇은 도금,
비선형 자성 코팅, 온도 법칙, 3D 전이나 실측 foil 정확도 보증이 아닙니다.

[English](../../../../packages/sipi/metal_cores.md)
