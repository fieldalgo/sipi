# 모서리 해상도를 명시한 FEM 선로 역산

`seek_corner_fem_shape_line_quantity`는 명시적
[모서리 FEM 선로](corner_fem_line.md)를 반환하는 팩토리로 기존 유계
단일 변수 역산을 수행합니다. 팩토리는 양의 주파수 한 개, 길이 0,
단일 신호 또는 순서가 정해진 두 신호를 제공해야 합니다. 탐색 중
주파수와 신호 정체성은 바뀌지 않습니다.

```python
from sipi.templates import stripline
from sipi import (CrossSectionDocument, FEMShapeTransmissionLineDocument,
                  CornerFEMShapeTransmissionLineDocument,
                  seek_corner_fem_shape_line_quantity)

metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness=dict(kind='smooth'))

def factory(width):
    cross = CrossSectionDocument(stripline(width=width, plane_spacing=.002,
        eps_r=4., thickness=.00005, box_width=.008),
        mesh=dict(edge_size=5e-6, far_size=.0002, grade=.1))
    line = FEMShapeTransmissionLineDocument(cross, [2e9], materials={},
        conductors=dict(signal=metal), reference=metal,
        ground_thickness=35e-6, length=0.)
    return CornerFEMShapeTransmissionLineDocument(line, corner_size=2.5e-6)

assert factory(.0004).corner_size == 2.5e-6
options = dict(quantity='impedance_real', tolerance=.2, max_evaluations=12)
# result = seek_corner_fem_shape_line_quantity(
#     factory, [.00039, .00041], 70.35, **options)
```

계산량은 기존 정의를 유지합니다. 단일 선로의 `impedance_real`·
`attenuation`, 쌍 선로의 Ic=0 구동 `differential_forward_impedance_real`·
Id=0 구동 `common_forward_impedance_real`입니다. 쌍 계산량은 전체 복소
순방향 특성 행렬을 사용하며 독립 고유모드가 아닙니다.

양쪽 끝점을 모두 계산하고 기존 끝점 수락·브라켓 이분법 규칙을 따릅니다.
세분을 위해 선로 시도 한 번을 남깁니다. 선택된 기하·재료·금속 입력을
동결하고 해석된 edge·far·grade·corner를 모두 절반으로 줄이며 min_angle은
유지합니다. 세분 때 팩토리를 다시 호출하지 않습니다. 원래 값과 세분 값
모두 절대 목표 허용오차 안이어야 하며 상대 변화도 기존 0.005 이하여야
합니다. 두 값이 모두 0이면 상대 변화는 0입니다.

실패를 포함한 팩토리·검증·장 추출·진단 시도마다 예산을 사용합니다.
선로 시도 안에는 여러 장 풀이가 있으며 평가 예산이 시간·메모리 한도를
보장하지는 않습니다. 기존 전류 미분·내부 확장장·전류 보존·표피 깊이·
양의 에너지 검사를 유지합니다. 실패는 `FEMShapeLineQuantityGoalError`로
전체 모서리 입력, 완료 이력과 완료·부분 전류 관측을 보존하고 중단
신호는 전파합니다.

결과 `CornerFEMShapeLineQuantityDesign`은 선택·세분 모서리 입력과 두
전류 기록을 담습니다. 전체 입력과 정확한 계산물 근거를 보존하세요.
직접 팩토리는 직렬화하지 않으며 기존 FEM 목표 저장 스키마의 계약은
바뀌지 않습니다.

검증은 독립 특성량, 실제 단일 70.35Ω·쌍 92.8Ω 목표, 같은 값·더 작은
모서리 제어, 동결된 세분, 기존 결과 대조와 유형 있는 실패를 포함합니다.
이 유한 검사는 작은 상호 손실, 외곽 충분성, 임의 팩토리, 연속성,
유일성, 전역 최적값, 실측 정확도나 새 플랫폼을 인증하지 않습니다.

[English](../../../../../packages/sipi/corner_fem_goal.md)
