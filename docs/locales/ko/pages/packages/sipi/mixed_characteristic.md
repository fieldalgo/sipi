# 차동·공통 좌표의 특성 행렬

`LineCharacteristic.mixed_mode()`는 두 도체 쌍의 전체 전방파 행렬을 차동·공통
좌표로 나타냅니다. 첫 도체가 +, 둘째가 −이며 이름으로 극성을 추정하지 않습니다.
single-ended 좌표 두 개만 받으며 이미 변환한 결과의 재변환은 거부합니다.

```python
import numpy as np
from sipi import rlgc_characteristic

line = rlgc_characteristic([1e6, 1e9],
    R=[[6, .4], [.4, 11]], L=np.array([[400, 80], [80, 310]])*1e-9,
    G=[[.004, -.001], [-.001, .006]], C=np.array([[100, -20], [-20, 130]])*1e-12,
    names=('plus', 'minus'))
mixed = line.mixed_mode()
assert mixed.basis == 'mixed-mode'
assert mixed.names == ('differential', 'common')
mixed.z_characteristic
mixed.voltage_transfer(.01)
```

전압과 +z 방향 전류의 정의는 다음과 같습니다.

```
Vd = V1 - V2          Id = (I1 - I2)/2
Vc = (V1 + V2)/2      Ic = I1 + I2
```

복소 전력 `V1 conj(I1)+V2 conj(I2) = Vd conj(Id)+Vc conj(Ic)`를 보존합니다.
전압 변환 A와 전류 변환 B=A^(-T)에 대해 `Gamma_m=A Gamma_v A^(-1)`,
`Z_m=A Zc A^T`, `Y_m=B Yc B^T`입니다. 차동·공통 순서에서
`dV_m/dz=-Gamma_m V_m`, `I_m=Y_m V_m`, `V_m=Z_m I_m`을 만족합니다.
단위·양의 주파수 조건·+z 전류·`exp(+j omega t)` 규약은 그대로입니다.
voltage_transfer는 순수 전방파 전압 전달이며 유한 선로의 S21이 아닙니다.

이는 **좌표 변환**이지 고유모드 추출·추적이 아닙니다. 비대칭 쌍에서는 Z/Y/Gamma의
비대각 항이 0이 아닐 수 있습니다. 차동 전류만 입력해도 공통 전압이 생기고
전파 중 두 성분이 섞일 수 있습니다. 비대각 항을 버리거나 대칭을 추정하지 않습니다.
`Z_m[0,0]`은 전방파 입력에서 Ic=0일 때 차동 전압/전류 비이며 일반적인 독립
차동 고유모드 임피던스가 아닙니다. 교환 대칭 쌍에서만 기존 대각 차동·공통 모드로
환원되어 `Zdiff=2 Zodd`, `Zcommon=Zeven/2`를 만족합니다.

basis 기본값은 single-ended여서 기존 다섯 인자 LineCharacteristic 생성자를
유지합니다. mixed-mode는 좌표 두 개가 필요합니다. 배열은 복사/읽기 전용이며
출력 이름은 differential·common입니다. 원본 이름과 배열은 보존합니다. 변환 후에도
기존 유한값·상반성·실수부 양의 정부호·역행렬 잔차·전방근·조건수 관문을 적용합니다.
표현할 수 없는 변환은 물리량을 임의로 재스케일하거나 부분 결과를 내지 않고 실패합니다.

공유 메시와 금속 체적 선로 결과 모두 `result.characteristic().mixed_mode()`를
추가 장 해석 없이 사용합니다. 저장 선로 JSON은 그대로입니다. scalar propagation()
API는 여전히 비대칭 쌍을 거부합니다. 좌표 변환이 독립 짝/홀 모드를 만드는 것은
아닙니다. 공차/역산의 z_diff도 기존 대칭 준정적 정의를 유지합니다. 별도의
LineNetwork.mixed_mode()는 네 포트 순서를 갖는 유한 선로 S 변환이며 이 API는
두 전방 전압/전류 좌표를 다룹니다.

동일 임피던스 행렬에 대한 독립 scikit-rf 일반화 혼합 파동 변환으로 손실/무손실
비대칭 쌍의 Z/Y를 normwise 상대 1e-10으로 대조합니다. 대칭 scalar 모드 극한,
복소 전력 보존·구성 방정식·극성 반전·전방 전달은 1e-12, 별도 변환 RLGC의 행렬은
1e-10으로 검사합니다. 비대각 항 보존, 미지원 개수/basis 거부, 두 추출 결과의
추가 메시 없음도 확인합니다. 정규화와 대수 검증이며 기존 장 해석·메시/외곽·RLGC·
재료 유효성 조건은 유지됩니다. 실측 적층판·모드 추적·새 솔버·플랫폼 검증은 아닙니다.

[전체 행렬](characteristic.md) · [English](../../../../../packages/sipi/mixed_characteristic.md)
