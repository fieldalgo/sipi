# 무손실 단일 선로 시작 응답

[유한 수동 RLGC 회로](rlgc_startup.md)는 상수 손실을 포함한 명시적 회로 셀을 다룹니다.

[입력 저장](startup_document.md)으로 엄격한 JSON 및 공통 실행에 연결할 수 있습니다.

`lossless_line_response`는 **초기 에너지가 없고 균일하며 분산과 손실이 없는
단일 선로**를 계산합니다. 양의 실수 특성 임피던스와 편도 지연, 구간별 선형
Thevenin 입력과 저항 종단을 지정하면 소스/부하 전압, 전류, 진행파를 반환합니다.

```python
import numpy as np
from sipi import lossless_line_response

response = lossless_line_response(np.array([0., 1., 2., 3.])*1e-9,
    source_times=[0.], source_voltages=[1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=1)
np.testing.assert_allclose(response.voltage[:, 1], [0., 1., 1., 1.], rtol=0, atol=1e-14)
np.testing.assert_allclose(response.voltage[:, 0], [.5, .5, 1., 1.], rtol=0, atol=1e-14)
np.testing.assert_array_equal(response.current[:, 1], np.zeros(4))
assert response.terms == 1 and response.port_names == ('source', 'load')
assert not response.voltage.flags.writeable
record = response.to_dict()
```

개방 부하는 편도 지연 뒤 입사 전압을 두 배로 만듭니다. 왕복 지연 뒤 반사가
소스에 도달하고 정합 소스에서 흡수됩니다.

## 입력, 좌표와 기록

`time`, `source_times`는 비어 있지 않은, 비음수 초 단위의 유한 실수 배열이며
엄격히 증가해야 합니다. 한 샘플도 허용합니다. `source_voltages`는 knot마다
하나의 유한 실수 전압을 가지며 bool은 거부합니다. 첫 knot 이전은 0, knot
사이는 선형, 마지막 이후는 마지막 값으로 유지합니다. 첫 값이 0이 아니면 그
시점의 명시적 오른쪽 연속 step이며 한 knot로도 표현합니다. 펄스는 0으로
돌아오는 knot를 지정해야 합니다. 주기 확장, 초기 에너지, 빠진 DC를 추정하지
않습니다.

`z0_ohm`, `delay_s`는 양의 유한 스칼라입니다. `source_resistance`는 유한한
비음수 저항이며 0은 이상 전압원입니다. `load_resistance`도 유한한 비음수
저항이며 0은 단락, **None은 개방**입니다. 무한대는 거부합니다. 반사 계수가
1로 반올림되는 극단적인 경우도 유한 저항을 개방으로 바꾸지 않습니다.

`voltage`, `current`는 `(시각 수,2)` 형상의 소스/부하 순서 V와 A입니다.
**양쪽 전류 모두 선로 안으로 향하므로** 부하 전달 전력은
`-voltage[:,1]*current[:,1]`입니다. `forward_voltage`, `backward_voltage`는
같은 두 평면의 오른쪽/왼쪽 진행 전압파이며 `drive_voltage`는 출력 시각의
이상 소스 전압입니다. 배열은 복사된 읽기 전용 값입니다. `to_dict()`는 단위,
원입력, 항 수를 포함하는 독립적인 유한 JSON 호환 자료를 반환합니다. 이는
결과 기록이며 버전 저장 입력 스키마가 아닙니다. 공통 실행과 앱 폼은 별도입니다.

명시적으로 무손실이며 주파수와 무관한 스칼라 L', C', 길이 ell이면
`Z0=sqrt(L'/C')`, `delay=ell*sqrt(L'*C')`로 정할 수 있습니다. R=G=0이
전제이며 임의 추출 선로의 손실이나 분산을 자동 제거하지 않습니다.

## 유한 지연 합과 예산

`gs=(Rs-Z0)/(Rs+Z0)`, `gl=(Rl-Z0)/(Rl+Z0)`(개방은 1),
`k=Z0/(Rs+Z0)`, `tau=delay`일 때 소스 출사파는
`a(t)=k*sum((gs*gl)**n * Vs(t-2*n*tau))`입니다. 소스 귀환파는
`b(t)=gl*a(t-2*tau)`, 부하 입사파는 `a(t-tau)`입니다.

입력 이전 이력이 0이므로 유한 시간의 합은 유한합니다. `gs*gl=+1` 또는
`-1`인 비감쇠 이상 소스에도 적용하며 무한 꼬리를 근사하지 않습니다. 정규화한
저항 합의 경계식으로 포트 전압/전류를 직접 계산하여 `1-gl`이나 거의 같은
진행파의 차에서 작은 유한 부하 전류가 사라지는 문제를 피합니다.

`max_terms`는 1..10000 정수이며 파형 계산 전에 검사합니다. `terms`는 값이
0인 입력 기여도 포함하는 **도달 가능한 전방 왕복 항** 수입니다. 시각 수,
양쪽 모든 파의 수, CPU/메모리 보장이 아닙니다. 왕복 계수가 정확히 0이면
전방 항은 최대 하나지만 귀환파는 유지합니다. 첫 입력 이전이면 항 수가 0일
수 있습니다. 예산 초과는 오류이며 시간을 줄이거나 늦은 항을 버리지 않습니다.

이동된 입력 knot는 부동소수점 시간 해상도에서 유한하고 구별되어야 합니다.
구별할 수 없는 knot나 비유한 출력은 거부합니다. 파두는 표현된 이동 knot에서
오른쪽 연속 규약을 따릅니다.

## 수락과 범위

집중 검사는 정합/개방/단락의 첫 도달과 귀환, 저항 정상 한계, 양쪽 경계식,
펄스 이전 이력, 중첩, 시간/임피던스 스케일, 비감쇠 합, 예산, 입력 거부와
복사를 확인합니다. 극단적인 유한 저항에서도 전류와 경계식을 보존합니다.
포트 전력 적분은 정합/개방/단락 step의 최종 전기/자기 에너지와 일치하며
소스 전력은 소스 저항 손실과 선로 입력 전력의 합과 일치합니다.

독립 SciPy 1.18.1 DOP853은 직렬 인덕터와 노드 커패시터 회로를 적분하며
양 끝에 절반 커패시터를 둡니다. Z0=50옴, 지연 1 ns, Rs=25옴, Rl=100옴,
초기 에너지 0, 0..2 ns에 1 V까지 상승하는 입력을 맞췄습니다. 0..12 ns의
1201개 샘플에서 32/64/128 셀 최대 소스/부하 오차는
0.006821/0.004185/0.002662 V입니다. 128 셀 한계는 0.02 V이며 두 세분에서
오차가 감소해야 합니다. ODE rtol/atol은 1e-10/1e-12, 최대 간격은
`.2*delay/cells`입니다. 이 공간 회로는 별도 수렴 기준이며 시험에서만 사용하고
새 의존성을 추가하지 않습니다. 기존 네트워크/종단/주기 회귀는 원래 기준을
유지합니다.

리액티브/비선형 종단, 손실, 분산, 결합 선로, 임의 실측 주파수 자료의 복원과
일반 TDR/eye/BER 해석은 범위 밖입니다. 실제 기판 기하·재료나 계측기 검증이
아닙니다. 브라우저/Windows 지원에는 별도 연결 및 정확 빌드 검증이 필요합니다.

[주기 응답](periodic.md) · [네트워크](network.md) ·
[English](../../../../../packages/sipi/startup.md)
