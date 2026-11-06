# 횡방향 이방성 정전계

`capacitance_matrix(mesh, eps_r, signals, ground)`는 상대 유전율로 scalar,
삼각형별 scalar `(T,)`, 일정한 횡방향 행렬 `(2,2)`, 삼각형별 행렬 `(T,2,2)`를
받습니다. 텐서 축은 메시의 **전역 x/y축**입니다. 기존 galerkin P1 텐서 강성행렬을
사용하며 별도 전계 솔버를 만들지 않습니다.

텐서는 상호적 복소 대칭이며 실수부가 양의 정부호, `exp(+jωt)` 규약에서
`−Im(eps_r)`가 양의 준정부호여야 합니다. 상대 1e-12로 대칭을 검사하고 그 범위의
반올림만 평균합니다. 손실 행렬 고윳값도 준정부호 주위 상대 1e-12 반올림을
허용합니다. 성분은 유한 수치여야 하며 bool은 거부합니다. 수동 텐서에도 양의
허수 비대각 성분이 있을 수 있습니다. 수동성은 성분별 부호가 아닌 **행렬 조건**입니다.
비상호·부정부호·능동 텐서는 거부합니다. 결과는 F/m의 복소 Maxwell 용량
`C−j C_loss`입니다.

`line_parameters`는 **실수** 텐서와 scalar/삼각형별 tan_delta를 받습니다.
각 지역의 손실탄젠트 하나가 지역 텐서 전체를 곱합니다. 축별 tangent 행렬은 받지
않고 복소 텐서에 다른 손실 모델을 자동 혼합하지 않습니다. 독립 손실 축을 가진
일반 복소 텐서는 capacitance_matrix를 사용하세요. 기존 scalar/삼각형별 동작은
유지합니다.

```python
import numpy as np
from sipi import coupled_microstrip, line_parameters

section = coupled_microstrip(
    width=.5e-3, gap=.3e-3, substrate_height=.5e-3,
    eps_r=4, tan_delta=.01, thickness=35e-6,
    air_height=4e-3, box_width=8e-3,
)
meshed = section.mesh(edge_size=4e-6, far_size=.25e-3, grade=.2)
materials = {
    'substrate': np.array([[3.5, .7], [.7, 4.5]]),
    'air': np.eye(2),
}
eps = np.array([materials[meshed.mesh.region_names[i]]
                for i in meshed.mesh.regions])
parameters = line_parameters(
    meshed.mesh, eps, meshed.signals, meshed.ground,
    tan_delta=meshed.tan_delta,
)
parameters.C, parameters.C0, parameters.L, parameters.G(1e9)
```

메시 API에 계수를 명시적으로 전달하는 예제입니다. section.analyze()는 여전히
원래 scalar 층 재료를 사용합니다. Layer·템플릿 eps_r·기하 JSON·주파수 재료
문서는 아직 텐서를 받지 않습니다. 입력 텐서장과 정확한 메시/빌드 식별자를 따로
보존해야 하며, 새 저장 스키마를 뜻하지 않습니다. LineParameters는 기존 진공 C0와
비자성 준TEM `L=μ0 ε0 C0⁻¹` 근사를 유지합니다. 비대칭 재료/기하 쌍에 정확한
even/odd 모드를 추정하지 마세요. 종방향 z 결합 성분·비상호성·자기 이방성·
full-wave 전파는 이 2차원 계약 밖입니다.

## 독립 검증

단위행렬 텐서는 기존 scalar/삼각형별 C·C0·L·C_loss를 상대 1e-12로 재현합니다.
축 정렬 층상 평행판은 독립 복소 해석식 `C=ε0 W/(h1/eps_yy1+h2/eps_yy2)`와
진공 인덕턴스를 상대 1e-9로 검사합니다.

정확한 좌표변환으로 회전한 타원 동축선의 기준을 만듭니다. 양의 실수 정부호 A와
`x=A^(1/2) ξ`에서 ξ의 원형 반경 a,b는 실제 타원이 되며, 텐서 A(1−j tanδ)는
`C=2π ε0 sqrt(det A)(1−j tanδ)/ln(b/a)`를 줍니다. 반경/각도 분할을
16/64 → 32/128 → 64/256으로 늘릴 때 오차가 감소하고 수렴 차수 1.5 이상,
최종 상대 오차 0.1% 이하를 요구합니다. 좌표와 재료의 동시 회전·균일 기하 확대는
용량을 상대 1e-12로 보존합니다. 동축 외곽 접지는 물리 경계이며 인공 개방 외곽의
수렴 검사가 아닙니다.

이종 복소 텐서의 차동 microstrip은 같은 메시의 scikit-fem 12.0.2 독립 이방성
복소 P1 에너지와 최대 상대 C 차이 1e-9로 비교합니다. 별도 4→1μm 모서리 메시
세분화 및 상자/공기 높이 두 배 변화는 각각 복소 C 성분의 최대 상대 변화 1% 이하를
요구합니다. 같은 메시 비교만으로 수렴을 증명하지 않습니다. 상호성·양의 용량/
손실 행렬·입력 사본·잘못된 shape·대칭·정부호·수동성·손실 표현도 검사합니다.

이는 명시한 수치 문제의 검증이지 실측 적층재·주파수 의존 텐서 분산·3차원 전이·
새 플랫폼 정확도 검증이 아닙니다.

[개요](overview.md) · [유전체 분산](dielectrics.md) ·
[English](../../../../../packages/sipi/tensor_electrostatics.md)
