# Touchstone1 정규화 파라미터 입력

[English](../../../../../packages/sipi/touchstone_normalized.md) | **한국어**

`sipi.touchstone.loads_touchstone_normalized(text, *, ports, z_ref, port_names=None)`는
엄격한 Touchstone1.0 부분집합의 명시된 Y/Z/H/G를 읽습니다. 포트 수와 출력 기준
저항은 필수입니다. H/G는 정확히 두 포트이며 Y/Z는 기존 파서의 양의 포트 수를
지원합니다. 기존 S·물리 v2 Y/Z·[물리 v2 H/G](touchstone_hybrid.md) API의 허용
종류는 그대로입니다.

```python
import numpy as np
from sipi import hybrid_network
from sipi.touchstone import loads_touchstone_normalized

text = '# Hz H RI R 100\n0 .8 0 -.1 0 .2 0 1 0\n'
network = loads_touchstone_normalized(text, ports=2, z_ref=[31., 73.],
                                     port_names=['input', 'output'])
physical = np.array([[[80., .2], [-.1, .01]]])
expected = hybrid_network([0.], physical, z_ref=[31., 73.])
np.testing.assert_array_equal(network.s, expected.s)
```

스칼라 옵션 R(기본50옴)은 입력 정규화 기준입니다. 필수 출력 기준 `z_ref`는
양의 실수 스칼라/포트별 값이며 입력 R과 독립적입니다.

| 입력 | 물리값 복원 |
|---|---|
| Z | Z = R Zn |
| Y | Y = Yn / R |
| H | H11 = R Hn11; H22 = Hn22 / R |
| G | G11 = Gn11 / R; G22 = R Gn22 |

하이브리드 비대각은 무차원으로 유지합니다. H는[V1,I2]=H[I1,V2], G는
[I1,V2]=G[V1,I2]이며 전류는 두 포트 안으로 들어갑니다. 위 식은 이 물리 정의와
스칼라 기준 정규화에서 단위로 유도한 것이며 규격에 그대로 적힌 식을 인용한
것은 아닙니다. [IBIS Touchstone2.0 규격](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)의
7쪽은 v1 R의 역할을,14–15쪽은 정규화된 v1 Z를 물리 v2 Z로 바꾸는 예를
제시합니다. 유한한 물리값을 먼저 복원하고 기존 [Y/Z](touchstone_parameters.md)
또는 [H/G](hybrid_parameters.md) 변환을 한 번 호출하여 원래 수치 기준을 유지합니다.

```python
# Same physical H, with input normalized at a different resistance.
other = '# Hz H RI R 50\n0 1.6 0 -.1 0 .2 0 .5 0\n'
same = loads_touchstone_normalized(other, ports=2, z_ref=[31., 73.])
np.testing.assert_array_equal(same.s, network.s)
np.testing.assert_array_equal(same.z_ref, [31., 73.])
assert not same.s.flags.writeable
```

RI/MA/DB·Hz/kHz/MHz/GHz·ASCII 주석·데이터 줄 분할을 지원합니다.1/2포트는
주파수 레코드 전체를 한 줄에 쓰며 두 포트는11,21,12,22 순서입니다. 더 큰 행렬은
기존 v1 행 배치를 사용합니다. 파일 확장자를 검사하지 않아 `ports`는 항상
명시해야 합니다. Y/Z/H/G를 생략한 옵션을 포함하여 기본 S를 거부합니다.
R은 양의 유한한 실수 하나입니다. 출력 기준은 포트마다 달라도 되지만 입력 R은
하나입니다. 이름은 고유하고 유효한 문자열의 시퀀스이며 문자열 하나는 거부합니다.

v2·v1.1 복수 기준 저항·혼합 모드·잡음·미지원 키워드·잘못된/불완전 레코드·
해석/복원 후 비유한 값·잘못된 개수/기준/이름·원래 조건/잔차 실패를 거부합니다.
배열은 독립 읽기 전용입니다. 파일 입출력·보간·재료 피팅·수동성/인과성·측정
출처나 규격 전체 지원을 추론하지 않습니다.

검증은 네 파라미터·세 값 형식·네 주파수 단위·Y/Z1–4포트·R 불변성·서로 다른
출력 기준·0/이상적 변압기/대각 해석식·엄격한 실패·물리 변환 한 번 호출을
포함합니다. 기존 S/Y/Z/H/G fixture290개의 배열/메타데이터 해시도 정확히 보존합니다.

scikit-rf2.2.0의 동일 파일 비교는 기준 경로를 구분합니다. v1 Z의 R=1/50/100/10000,
Y/H/G의 R=1 경로를 사용합니다. 기준 도구의 v1 파서는 Y/H/G의 모든 원시 성분에
R을 곱하여 R≠1에서 위 물리 단위를 보존하지 않습니다. 이 차이는 기록에 남기며
정확도 근거로 수락하지 않습니다. 동일한 물리 v2 파일은16개 파라미터/R 조합의
별도 기준이며 사전 기준 절대 S1e-12를 유지합니다(연구 최대2.36e-14).
제품 시험은 세 형식의 조건부 동일 파일21개와 R≠1의 동등 v2 파일12개도 검사합니다.
실패한 기준 경로에 맞추어 기준을 완화하지 않았습니다. scikit-rf는 기존
BSD-3-Clause 고지를 유지한 시험 전용입니다. 런타임 의존성·저장 스키마·공간
모델·앱·플랫폼 지원 변화는 없으며 대수 변환에 공간 수렴을 주장하지 않습니다.
