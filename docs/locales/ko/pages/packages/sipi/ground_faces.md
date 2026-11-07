# 접지 도체의 면별 표면 법칙

[English](../../../../../packages/sipi/ground_faces.md)

Python [기준 도체 표면 API](reference_surfaces.md)의 ground trace 매핑에 전체 둘레용
`SurfaceMetal` 또는 아래·위·왼쪽·오른쪽 면용 `TraceFaceMetals`를 넣을 수 있습니다.
두 형식을 함께 사용할 수 있습니다. 4면 지정은 유한 두께의 직사각형·사다리꼴
`Trace`에만 적용합니다. 기존 전체 둘레 `PolygonTrace` 접지는 그대로 지원하지만
임의 다각형·두께 0 접지에는 4면을 지정할 수 없습니다.

```python
import numpy as np
from sipi import coplanar_stripline
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import (TraceFaceMetals, ReferenceSurfaceMetals,
                                 surface_conductor_loss_by_face)

section = coplanar_stripline(width=.5e-3, gap=.2e-3, ground_width=.5e-3,
    plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6, eps_r=4., box_width=4e-3)
copper = SurfaceMetal(58e6)
left_ground = TraceFaceMetals(bottom=copper,
    top=SurfaceMetal(58e6, roughness_rms=.5e-6), left=copper, right=copper)
reference = ReferenceSurfaceMetals(bottom=copper, top=copper, sides=None,
    conductors={'ground_left': left_ground, 'ground_right': copper})
result = surface_conductor_loss_by_face(section, [1e9, 4e9],
    conductors={'signal': TraceFaceMetals.uniform(copper)}, reference=reference,
    ground_thickness=35e-6, edge_size=2.5e-6, far_size=.1e-3, grade=.05)
assert 'reference:ground:ground_left:top' in result.boundary_labels
assert result.boundary_labels[-1] == 'reference:ground:ground_right'
np.testing.assert_allclose(result.factors.parts[4:].sum(axis=0),
                           result.factors.base.parts[-1], rtol=1e-12, atol=1e-12)
np.testing.assert_allclose(result.resistance_parts.sum(axis=1), result.R, rtol=1e-12)
```

면 이름은 전체 단면 좌표 기준입니다. 사다리꼴의 left/right는 기울어진 면을
따릅니다. 기존 `SurfaceMetal` 법칙 4개를 모두 지정하며,
`TraceFaceMetals.uniform(metal)`은 같은 법칙을 네 면에 넣습니다. 전도도·상대
투자율·기존 거칠기 모델의 정의를 유지합니다. 거칠기 통계 환산·금속 내부 도금층·
실측 동박과의 등가성을 추정하지 않습니다.

## 할당과 전류 보존

위·아래 기준면과 측벽은 기존의 단일 법칙을 유지합니다. `conductors`는 모든
접지 도체 이름을 정확히 한 번씩 포함해야 하고, 열린 경계는 `None`, 접지 경계는
금속 법칙을 지정합니다. 매핑은 복사되어 읽기 전용이 됩니다. 모든 기준 도체는
여전히 같은 PEC 전위이며 포트를 추가하거나 부유 접지를 모델링하지 않습니다.

메시를 만들기 전 각 면의 skin depth가 **해당 도체의 최소 치수/5** 이하여야 합니다.
최소 치수에는 두께와 최소 면 폭이 들어갑니다. 얇은 도체나 낮은 전도도의 면이
다른 도체 치수를 대신 사용하지 않습니다. 양의 주파수·기존 양도체 조건과
`ground_thickness`의 양수 입력·plane/측벽 정의도 유지됩니다.

