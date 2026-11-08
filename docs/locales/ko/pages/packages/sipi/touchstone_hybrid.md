# Touchstone2 물리 하이브리드 입력

[English](../../../../../packages/sipi/touchstone_hybrid.md) | **한국어**

`sipi.touchstone.loads_touchstone_hybrid(text, *, z_ref, ports=None, port_names=None)`는
엄격한 단일 종단 Touchstone2.0 부분집합에서 명시된 물리 H/G를 읽습니다.
별도 모듈 API이며 기존 [S·물리 Y/Z 읽기](touchstone_parameters.md)의 허용 종류와
동작은 그대로입니다. 정확히 두 포트가 필요합니다.

```python
import numpy as np
from sipi import hybrid_network
from sipi.touchstone import loads_touchstone_hybrid

text = """[Version] 2.0
# Hz H RI R 123
[Number of Ports] 2
[Two-Port Data Order] 12_21
[Number of Frequencies] 1
[Reference] 40 90
[Network Data]
0 80 0 .2 0 -.1 0 .01 0
[End]
"""
network = loads_touchstone_hybrid(text, z_ref=[31., 73.],
                                 port_names=['input', 'output'])
expected = hybrid_network([0.], np.array([[[80., .2], [-.1, .01]]]),
                          z_ref=[31., 73.])
np.testing.assert_array_equal(network.s, expected.s)
```

[IBIS Touchstone2.0 규격](https://ibis.org/touchstone_ver2.0/touchstone_ver2_0.pdf)의
7/10쪽에서 v2 H/G 값은 R/[Reference]의 영향을 받지 않는 물리값이며,13쪽에서
H/G는 두 포트로 제한합니다.11쪽의 삼각 형식은 수치 전치 대칭을 나타냅니다.
명시한 `z_ref`가 출력 파동의 기준 저항을 정하고 파일의 기준 저항은 문법만 검사하며
데이터에 곱하지 않습니다.

H는[V1,I2]=H[I1,V2]이고 H11은 옴/H22는 지멘스입니다. G는[I1,V2]=G[V1,I2]이고
G11은 지멘스/G22는 옴입니다. 비대각은 무차원이며 전류는 두 포트 안으로 들어갑니다.
해석한 행렬은 [직접 물리 하이브리드 변환](hybrid_parameters.md)에 한 번 전달하며
기존 유한값·조건·잔차 기준을 유지합니다. H/G나 개별 성분을 역산하지 않습니다.

RI/MA/DB,Hz/kHz/MHz/GHz,명시한 두 포트 순서21_12/12_21,줄 분할,
ASCII 주석·정보 블록,Full/Lower/Upper 행렬은 공통 엄격 파서를 사용합니다.
삼각 재구성은 켤레가 아닌 보통 전치이며 전체 행렬의 두 포트 순서와 무관합니다.
수치적으로 대칭인 H/G가 상반성을 뜻하지는 않습니다. 상반 하이브리드의 비대각은
서로 반대 부호입니다.

```python
changed = text.replace('R 123', 'R 701').replace('[Reference] 40 90', '[Reference] 2 900')
same = loads_touchstone_hybrid(changed, z_ref=[31., 73.])
np.testing.assert_array_equal(same.s, network.s)
np.testing.assert_array_equal(same.z_ref, [31., 73.])
assert not same.s.flags.writeable
```

버전·H/G 옵션·포트/주파수 개수·두 포트 순서·데이터·종료 블록은 지원하는 엄격한
문법을 따라야 합니다. `ports`를 주면2와 같아야 합니다. 출력 기준 저항은 필수이며
양의 실수 스칼라/두 값이어야 합니다. 이름은 유효한 고유 문자열 두 개이며 하나의
문자열은 거부합니다. 반환 주파수/S/기준 저항 배열은 독립 읽기 전용입니다.
파일 입출력은 호출자가 담당하고 주석에서 물리 포트 짝을 추론하지 않습니다.

v1·기본값/S/Y/Z·비2포트·혼합 모드·잡음·미지원 키워드·중복/잘못된 순서의
메타데이터·잘못된 단위/수치·불완전 레코드·유효하지 않은 기준 저항·원래 변환
실패를 거부합니다. v1 정규화·자동 보간·수동성·인과성·측정 출처·재료 피팅을
추론하지 않습니다.

검증은 해석한 물리 행렬과 직접 API 입력의 정확한 동일성을 검사하고0 H/G 경계,
이상적 변압기·rank-one 역하이브리드 식을1e-12에서 대조합니다. 출력 기준을
고정하면 파일 기준 저항 변경으로 결과가 바뀌지 않습니다. 두 삼각 순서는 같은
결과를 재구성하고 기존 S110개·Y/Z124개 fixture의 배열/메타데이터 해시도
정확히 보존합니다.

scikit-rf2.2.0의 동일 파일 독립 비교20개는 전체 행렬12개(H/G·RI/MA/DB·두 순서),
12_21로 기록한 하삼각/상삼각 RI/MA8개입니다. 원래21_12 삼각 비교는 실패했습니다.
기준 파서가 일부만 채운 행렬을 먼저 전치한 뒤 원래 지정한 삼각으로 복사하여
비대각 데이터를 잃는 경로입니다. 원 파일/결과를 보존하며 그8개를 통과로 세지
않습니다. 조건을 명시한 순서 비교는 같은 물리 행렬과 원래 절대 S1e-12 기준을
유지하며 연구 최대 차이는4.64e-15입니다. 두 순서 모두 원시 물리값 재구성도
검사합니다. 제품 파서를 바꾸거나 임의 기준 파서의 정확도를 주장하지 않습니다.

[rank-one G 기준 경로의 한계](hybrid_parameters.md)도 유지합니다. 일부 기준
경로는 존재하지 않는 유한 Z를 만들지만 직접 파동 식은 유효하므로 해당 파일은
독립 해석식으로 검사합니다. scikit-rf는 기존 BSD-3-Clause 고지를 유지한 시험
전용입니다. 런타임 의존성·저장 스키마·물리 장 모델·앱·플랫폼 지원을 추가하지
않으며 회로 대수 연산에 공간 수렴을 주장하지 않습니다.


[별도 정규화 v1 Y/Z/H/G 읽기](touchstone_normalized.md)는 입력 스칼라 기준으로 물리 단위를 복원합니다.
