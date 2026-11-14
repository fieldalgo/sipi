# 접지 패턴과 바닥 접지판의 표면 금속 분리

`panel_shape_conductor_loss_with_reference_metals`는 각 신호 전체 둘레,
바닥 접지판, 이름별 접지 패턴에 서로 다른 표면 재료를 적용합니다.
[정전용량 형상 미분 전류](panel_shape_conductor.md)의 접지 합산 전 행렬을
재사용합니다. 전계 솔버나 기본 방식은 바뀌지 않으며 기존 공통 접지 금속
API와 출력도 그대로입니다.

`conductors`는 모든 신호 이름에 `SurfaceMetal` 또는 `LayeredSurfaceMetal`을
정확히 대응시킵니다. `reference`는 명시적 `ReferenceSurfaceMetals`여야 합니다.
`bottom`에는 금속, `top`·`sides`에는 None을 넣고 `conductors`에는 모든
접지 패턴 이름과 전체 둘레 금속을 지정합니다. 이 API는 `TraceFaceMetals`를
거부합니다. 바닥 접지·위/옆 열린 경계, 볼록한 유한 두께 도체와 기존 패널·
형상 이동폭 한도를 유지합니다.

표피 깊이는 각 경계의 재료와 남은 치수로 검사합니다. 바닥은 명시적
`ground_thickness`, 접지 패턴은 각자의 유한 단면 치수를 사용합니다.
코팅 두께는 기존 표면 모델과 같은 보수적 남은 코어 치수에 반영합니다.
모든 활성 금속에 기존 양도체 조건과 표피 깊이 <= 남은 치수 / 5를 전계
계산 전에 적용합니다. 거칠기 모델은 기존 정의를 그대로 쓰며 코팅 금속에
거칠기 보정을 암묵적으로 더하지 않습니다. 국소 평면 코팅식은 코팅 모서리나
금속 내부 전류 확산을 해석하지 않습니다.

경계 b의 형상 에너지 행렬 Qb와 복소 표면 임피던스 Zsb에 대해
Re(Zsb) Qb를 R에, Im(Zsb) Qb / omega를 내부 L에 더합니다. 접지 금속을
바꾸면 같은 PEC 진공 전류장의 손실 가중치가 달라집니다. 기존 표면 임피던스
섭동이며 유한 전도도 전계 자체를 다시 푸는 모델은 아닙니다.

`ShapeReferenceConductorLoss`는 주파수·R·내부 L·`skin_depth`·
`roughness_factor`·`surface_impedance`·`metals`·`boundary_labels`·
`boundary_parts`를 불변 배열/튜플로 보존합니다. 순서는 기하의 신호 순서,
`reference:bottom`, 기하 순서의 `reference:ground:<name>`입니다.
원 `factors`에는 합산 접지 전류·C0·모든 전류 표본과 두 이동폭 근거가 남습니다.
`resistance_parts`는 각 경계의 저항 기여입니다. `network(C=..., G=...,
length=..., z_ref=...)`는 기존 RLGC 변환을 쓰므로 C/G의 기하·주파수가 같아야 합니다.

아래는 바닥 금속과 코팅 접지 패턴을 다르게 지정하는 준비 예제입니다.
치수는 m, 전도도는 S/m입니다. 주석의 함수를 호출하면 실제 전류장을 계산합니다.
전체 계산을 저장하려면 [접지 금속별 저장 선로](shape_reference_panel_line.md)를 사용합니다.

```python
from sipi import CrossSection, Layer, Trace, MetalLayer
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal
from sipi.face_conductor import ReferenceSurfaceMetals
from sipi.shape_reference_conductor import panel_shape_conductor_loss_with_reference_metals

section = CrossSection([Layer('uniform', .01105, 4.2)], [
    Trace('a', -.0005, .0003, .001, 50e-6),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True),
    Trace('b', .0005, .0004, .001, 60e-6),
], .02)
signals = {'a': SurfaceMetal(58e6), 'b': SurfaceMetal(35e6)}
reference = ReferenceSurfaceMetals(
    bottom=SurfaceMetal(45e6), top=None, sides=None,
    conductors={'guard': LayeredSurfaceMetal(58e6, coatings=(
        MetalLayer(.2e-6, 14e6, 3.), MetalLayer(1e-6, 40e6)))})
options = dict(conductors=signals, reference=reference, ground_thickness=35e-6,
               panels_per_edge=64, ground_modes=1024, interpolation_degree=16,
               step_fraction=.001)
# result = panel_shape_conductor_loss_with_reference_metals(
#     section, [1e9, 4e9, 16e9], **options)  # Starts the current extraction.
```

독립 평면 금속 전달식·경계별 합·수동 4포트 식·정확한 접지 재합산과 선택한 유한 패널 관측을 검증합니다. 전류 추출은 유한 영역 근사입니다. 외곽 충분성·작은 상호항/절대 정확도·실측 동박 특성·임의 기하 지원을 입증하지 않습니다.
