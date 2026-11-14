# 직선면 형상전류에 표면 재료 적용

`panel_shape_conductor_loss_by_face`는 [직선면 형상전류 에너지](panel_shape_faces.md)에
서로 다른 국소 표면 재료를 적용합니다. 아래쪽 접지·위/옆 개방 경계에서 유한 두께의
직사각형 또는 사다리꼴 `Trace` 1~4개를 지원합니다. 각 신호 이름에는
bottom/top/left/right 순서의 `TraceFaceMetals`가 필요합니다.
사다리꼴의 left/right는 기울어진 옆면입니다.

`reference`는 명시적인 `ReferenceSurfaceMetals`여야 합니다. 아래 접지면의 재료,
개방된 위/옆 경계의 `None`, 각 접지 패턴 이름의 정확한 대응을 입력합니다.
접지 패턴은 전체 둘레용 `SurfaceMetal` 또는 네 면의 `TraceFaceMetals`를 받습니다.
전체 둘레 지정은 네 면 에너지의 합을 사용하며 별도로 미분한 전체 경계 값으로
대체하지 않습니다. 원래의 면 합 대 전체 경계 항별 상대 1e-4 검사도 유지합니다.

기존 `SurfaceMetal`의 벌크·명시 거칠기와 `LayeredSurfaceMetal`의 평면 도금식을
재사용합니다. 각 경계의 전도도·투자율·주파수·침투 깊이·남는 코어 치수를
전계 계산 전에 검사합니다. 얇은 접지면과 두꺼운 접지 패턴은 각자의 치수를 씁니다.
도금과 거칠기는 함께 적용할 수 없으며 실측 거칠기 값을 추정하지 않습니다.
입력 기하는 완성된 PEC 표면이고 도금은 그 안쪽을 차지하는 국소 고주파 섭동입니다.
도금 모서리나 유한 금속 내부를 직접 푸는 모델은 아닙니다. 기존 양도체·침투 깊이
조건을 유지합니다.

`ShapeFaceConductorLoss`는 주파수, R [ohm/m], 내부 L [H/m], 침투 깊이, 거칠기 계수,
표면 임피던스 [ohm/square], 재료 대응, `boundary_labels`, `boundary_parts` [1/m]를
불변 배열로 보존합니다. 경계 순서는 신호 순서대로 네 면씩, 아래 접지면, 기하 순서의
각 접지 패턴(전체 하나 또는 네 면)입니다. 이는 원래 기하 순서로 섞인 면별 에너지와
다르므로 이름과 구조로 대응합니다. 신호 사이에 접지 패턴이 있어도 대응을 유지합니다.

R = sum(Re(Zs_b)*Q_b), 내부 L = sum(Im(Zs_b)*Q_b/omega)이며
`resistance_parts`는 각 경계의 기여입니다. `factors`에 모든 면별 표본과 원래
`base` 전체전류 표본, C0, 외부 L을 보존합니다. 에너지를 부호 있는 면별 전류로
해석하지 않으며 보존 진단은 `factors.base.current_integrals`의 원래 그룹 값을 씁니다.
재조정·PSD 투영 없이 원래 전체/면별 오류, 부분 표본, 중단을 그대로 전달합니다.
자원 제어와 최대 85회 공유 풀이 제한은 면별 에너지 API와 같습니다.

아래 예제는 입력만 만듭니다. 호출 주석을 해제하면 계산합니다. 단위는 미터·헤르츠입니다.

```python
from sipi import CrossSection, Layer, Trace, MetalLayer
from sipi import panel_shape_conductor_loss_by_face
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.boundary_conductor import SurfaceMetal, LayeredSurfaceMetal

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
copper = SurfaceMetal(58e6)
coated = LayeredSurfaceMetal(58e6, coatings=(MetalLayer(.2e-6, 14e6, 3.),))
conductors = {'a': TraceFaceMetals(copper, coated, copper, copper),
              'b': TraceFaceMetals.uniform(copper)}
reference = ReferenceSurfaceMetals(copper, None, None,
    {'guard': TraceFaceMetals.uniform(SurfaceMetal(40e6))})
options = dict(conductors=conductors, reference=reference, ground_thickness=35e-6,
               panels_per_edge=32, ground_modes=4096,
               interpolation_degree=16, step_fraction=.001)
# result = panel_shape_conductor_loss_by_face(section, [1e9, 4e9], **options)
# print(result.boundary_labels, result.R, result.L_internal)
```

`result.network(C=..., G=..., length=..., z_ref=...)`는 원래 외부 L에 내부 L을 더하고
입력한 유전체 C/G를 사용합니다. 호출자가 같은 기하·신호 순서·주파수의 C/G를 제공해야
합니다. 이 직접 API는 유전체 전계를 계산하거나 새 저장 JSON 스키마를 추가하지 않습니다.

독립 표면 재료 전달행렬, 양의 국소 전력, 균일 면 재료와 원래 전체전류 손실의 일치,
실제 사다리꼴 접지 패턴의 패널 세분·신호 순열, 독립 4포트 전달·수동성, 사전 거부와
오류 보존을 검사합니다. 소스·격리 설치본 시험과 플랫폼 검증은 구분합니다.
유한 영역 수렴 관측과 앞선 독립 전류 기준은 임의 기하의 절대 정확도나 작은 상호항
정확도를 보장하지 않습니다. 대상 기하의 패널과 외곽을 별도로 세분해야 합니다.
브라우저/EXE 연결, 면별 손실 저장 입력, 새 플랫폼 검증은 이 직접 API 단위의 범위 밖입니다.
