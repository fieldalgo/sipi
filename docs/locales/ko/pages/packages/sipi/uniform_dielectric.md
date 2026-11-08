# 균일 스칼라 유전체의 진공 정전용량 재사용

주파수별 추출에서 **실제 메시의 모든 요소가 정확히 같은 스칼라 유전율**을
가지면 진공 정전용량을 재사용합니다. 단일 및 다도체 단면에 적용되며 서로
다른 영역 이름도 해당 주파수의 스칼라 값이 같으면 이 조건을 만족합니다.

공간적으로 일정한 스칼라 계수에서는 강성 행렬이 `K=eps*K0`입니다. 도체
전압을 고정한 Dirichlet 전위는 변하지 않으므로 복소 에너지로부터
`C_complex=eps*C0`를 얻습니다. 외부 인덕턴스는 `L=mu0*eps0*inv(C0)`로
유지하며 재료로 스케일하지 않습니다. 기존 양의 시간 부호에서 유전체
컨덕턴스는 `G=-2*pi*f*Im(C_complex)`입니다. 이는 이산 문제의 항등식이며
서로 다른 재료를 유효 유전율 하나로 합치는 모델이 아닙니다.

```python
import numpy as np
from sipi import stripline
from sipi.dielectric import DebyeDielectric, dispersive_line

material = DebyeDielectric(2., [4.], [1e9])
frequencies = [0., 1e8, 1e9, 1e10, 1e12]
section = stripline(width=.5e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3)
sweep = dispersive_line(section, frequencies, materials={'dielectric': material},
    edge_size=1e-6, far_size=.125e-3, grade=.1)
expected = material.permittivity(frequencies)[:, None, None]*sweep.C0
np.testing.assert_allclose(sweep.C_complex, expected, rtol=1e-12, atol=0)
assert not sweep.C_complex.flags.writeable
assert sweep.G[0, 0, 0] == 0
```

## 정확한 선택과 공통 메시 연결

기존 영역-요소 매핑을 매 주파수에 적용합니다. 빠른 경로는 비어 있지 않은
스칼라 벡터, 유한하고 수동인 계수, 양의 실수부, 모든 요소의 정확한 값
일치를 요구합니다. 영역 이름이나 `allclose`로 판단하지 않으며 재료 값을
반올림하거나 이전 주파수의 판정을 재사용하지 않습니다. 1e-12 차이도 일반
솔버를 사용합니다. 실제 요소에 없는 스칼라 영역 값은 장 계수를 바꾸지
않습니다.

등방 텐서를 포함한 텐서와 비균일 스칼라 계수는 기존 복소 해법을 유지합니다.
재료 사전 검증, 공개 API의 알 수 없는 영역 거부, 도체/기준 경계, 신호 순서,
읽기 전용 출력과 저장 입력은 같습니다.

공통 메시 선로 연결은 이미 구한 진공 C0를 내부적으로 전달할 수 있습니다.
재사용은 그 행렬을 수정하거나 도체 모델을 바꾸지 않습니다. 모든 주파수가
균일한 경우 C0용 정전용량 행렬 추출은 한 번이며, C0가 전달되면 추가 추출은
없습니다. 이는 행렬 추출 횟수이며 내부 선형해법, 메시 생성, 최적화 시도
횟수나 실행 시간 보장이 아닙니다. 일반 계수는 기존 추출을 수행합니다.
새 의존성, 공개 API, 저장 스키마는 없습니다.

## 독립 수락 기준과 범위

`tests/sipi/test_uniform_dielectric.py`는 단일 stripline, 대칭 쌍, 동일 재료의
두 영역 쌍을 기존 직접 복소 FE와 비교합니다. C0 전달 여부와 0/.1/1/10/1000
GHz를 검사하며 복소 C의 성분별 상대 차이 한계는 1e-10입니다. 별도의
scikit-fem 12.0.2 복소 P1 조립/Dirichlet 에너지도 쌍 메시에서 같은 한계를
사용합니다. 독립 구현도 메시를 공유하므로 메시 수렴 자체를 입증하지는
않습니다.

복소 평행판의 직렬 정전용량 해로 거의 같지만 다른 층, 한 주파수에서만 같은
층, 대각 및 등방 텐서 경로를 검사합니다. 잘못된 계수 거부, 진공 L, G,
샘플 복사, 신호 순서와 행렬 추출 횟수는 별도로 검사합니다.

얇은 stripline 쌍은 폭 .5 mm, 간격 .1 mm, 평면 간격 1 mm, 상자 폭 8 mm를
사용합니다. edge/far/grade는 1 마이크로미터/.125 mm/.1입니다. 요청 메시,
세 값을 절반으로 줄인 메시, 별도 16 mm 상자 각각에서 다섯 재료 샘플의
차동 및 공통 임피던스가 독립 Cohn 식과 .5옴 이내여야 합니다. 기존 재료,
텐서, 공통 선로, 도체 면, 기준 도체 및 주파수 목표 회귀는 기존 한계를
유지합니다. 실제 응용에서는 해당 유한 메시의 수렴을 계속 확인해야 합니다.

준 TEM 근사나 실제 적층판 특성을 바꾸지 않으며, 시험 주파수의 full-wave
유효성이나 일반적인 앱 속도 향상을 보장하지 않습니다. 런타임/플랫폼 수락은
정확한 빌드 버전의 별도 근거이며 소스 및 설치 엔진 검사와 구분합니다.

[유전체](dielectrics.md) · [주파수 목표](sampled_design.md) ·
[English](../../../../../packages/sipi/uniform_dielectric.md)