기준 그룹 순서는 bottom·top·sides, 이어서 단면의 ground trace 순서입니다.
전체 둘레는 `reference:ground:<name>`을 유지하고 4면 지정은
`reference:ground:<name>:bottom`·`:top`·`:left`·`:right`로 확장합니다.
기존 공통 reference와 전체 둘레 경로의 label·배열 shape는 바꾸지 않습니다.
확장된 이름은 서로 달라야 합니다. 예를 들어 4면 도체 `g`와 전체 둘레 도체
`g:bottom`은 이름이 충돌하므로 **메시 전** 거부합니다. 기존 도체 이름의 콜론을
일괄 금지하지는 않습니다.

면의 수와 관계없이 공유 진공 추출 한 번을 수행하며, 그 안에서 신호마다 단위
전압 해를 구합니다. 각 접지 edge의 양 끝점은 정확히 하나의 비어 있지 않은
그룹에 속해야 합니다. 면을 합친 전류 제곱 적분과 전류는 원래 도체별·전체 접지
합을 유지합니다. C0·외부 L·전체 전류 flux 오차 5% 초과 거부도 그대로입니다.
flux 검사는 전류 기울기 진단이며 저항 정확도 5% 보증이 아닙니다.

신호 N개·기준 그룹 M개에서 P=4N+M 항목으로 기존 [면별 손실 shape](face_conductor.md)를
사용합니다. Q는 Ki Kj의 N×N 적분이고 단위는 1/m입니다. 저항은
`sum(Re(Zs)*Q)`, 내부 인덕턴스는 `sum(Im(Zs)*Q)/(2*pi*f)`이며
`resistance_parts`가 각 국소 기여를 보존합니다. 상호 항·label·skin depth·복소 표면
임피던스도 확인할 수 있습니다.

## 검증과 한계

`tests/sipi/test_ground_faces.py`는 독립 scikit-fem P1 진공 해와 edge 중점 분류로
사다리꼴 접지의 면별 전류를 대조합니다. Q·적분 전류의 오차 기준은 1e−10입니다.
같은 메시에서 네 면에 같은 법칙을 주면 기존 전체 둘레의 R·내부 L·도체별 합으로
1e−12 이내 환원해야 합니다. 혼합 할당·읽기 전용 결과·메시 전 거부·상호성·
양의 준정부호 기여와 수동 네트워크도 검사합니다.

넓은 중앙 신호판과 두 유한 접지판의 금속 면 간격이 같으면 각 신호 수평면·마주
보는 접지면은 Q=1/(4W), 각 접지면 전류는 −1/2에 접근합니다. 신호의 표면 저항이
Rs이고 두 접지의 마주 보는 면이 2Rs·3Rs이면 총 저항은 7Rs/(4W)에 접근합니다.
면별 Q·가중 R은 5% 이내, 별도 메시 변화도 5% 이내를 요구합니다. 사다리꼴 접지
쌍에서는 R의 메시 세분·상자 두 배 변화 각각 5% 이내를 검사합니다. 유한 판 끝의
반대면·측면 전류는 실제 계산에 남아 있으며 평행판 식은 극한 대조에만 씁니다.

사다리꼴 접지 사례에서 최초 edge 5→2.5µm 세분의 R 변화는 6.78%로 기준을
넘었습니다. edge·far·grade를 다시 절반인 1.25µm·50µm·0.025로 줄였을 때
메시 변화 4.63%, 상자 두 배 변화 0.68%를 얻었습니다. 형상·금속·5% 기준은
유지했습니다. 전류 flux 진단 통과만으로 이 저항 수렴이 입증되지는 않습니다.

PEC 표면의 일차 섭동 모델입니다. 금속 내부 확산·도금 적층·3차원 접지 연결·
실측 제조 특성을 계산하는 것은 아닙니다. 실제 형상과 주파수에서 메시·외곽
수렴을 확인하세요.

이번 단위는 Python API 확장입니다. 기존 transmission-line/5 JSON은 접지 도체당
전체 둘레 금속 하나만 받고 4면 접지 record는 거부합니다. 기존 스키마 뜻은
바뀌지 않으며 앱·Windows 후보도 이번 API 확장으로 갱신되지 않습니다.
