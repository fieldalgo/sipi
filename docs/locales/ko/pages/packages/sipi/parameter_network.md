# 물리 임피던스·어드미턴스 표본

[English](../../../../../packages/sipi/parameter_network.md) | **한국어**

`impedance_network(frequency, impedance, *, z_ref, names=None)`와
`admittance_network(frequency, admittance, *, z_ref, names=None)`는 명시한
물리 Z 또는 Y 행렬을 불변 [LineNetwork](network.md)로 변환합니다.
Z는 Ω, Y는 S(지멘스), 주파수는 Hz입니다. 전류는 네트워크 안쪽을 향하며
위상 규약은 exp(+j omega t)입니다. 물리 포트 순서는 호출자가 지정합니다.

```python
import numpy as np
from sipi import impedance_network

frequency = [0., 1e6, 1e8]
impedance = np.array([[[120.]], [[120.+2j]], [[120.+200j]]])  # ohms
network = impedance_network(frequency, impedance, z_ref=50., names=['terminal'])
assert network.s.shape == (3, 1, 1)
assert abs(network.s[0, 0, 0] - 70/170) < 1e-12
```

입력은 양의 N에 대해 정확히 `(F,N,N)` 형태여야 합니다. 단일 포트도 행렬로
주며 상수 행렬의 주파수 방송이나 스칼라 대체는 하지 않습니다. 주파수는 유한한
0 이상 값으로 엄격히 증가해야 합니다. 행렬은 유한한 실수·복소수이며 비대칭도
가능합니다. 불리언·문자열은 거부합니다. 필수 `z_ref`는 유한한 양의 실수 스칼라
또는 포트별 값으로 모든 주파수에서 일정합니다. 복소·주파수별 기준은 지원하지
않습니다. 이름은 포트마다 고유한 비어 있지 않은 한 줄 문자열이며 기본값은
`port1`, `port2`, … 입니다. 결과는 single-ended이며 배열은 복사한 읽기 전용입니다.
변환 성공은 수동성·상반성·인과성·측정 출처·선로/재료 모델의 인증이 아닙니다.
능동 입력은 절댓값이 1보다 큰 S를 만들 수 있습니다.

```python
from sipi import admittance_network

# A resistor between two terminals has a rank-one admittance matrix.
y = np.array([[[1., -1.], [-1., 1.]]])/37.  # siemens
series = admittance_network([0.], y, z_ref=[50., 50.], names=['left', 'right'])
assert abs(series.s[0, 1, 0] - 100/137) < 1e-12
opened = admittance_network([0.], np.zeros((1, 2, 2)), z_ref=50.)
assert np.array_equal(opened.s[0], np.eye(2))
```

`D = diag(sqrt(z_ref))`일 때 정규화 행렬은 임피던스의 경우
`A = D^-1 Z D^-1`, 어드미턴스의 경우 `A = D Y D`입니다. 각각
`S = (A-I)(A+I)^-1`, `S = (I-A)(I+A)^-1`을 우측 선형계 풀이로 계산하며
켤레전치가 아닌 전치를 사용합니다. Z나 Y 자체를 역행렬로 바꾸지 않습니다.
따라서 계수가 부족한 물리 행렬도 유효할 수 있으며 0인 Z는 정확한 단락,
0인 Y는 정확한 개방을 줍니다. 독립 정의는
[scikit-rf z2s](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.network.z2s.html)와
[y2s](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.network.y2s.html)를 참고합니다.

주파수마다 `max(1, max(abs(Re(A))), max(abs(Im(A))))`로 A와 I를 나눈 뒤
파동 분모를 만듭니다. 분모의 최소 특잇값이
`1e-12 * max(1, 최대 특잇값)` 이하이면 거부합니다. 행렬 조건수뿐 아니라
스칼라 분모의 상쇄도 검사합니다. 보수적인 기준이므로 극단적인 유한 수동 입력도
거부할 수 있습니다. 정규화·결과·잔차가 비유한이거나 정규화 풀이 잔차가 1e-10을
넘어도 거부합니다. 유사역행렬·고윳값 자르기·입력 보정은 하지 않습니다. 큰 유한
입력은 중간값을 표현할 수 있는 범위에서만 지원하며 이 기준은 측정 오차 보장이 아닙니다.

[Touchstone](touchstone.md) 파일 해석은 별도입니다. 정규화된 파일 숫자를 물리
Ω/S로 전달하면 안 됩니다. 기존 importer는 문서화한 S 부분집합만 그대로 받습니다.

검증은 `tests/sipi/test_parameter_network.py`에 있습니다. 1–4포트의 비상반·상반·
대각·rank-one 행렬과 서로 다른 기준저항을 독립 scikit-rf 2.2.0과 32조건에서
비교하며 절대 S 차이는 1e-12 이하입니다. V=ZI / I=YV 파동 복원의 상대 잔차는
1e-10 이하입니다. 스칼라 R/L/C 해석, 독립 부하 KCL, 정확한 개방·단락, 포트 순열,
기준저항 변경, 일관된 단위 배율, 복사 및 실패 기준은 별도로 확인합니다.
대수 변환에는 세분할 메시나 외곽 경계가 없으며 기존 장/전파 솔버는 바꾸지 않습니다.
BSD-3-Clause 기준 도구는 시험 전용으로 유지하며 실행 의존성을 추가하지 않습니다.


[별도 Touchstone 2.0 물리 Y/Z reader](touchstone_parameters.md)는 출력 기준을 필수로 지정하며 기존 S reader 계약을 유지합니다.


[물리 2포트 H/G 변환](hybrid_parameters.md)은 명시한 혼합 단위와 직접 파동 식을 사용합니다.
