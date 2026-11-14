# FEM 형상 에너지 전류를 이용한 금속 손실

`fem_shape_conductor_loss_by_boundary`는 명시적으로 검산한
[FEM 형상 에너지 전류](fem_shape_conductor.md)에 기존 `SurfaceMetal` 또는
`LayeredSurfaceMetal` 법칙을 적용합니다. 신호마다 하나의 재료를 지정하고,
위·아래 접지면 및 유한 접지 패턴은 모두 하나의 명시적인 reference 재료를
공유합니다. 개별 동박 면을 분리하지 않으며 기존 손실 API와 저장 선로의 기본값은
바뀌지 않습니다.

```python
from sipi import fem_shape_conductor_loss_by_boundary
from sipi.templates import coupled_stripline
from sipi.boundary_conductor import SurfaceMetal

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            thickness=.00005, eps_r=4., box_width=.008)
metals = {'positive': SurfaceMetal(58e6), 'negative': SurfaceMetal(35e6)}

def calculate():
    return fem_shape_conductor_loss_by_boundary(
        section, [2e9, 5e9], conductors=metals,
        reference=SurfaceMetal(58e6), ground_thickness=35e-6,
        edge_size=2.5e-6, far_size=.0001, grade=.05)
```

`calculate()`를 호출하면 전계를 풉니다. 재료·잔여 코어·표피 깊이 검사는 메시
생성 전에 수행하며 최대 신호 4개를 허용합니다. 하나의 메시에서 진공 전류 기저와
모든 기하 이동 검산을 계산합니다. 원 기울기 전류 잔차도 기존 기준인 5% 이하여야
합니다. 이 조건은 새 에너지 미분 검사와 별개이며 저항 오차의 상한이 아닙니다.

경계별 R 기여는 `Re(Zs) * Q`, 내부 L은 `Im(Zs) * Q / omega`입니다. 단위는 각각
ohm/m, H/m입니다. 반환된 `BoundaryConductorLoss.factors`는 원 기울기 근거,
두 연장, 두 이동 크기 및 완료된 모든 정전용량 표본을 가진
`FEMShapeCurrentFactors`입니다. `boundary_labels`는 신호 순서 다음 reference
그룹을 나타내며, `resistance_parts`에 경계별 저항 기여를 보존합니다.

코팅은 완성 단면 경계 안쪽을 차지합니다. 기존의 보수적인 잔여 코어 및 국소
평면 표면 법칙의 유효범위를 유지합니다. 코팅 모서리, DC, 금속 내부의 전체
확산을 이 연결 함수에서 풀지는 않습니다. 기존 거칠기 모델의 가정을 유지하며
거칠기 보정이나 서로 다른 측정 규약 사이의 변환을 추정하지 않습니다.

같은 기하·주파수의 유전체 C/G와 함께
`result.network(C=..., G=..., length=..., z_ref=...)`를 사용합니다. 외부 인덕턴스는
동일 진공 C0에서 구하고 내부 인덕턴스를 별도로 더합니다. 이 연결 함수 자체는
요청한 유전체 C/G를 계산하지 않습니다. 다른 신호 순서나 다른 물리 기하에서
얻은 행렬을 섞으면 안 됩니다.

전류 추출 실패는 원 typed exception과 부분 전계 관측을 그대로 보존하며 중단
예외는 전파합니다. 전류 잔차나 재료 검사에 실패해도 다른 전류 방식으로 자동
복구하지 않습니다. 작은 상호항을 포함하여 메시 세분, 외곽 및 독립 기준을
별도로 검증해야 합니다. 관련 시험은 실제 닫힌 차동 메시, 독립 적층 금속 전달식,
4포트 행렬 지수 네트워크를 사용합니다. 선택한 사례의 수락은 임의 기하·실측
정확도 또는 다른 OS·Worker·실행 파일의 지원을 뜻하지 않습니다.
