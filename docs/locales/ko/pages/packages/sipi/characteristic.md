# 전체 행렬을 사용하는 전방파 전파

[차동·공통 좌표](mixed_characteristic.md)에서도 쌍의 전체 결합 행렬을 보존합니다.

`rlgc_characteristic(frequency, R=..., L=..., G=..., C=..., names=None)`는 **원래
도체 전압·전류 좌표**에서 전방파 행렬을 계산합니다. 짝/홀 쌍으로 투영하지 않고
비대칭 상호 다도체 RLGC를 지원합니다. 입력은 `rlgc_network`와 같은 실수 대칭
양의 준정부호 R/G, 양의 정부호 L/C이며 `(N,N)` 또는 `(F,N,N)` 형태입니다.
주파수는 엄격히 증가하는 양수여야 하고 DC는 제외합니다. SI 단위와 `exp(+jωt)`를 사용합니다.

직렬 임피던스 `Z=R+jωL`, 병렬 어드미턴스 `Y=G+jωC`에서 결과는 다음을 만족합니다.

```
Gamma_v^2 = Z Y
Zc = Gamma_v^-1 Z,  Yc = Zc^-1
dV/dz = -Gamma_v V
I(z) = Yc V(z)
V(z) = exp(-Gamma_v z) V(0)
```

z는 횡방향 메시 x/y와 구분되는 선로 진행 거리입니다. I는 +z 방향을 양수로 하며,
유한 네트워크의 먼 쪽 포트 전류는 선로 안으로 향하므로 `-I(length)`입니다.

`LineCharacteristic`에는 복사된 읽기 전용 `frequency`, 도체 `names`, 그리고 세
`(F,N,N)` 배열이 있습니다. `gamma_voltage`는 1/m, `z_characteristic`은 Ω,
`y_characteristic`은 S입니다. `voltage_transfer(length)`는 유한 비음수 길이(m)의
읽기 전용 행렬 지수를 반환합니다.

이 값들은 도체별 스칼라가 아닌 **행렬**입니다. 대각 원소를 일반적으로 모드 임피던스나
전파상수로 해석할 수 없습니다. 전달 행렬은 순수 전방파를 가정하며 S21·단자 전압원
응답·반사를 포함한 유한 선로 응답이 아닙니다. 기준 임피던스가 있는 유한 포트 해석은
`rlgc_network`를 사용하세요. 일반 행렬 Zc를 회로 종단 API의 대각 부하 사전으로
그대로 전달할 수도 없습니다.

## 예제

```python
import numpy as np
from sipi import rlgc_characteristic

result = rlgc_characteristic(
    [1e6, 1e8, 1e9],
    R=[[2, .2], [.2, 3]],
    L=np.array([[400, 60], [60, 300]])*1e-9,
    G=[[.002, -.0003], [-.0003, .003]],
    C=np.array([[100, -15], [-15, 80]])*1e-12,
    names=('first', 'second'),
)
transfer = result.voltage_transfer(.02)
initial_voltage = np.array([1+0j, 0j])
voltage = transfer @ initial_voltage
current = np.einsum('fij,fj->fi', result.y_characteristic, voltage)
power = .5*np.einsum('fi,fi->f', voltage.conj(), current).real
assert np.all(power >= 0)
```

`TransmissionLineResult.characteristic()`와 `VolumeLineResult.characteristic()`는
이미 구한 RLGC와 도체 이름을 재사용하며 추가 장 해석을 하지 않습니다. 기울어진
주축 재료를 저장한 선로가 기존 스칼라 모드 대칭 계약을 만족하지 않아도 사용할 수
있습니다. 별도 `propagation()`/`rlgc_propagation` API는 여전히 단일 또는 엄격한
교환 대칭 쌍만 받고 기존 스칼라 감쇠 분해를 유지합니다. 이번 API는 일반 모드의
이름·순서 추적이나 모드별 손실 분해를 제공하지 않습니다.

## 분기·조건수·수동성

Z와 Y를 각각 정규화한 뒤 `Gamma_v = j sqrt(-Z Y)`로 물리적 분기를 계산합니다.
정확히 무손실인 선로에서 `sqrt(Z Y)`의 음의 실수축 분기 문제를 피합니다.
무손실 문제의 제곱근 입력을 실수로 유지하므로 검증 사례의 전파 행렬 실수부는
정확히 0입니다. 고유벡터 정렬·역행렬이 필요 없고 중복되거나 가까운 전파근도 처리합니다.

SciPy 행렬 제곱근과 선형 해를 사용합니다. 조건수 `1e12` 초과, 비유한/표현 불가능한
수치, 상대 `1e-10`을 넘는 제곱근·구성 관계·역행렬·상호성 잔차를 거부합니다.
허용된 상호성 반올림만 평균 처리하며 의사역행렬·정규화 보정·대각 투영·비대칭 선로의
묵시적 대칭화는 하지 않습니다. Zc/Yc 실수부는 양의 정부호여야 합니다. 전방 고유값은
양의 위상과 명시한 반올림 범위 안의 비음수 감쇠를 요구합니다. 조건이 지나치게 나쁘거나
표현할 수 없는 경우에는 결과를 인증하지 않고 거부합니다.

순수 전방파의 `H=(Yc+Yc^H)/2`에 대해 평균 전력은 `P=V^H H V/2`이며 정확한
국소 전력 항등식은 다음과 같습니다.

`Gamma_v^H H + H Gamma_v = Yc^H R Yc + G`.

우변은 도체·유전체 **전력 이차형식**의 분리이며 원소별 또는 모드별 스칼라 감쇠
분해가 아닙니다. 물리적 전력이 감소해도 간섭으로 전압의 유클리드 노름은 증가할
수 있습니다. 무손실 전방 전달은 이 전력 계량을 보존합니다.

## 독립 검증과 한계

```sh
python -m pytest -q -s tests/sipi/test_characteristic_matrix.py tests/sipi/test_propagation.py
```

독립 scikit-rf 2.2.0 `DistributedCircuit` 스칼라 해를 알려진 비직교 실수 T로
변환해 비대칭 3도체 문제를 구성합니다. `Z=T diag(z) T^T`,
`Y=T^-T diag(y) T^-1`이면 정확한 결과는 `Gamma=T diag(gamma) T^-1`,
`Zc=T diag(zc) T^T`입니다. 손실·무손실 모두 Gamma·Zc·전압 전달의 최대 노름 기준
상대 차이가 `1e-10` 이내여야 합니다.

단일 및 차동/공통 정규화, 중복/근접 근, 독립 SPD 형식, 전력 보존/소산, 전체 블록
전송선 방정식 지수, 길이 합성, 도체 좌표 변환·순열, 주파수별 입력, 복사, 거부 관문도
검사합니다. RLGC 공통 배율 `1e-200`~`1e200`은 실제 ZY의 overflow 없이 정규화를
확인하는 수치 스트레스 사례이며 재료 유효범위가 아닙니다. 실제 비대칭 텐서 공유 메시·
체적 선로로 진단 연결도 확인합니다.

균일 선로의 RLGC 대수 계산이므로 기존 메시·재료 보정·도체 근사·준TEM 유효성을
개선해 주지는 않습니다. 3D 전이·방사·비상호 매질·시간영역 모드 추적·새 운영체제·
브라우저/무설치 화면 지원을 제공하는 작업도 아닙니다.

[스칼라 모드 전파](propagation.md) · [네트워크](network.md) ·
[저장 선로](line_model.md) · [English](../../../../../packages/sipi/characteristic.md)
