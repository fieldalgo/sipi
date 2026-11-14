# 명시적 이중 셀 표면전류

`sipi.dual_cell_conductor`는 기존 공유 P1 진공 전계의 경계 반력으로
표면전류를 구하는 선택적 API입니다. 기존 기울기 API와 저장 선로 문서의
기본 계산 방식은 유지합니다.

```python
import numpy as np
from galerkin import rectangle_mesh
from sipi.dual_cell_conductor import dual_cell_surface_current_factors

mesh = rectangle_mesh(.002, .001, 8, 4)
result = dual_cell_surface_current_factors(
    mesh, {'signal': mesh.boundary['top']}, mesh.boundary['bottom'])
np.testing.assert_allclose(result.parts[:, 0, 0], [500., 500.], rtol=1e-10)
assert result.current_error < 1e-10
```

전압 기저 V, 강성 행렬 K의 절점 반력은 r=KV입니다. 각 금속 절점의 D는
그 절점에 붙은 금속 경계 변 길이의 절반 합입니다. 단위 전류로 정규화한
적분 반력 j=eps0*r*inv(C0)로 경계별 sum(j_i.T*j_i/D_i)를 계산합니다.
`parts`는 1/m 단위 (N+1,N,N) 배열이며 `names` 순서의 신호 경계와 마지막
통합 귀환 경계로 구성됩니다. `total`, `C0`, `L_external`,
`current_integrals`는 기존 표면전류 결과와 같은 계약입니다.

이는 경계 이중 셀의 평균값이며 법선 미분 보간이나 정확한 자속 제곱 적분이
아닙니다. `current_error`는 대수적 전류 보존 잔차로 1e-10 초과 시
거부하지만, 저항·전계 오차 추정값은 아닙니다. 근사 FEM 반력으로 엄밀한
저항 상하한을 보장하지 않습니다. 실제 기하의 메시·모서리·외곽 수렴과 작은
상호 항을 각각 확인해야 합니다.

`dual_cell_conductor_loss_by_boundary(section, frequency, conductors=...,
reference=..., ground_thickness=..., **mesh_options)`는 기존 `SurfaceMetal`
또는 `LayeredSurfaceMetal` 법칙을 적용하여 R, 내부 L, 경계별 전력 항을
포함한 기존 경계 손실 결과를 반환합니다. 한 메시와 한 전압 기저를 만들기
전에 유한 코어와 표피 깊이를 검사합니다. 모든 귀환면은 한 재료를 공유하며,
면별 재료법칙과 저장 문서의 이 방식 선택은 아직 포함하지 않습니다.

외부 영역은 등방성·비자성이고 열린 전계 경계의 법선 자속은 0입니다.
표면 임피던스의 고주파·국소 평면 제한을 유지하며 도체 내부 와전류 해석을
대체하지 않습니다.

검증은 정확한 평행판, 동축 다각형 극한, 독립 scikit-fem P1 반력,
크기·반사·순서 불변식과 한 결합 마이크로스트립의 동일 경계 패널 비교를
포함합니다. 이 사례의 세분 전체 행렬은 최대 항 기준 약 0.54% 차이지만,
작은 상호 항은 약 15.45/m 대 10/m입니다. 전체 행렬 오차를 모든 항의
상대 정확도로 해석하면 안 됩니다. 보편적 수렴이나 운영체제별 실행 동등성은
입증하지 않았으며 기존 기울기 방식의 세분화 실패도 별도로 남아 있습니다.

[English](../../../../../packages/sipi/dual_cell_conductor.md)
