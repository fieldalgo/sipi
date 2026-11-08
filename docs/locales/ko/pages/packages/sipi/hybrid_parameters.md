# 물리 단위의 2포트 하이브리드 파라미터

[English](../../../../../packages/sipi/hybrid_parameters.md) | **한국어**

`hybrid_network(frequency, hybrid, *, z_ref, names=None)`는 물리 H 표본을,
`inverse_hybrid_network(frequency, inverse_hybrid, *, z_ref, names=None)`는 물리 G
표본을 직접 변환하여 단일 종단 `LineNetwork`를 반환합니다.
기존 [물리 Z/Y API](parameter_network.md)는 그대로입니다.

전류는 두 포트 모두 회로 안으로 들어가며 위상자는 exp(+jωt)입니다.

| 종류 | 정의식 | 11 단위 | 12/21 단위 | 22 단위 |
|---|---|---|---|---|
| H | [V1,I2]ᵀ = H[I1,V2]ᵀ | 옴 | 무차원 | 지멘스 |
| G | [I1,V2]ᵀ = G[V1,I2]ᵀ | 지멘스 | 무차원 | 옴 |

정규화된 파일 값이 아닌 물리 혼합 단위입니다. G는 독립적으로 지정하며 구현이
H를 역산하여 만들지 않습니다.

```python
import numpy as np
from sipi import hybrid_network, inverse_hybrid_network

frequency = [0., 1e6]
through_h = np.array([[[0., 1.], [-1., 0.]]]*2)
network = hybrid_network(frequency, through_h, z_ref=[31., 73.],
                         names=['input', 'output'])
assert network.s.shape == (2, 2, 2)
np.testing.assert_allclose(network.s[0].T @ network.s[0], np.eye(2), atol=1e-12)
```

입력은 정확한(F,2,2) 형태, 불리언을 제외한 유한 수치, 유한·음이 아닌 엄격 증가
주파수 Hz와 명시한 양의 실수 기준 저항(스칼라 또는 두 원소)을 요구합니다.
상수 행렬을 자동 반복하지 않습니다. 이름은 기본 port1/port2 또는 서로 다른
비어 있지 않은 한 줄 문자열 두 개입니다. 복소수나 주파수별 기준 저항은 받지
않습니다. 반환 주파수·S·기준 저항 배열은 독립 읽기 전용이며 이름도 복사합니다.

d1,d2를 기준 저항의 제곱근이라 하면 무차원 H 성분은
H11/d1²,H12*d2/d1,H21*d2/d1,H22*d2²이고 무차원 G 성분은
G11*d1²,G12*d1/d2,G21*d1/d2,G22/d2²입니다. 정규화 v=a+b,i=a-b를 사용하여
B*b+A*a=0을 만듭니다. 무차원 행렬 Q에 대해 다음을 적용합니다.

```
A   = [[1-Q11, -Q12], [-Q21, 1-Q22]]
B_H = [[1+Q11, -Q12], [ Q21,-1-Q22]]
B_G = [[-1-Q11, Q12], [-Q21, 1+Q22]]
S   = -solve(B, A)
```

덧셈 전에 각 주파수의 Q와 단위 행렬 항을
max(1,max(abs(Re(Q))),max(abs(Im(Q))))로 나눕니다. 정규화·중간값·결과의 비유한,
스케일된 특잇값 s_min<=1e-12*max(1,s_max), 정규화 B*S+A 잔차>1e-10이면
거부합니다. 의사역행렬·조건 보정·H/G나 개별 성분의 역산을 사용하지 않습니다.
수치 기준은 명시적인 구현 한계이며 물리 정확도 인증이 아닙니다. H/G가 특이해도
파동 분모가 유효하면 계산할 수 있습니다.

```python
zero_g = inverse_hybrid_network([0.], np.zeros((1, 2, 2)), z_ref=50.)
np.testing.assert_array_equal(zero_g.s[0], np.diag([1., -1.]))
new_reference = network.renormalized([50., 50.])
np.testing.assert_allclose(new_reference.s[0], [[0., 1.], [1., 0.]], atol=1e-12)
assert not network.s.flags.writeable
```

H가0이면 포트1 단락·포트2 개방, G가0이면 포트1 개방·포트2 단락입니다.
이상적인 연결·변압기는 무한 Z 행렬을 만들지 않고 처리합니다. 능동 행렬을
수동으로 바꾸지 않으며 수동성·상반성·인과성·물성·물리 추출을 추론하지 않습니다.

검증은 같거나 다른 기준 저항의 이상적 변압기24사례,0/특이 경계 관계,
행별 물리 전압·전류 식, 수동 RC/RLC 부하의 독립 KCL, 기준 저항 변경과 일관된
단위 배율을 포함합니다. 해석식과 S 비교는1e-12, 물리 VI 잔차는1e-10이며
형태·주파수·기준 저항·이름·스케일·해법 실패를 검사합니다. 회로 대수 연산이므로
공간 메시·외곽 수렴을 주장하지 않고 주파수 보간도 하지 않습니다.

독립 scikit-rf2.2.0 비교는 `h2s`/`g2s`28사례와 직접 `y2s`4사례입니다.
후자는 rank-one 물리 Y에서 시작합니다. `g2s`가 H를 만든 뒤 H22로 나누어 Z를
구성하지만 해당 Y는 유한 Z로 표현되지 않습니다. 원래 비교는 NaN 또는 잘못된
유한 S를 만들었으며 기준 도구 경로의 실패로 기록을 보존합니다. 네 조건부 비교는
원 Y를 직접 쓰고 해석식 S=I-2α/(1+5α)*[[1,2],[2,4]]와 물리 식을 함께 검사합니다.
허용 오차나 후보 계산은 바꾸지 않았습니다. 기록된32조건부 비교의 최대 절대 S
차이는1.93e-15이며 이 대수 사례의 일치이지 실측 정확도가 아닙니다.

BSD-3-Clause scikit-rf는 시험 전용이며 저작권·조건·면책문을 검증 기록에
보존합니다. 런타임 의존성·저장 스키마·앱·플랫폼 지원을 추가하지 않습니다.
물리 Touchstone2 파일은 [별도 H/G 읽기](touchstone_hybrid.md)를 사용합니다.
