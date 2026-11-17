# All-active 모서리 전류와 도체 손실

[English](../../../../../packages/sipi/two_ground_corner_conductor.md)

`sipi.two_ground_corner_conductor`의 명시 함수는 공유 corner-power 장 계산을
SIPI의 기존 표면 금속 법칙에 연결한다.

- `two_ground_corner_current_factors`: 전체 표면과 분리된 두 동박.
- `two_ground_corner_face_current_factors`: 도체 아래·위·왼쪽·오른쪽 면.
- `two_ground_corner_conductor_loss`: 전체 경계별 국소 금속 법칙.
- `two_ground_corner_conductor_loss_by_face`: 도체 면별 국소 금속 법칙.

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.two_ground_corner_conductor import two_ground_corner_conductor_loss_by_face

section = CrossSection(
    [Layer("uniform", 0.002, 4.0)],
    [Trace("signal", x=0.00015, y=0.0008, width=0.0006, thickness=0.00007)],
    width=0.008, top="ground",
)
metal = SurfaceMetal(58e6)
loss = two_ground_corner_conductor_loss_by_face(
    section, [1e9, 3e9, 10e9],
    conductors={"signal": TraceFaceMetals.uniform(metal)},
    reference=ReferenceSurfaceMetals(metal, metal, None, {}),
    ground_thickness=35e-6, panels_per_edge=128, ground_modes=256,
)
```

## 범위와 해상도

유한 사각형/사다리꼴 `Trace` 1~2개가 모두 신호여야 하고 아래·위 접지 및 측면
개방이어야 한다. 접지 trace, 면 배정의 일반 다각형, 신호3개 이상은 명시 거부한다.
기존 [전체 표면](two_ground_conductor.md)·[면별](two_ground_face_conductor.md) 방법과
기본값은 유지한다. 정확히 고정한 공유 기능이 없으면 대체 없이 `RuntimeError`이다.

길이는 미터, 주파수는 헤르츠이다. `panels_per_edge`는 짝수 cubic 분할 `16..512`이며
corner patch를 합치면 edge당 실제 `n-6`개, 사각 도체 두 개의512분할에서 최대4048개다.
기본 분할은128이다. `interpolation_degree`는24로 고정하고20과 비교한다.
`ground_modes`는 **실제 fine** Fourier 모드 수인 짝수 `64..4096`, 기본256이며 절반의
모드 수 및 구적16/32와 비교한다. 기존 방법의 coarse 모드 수 의미와 다르다.

공유 솔버는 모서리 밀도와 squared-current Gram을 적분하며 내부 잔차·세분`1e-10`,
condition`1e10`미만을 검사하고 불변 whole/edge 결과 하나를 반환한다. SIPI는 수치
`solve(C,C)` 변환 없이 all-active 기저를 직접 보존한다. 실제 endpoint로 면을 맞추어
도체 아래·위·왼쪽·오른쪽, 이어 아래·위 동박 순서로 둔다. 면 합은 작은 부호 교차항도
분모 floor 없이 항별`1e-10`에서 전체 factor를 재현해야 한다. base 진단의 method는
`two-ground-corner-power-all-active`이다.

기존 `TwoGroundCurrentFactors`, `TwoGroundFaceCurrentFactors`, `TwoGroundConductorLoss`,
`FaceConductorLoss` 결과 계약을 유지한다. 전체 금속은 `SurfaceMetal`, 면별은
`TraceFaceMetals`를 받는다. `ReferenceSurfaceMetals`는 두 동박, 측면 법칙 없음,
빈 접지 trace mapping이어야 한다. 기존 코팅·거칠기·잔여 core·표피 깊이 제한을
장 계산 전에 검사한다. 표피 깊이가 남은 최소 도체 치수의1/5보다 크면 거부한다.

Factor는 균일한 자기 외부영역의 진공 전류이며 유전체 metadata는 전류 계산에 들어가지
않는다. `C0`는 진공 정전용량이다. `loss.network(C=..., G=..., length=...)`에는
같은 기하·이름의 실제 유전체 `C/G`를 별도로 계산해 전달해야 한다. 국소 표면섭동
모델은 유한금속 확산·코팅 모서리·실측 동박 보정을 풀지 않는다. 이 함수가 새 저장
JSON 형식이나 UI 경로를 선택하지 않는다.

## 검증 근거와 한계

저장 독립 scikit-fem12.0.2(BSD-3-Clause, 비배포) P3 volume-energy 참조는 편심 사각
하나와 비대칭 사다리꼴 쌍을 다루며 각각 qualified mesh두 개·내부 velocity extension두
개를 사용한다. 진공 정전용량0.05%, 면별factor·가중손실2%, whole1%로 비교하고
1/3/10GHz에서 해석 표면 임피던스 식을 적용한다. 공유 엔진은 별도로 panel`256→512`,
외곽폭`8→16→32mm`, 반사를 분모 floor 없이 검사한다. 원래 실패한 쌍의 참조 mesh는
실패로 보존하고 후속 더 세분한 mesh 쌍을 참조로 쓴다. Replay는 P3를 다시 실행하지 않는다.

표면법칙의 직접 식·선택 면 변화·whole/face 동등성·수동성·기존 상반 네트워크를 확인한다.
선택 수치 사례가 임의 기하·실측·거칠기 보정·다른 플랫폼·브라우저 수락을 뜻하지 않는다.
각 요구량의 panel/outer 수렴을 따로 확인해야 한다. 3활성도체 참조와 고정접지 축약은
각자 기준을 충족하지 못했으므로 이 통과 사례에서 지원을 추정하지 않고 범위에서 제외한다.

## 모서리 방식 전송선 저장

별도 [모서리 면별 전송선](two_ground_corner_face_panel_line.md)은 명시 전류 방식, 동일 기하 유전체와 네트워크 결과를 저장합니다.

더 작은 물리 패널 예산에서 두 밀도 모드를 명시적으로 선택하려면 [선형 모서리 밀도 전류](two_ground_linear_corner_conductor.md)를 참고합니다. 이 문서의 기존 함수와 기본 설정은 유지합니다.
