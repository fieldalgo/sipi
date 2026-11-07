# 기준면·접지 도체별 표면 법칙

[English](../../../../../packages/sipi/reference_surfaces.md) · [신호 면별 손실](face_conductor.md)

`ReferenceSurfaceMetals`는 Python 면별 손실 API에 아래·위 기준면, 측벽,
이름별 접지 도체 금속을 각각 지정합니다. 기존 단일 `SurfaceMetal` reference는
모든 접지를 합친 의미와 출력 형식을 유지합니다. 저장 line/4는 여전히 공통
reference만 받으며 이번 확장은 Python API입니다.

```python
import numpy as np
from sipi import stripline
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
                                 surface_conductor_loss_by_face)

section = stripline(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
                   eps_r=4., box_width=4e-3)
smooth = SurfaceMetal(58e6)
reference = ReferenceSurfaceMetals(bottom=smooth,
    top=SurfaceMetal(58e6, roughness_rms=.5e-6), sides=None, conductors={})
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={'signal': TraceFaceMetals.uniform(smooth)}, reference=reference,
    ground_thickness=35e-6, edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert result.boundary_labels[-2:] == ('reference:bottom', 'reference:top')
np.testing.assert_allclose(result.factors.parts[4:].sum(axis=0),
                           result.factors.base.parts[-1], rtol=1e-12, atol=1e-12)
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

생성자의 네 필드는 모두 명시합니다. 단면의 `bottom`, `top`, `sides`가 ground일
때만 `SurfaceMetal`을 지정하고 열린 경계에는 `None`을 넣습니다. 양 측벽은 하나의
`sides` 법칙을 공유합니다. `conductors`에는 모든 명시적 ground trace의 이름을
정확히 넣고 각 도체 둘레 전체에 하나의 법칙을 적용합니다. 신호 도체에는 별도의
`TraceFaceMetals`를 사용합니다. 누락·알 수 없는 이름·사용하지 않는 경계 지정은
메시 전에 거부합니다. ground mapping은 복사 후 읽기 전용으로 만들어 호출자가
원래 mapping을 수정해도 배정이 바뀌지 않습니다.
필드 모델의 모든 ground 그룹은 같은 PEC 기준 전위를 유지합니다. 표면 법칙을
분리해도 독립된 귀환 도체 포트가 추가되는 것은 아닙니다.

신호 면의 표피 깊이는 기존 최소 치수 규칙을 따릅니다. 활성 plane/측벽은
`ground_thickness`, 영역 폭·높이 중 최솟값을 사용하고 각 명시적 ground trace는
자신의 최소 치수를 사용합니다. 모든 표피 깊이는 메시 생성 전에 해당 치수/5
이하여야 합니다. trace만 접지인 단면에서도 `ground_thickness`는 양수여야 하지만
이 값이 trace의 최소 치수에 들어가지는 않습니다. 이는 필요조건이며 정확도 보장은 아닙니다.

한 번의 진공 전류 해를 신호별 네 면, 활성 bottom·top·sides, 단면 순서의
ground trace로 나눕니다. reference label은 `reference:bottom`, `reference:top`,
`reference:sides`, `reference:ground:<name>`입니다. 모든 접지 경계 edge는
정확히 하나의 비어 있지 않은 그룹에 속해야 합니다. plane/측벽 양 끝점에는 단면
경계 tolerance를, ground trace 양 끝점에는 그 기하를 사용합니다. 중복·누락은 거부합니다.

신호 N개와 reference 그룹 M개에서 P=4N+M 항목입니다. 기존 면별 손실 배열은
4N+1 대신 P를 사용하고 `factors.reference_labels`가 M개 label을 보존합니다.
공통 reference는 M=1, label `reference`를 유지합니다. reference의 Q와 적분
전류 합은 원래 ground 전체와 1e−12 이내로 일치해야 합니다. C0·외부 L과
도체 전체 전류 flux 5% 초과 거부는 그대로입니다. 각 국소 표면 임피던스와 Q의
곱을 합쳐 저항·내부 L을 만들며 상호 항과 표면별 기여도 보존합니다.

독립 scikit-fem 12.0.2 검증은 두 기준면·측벽·두 ground trace가 있는 신호 쌍의
필드를 별도로 조립하고 edge 중간점으로 reference 전류를 분류합니다. Q와 적분
전류는 1e−10 이내로 일치합니다. 모든 법칙이 같으면 공통 reference 결과와
1e−12 이내로 일치합니다. PSD·상호성·수동 network·각 reference 종류만의 접지,
메시 전 엄격한 거부와 분할 합도 검사합니다.

넓은 중앙 stripline의 신호 수평면과 각 기준면에는 Q≈1/(4w)가 적용됩니다.
서로 다른 기준면 저항률의 해석적 전력 합을 5% 이내로 검증합니다. 별도의 편심
stripline에서는 메시 세분과 두 배 영역의 저항 변화가 각각 5% 이내여야 합니다.
이는 특정 검증 사례의 기준이며 임의 단면의 보편적 정확도 상한이 아닙니다.

모델은 PEC 표면의 일차 섭동입니다. 서로 다른 법칙 지정이 실현 가능한 도금 적층,
금속 내부 전류 재분포나 동박 실측 보정을 뜻하지 않습니다. ground trace의 면은
분리하지 않고 도체마다 하나의 법칙을 적용합니다. 실제 기하·주파수에서 메시와
외곽 수렴을 각각 확인해야 합니다. 앱 pin이나 플랫폼 수락 범위는 확대하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_reference_surfaces.py tests/sipi/test_face_conductor.py tests/sipi/test_face_line.py
```
