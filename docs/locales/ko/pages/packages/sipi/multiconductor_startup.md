# 3·4신호 상수 RLGC 시작 응답

`multiconductor_rlgc_ladder_response`는 초기 저장 에너지가 0인 유한 균일
회로를 계산합니다. `signals=3` 또는 `4`를 명시하며 행렬로 개수를 추정하지
않습니다. `MulticonductorRLGCLadderResponse`는 기존
[2신호 응답](coupled_startup.md)과 별도 자료형입니다.

상수 실수 대칭 N×N `R`[ohm/m], `L`[H/m], `G`[S/m], `C`[F/m]를
입력합니다. L/C는 양의 정부호, R/G는 양의 정부호 또는 정확히 영행렬이어야
합니다. 영행렬이 아닌 특이 양의 준정부호는 이번 계약에서 제외합니다.
모든 비영행렬의 최소/최대 고유값 비는 1e-12보다 커야 합니다. 대칭화,
고유값 보정·절단, 순위 추정, 스칼라 자동 확장은 하지 않습니다.

`source_resistance`와 `load_resistance`는 각각 N개의 유한 양수 저항[ohm],
`length`는 유한 양수 길이[m]입니다. 정수 `cells=1..128`을 명시하며 양 끝의
병렬 C/G에 반 가중치를 적용합니다. 상태 수는 N*(2*cells+1)입니다.
`time`은 0에서 시작하는 2..10000개의 균일 표본(상대 간격 오차 1e-10 이내),
실수 PWL `source_voltages`는 (시간,N) 모양과 정확히 0인 첫 행을 요구합니다.
이상 전압원·개방·단락·리액티브·전류원 종단을 암묵적으로 만들지 않습니다.

```python
import numpy as np
from sipi import multiconductor_rlgc_ladder_response

time = np.linspace(0., 12e-9, 121)
r = multiconductor_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 23., 26.]), L=np.diag([450., 470., 490.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C=np.diag([210., 220., 230.])*1e-12,
    length=.1, cells=16, source_resistance=[25., 25., 25.],
    load_resistance=[100., 100., 100.])
assert r.voltage.shape == (121, 6)
assert r.port_names == ('near_0', 'near_1', 'near_2', 'far_0', 'far_1', 'far_2')
np.testing.assert_allclose(r.line_power,
    r.energy_rate+r.series_loss+r.shunt_loss, rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.energy_rate+r.series_loss+r.shunt_loss+r.source_resistor_loss+r.load_resistor_loss,
    rtol=1e-10, atol=1e-12)
assert r.to_dict(include_states=True)['states_included']
```

단자 순서는 모든 near 신호 다음 모든 far 신호입니다. 양 끝 단자 전류는
선로 안으로, 내부 구간 전류는 near에서 far로 향합니다. 노드 전압 모양은
(시간,셀+1,N), 구간 전류는 (시간,셀,N), 단자 전압/전류는 (시간,2*N)입니다.
배열은 복사 후 읽기 전용이며 `inputs`는 매번 새 사본을 반환합니다.
`to_dict(include_states=True)`는 내부 상태까지 포함하고 기본값은 생략합니다.
이 결과 직렬화는 버전 있는 저장 입력 계약이 아닙니다. 기존 저장·2/4단자
파동 어댑터에 새 자료형을 암묵적으로 허용하지 않습니다.

에너지와 손실은 모든 신호의 합입니다. 부호 있는 전력 관계는
`line_power = energy_rate + series_loss + shunt_loss`,
`source_power = energy_rate + series_loss + shunt_loss + source_resistor_loss
+ load_resistor_loss`입니다. 선로·전체 전력 상대 잔차 기준은 각각 1e-10이며
규모가 0인 경우를 별도로 처리합니다. 유한 계수·상태·진단량, 비음수 저장
에너지·손실을 검사하고 음의 단자 전력은 보존합니다. 전력 보존만으로
실제 물리 정확도를 주장하지 않습니다.

N=3/4 모두 독립 scalar 및 기존 2+1/2+2 블록 한계(1e-10 V/1e-12 A),
비가환 노드 KCL의 별도 SciPy DOP853 적분(1e-8 V/1e-9 A),
scikit-rf 2.2.0의 연속 scalar 모드 ABCD와 대조합니다. 고정 시험 입력에서
100 MHz·500 MHz·1 GHz의 32/64/128셀 오차가 감소하고 최종 1 mV 이하입니다.
100 MHz의 주기당 256/512/1024 표본은 유한 회로 주파수 기준으로 수렴하며,
7/8/9주기 관측 차이는 1e-8 V 이하입니다. 관측 시간이나 기준을 자동으로
완화하지 않습니다. 임의 입력에 대한 보증이 아니며 펄스·영입력·무손실,
도체 순열, 진폭·시간·임피던스 배율, 복사·엄격 입력·극단 규모·전파 실패도
별도로 검증합니다.

이는 SciPy PWL 상태 공간 계산을 사용하는 유한 상수 RLGC 회로입니다.
장 추출·일반 재료 분산·전자기 full-wave 과도 계산·실측 TDR 추정과 다릅니다.
사용 입력마다 소스·시간·공간 수렴을 확인해야 하며 셀/행 상한은 실행 시간이나
정확도 보증이 아닙니다. 도구 버전과 정확한 설치본 검증은
[개발 문서](../../../../../development.ko.md)를 따릅니다.

[3·4신호 입력 저장](multiconductor_startup_document.md)은 명시 신호 수와 SI 입력·시간 행 예산을 보존합니다.
