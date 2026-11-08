# 유한 수동 RLGC 시작 응답 회로

`rlgc_ladder_response`는 초기 에너지가 없는 균일한 단일 RLGC **유한 회로**를
명시적 셀 수와 구간별 선형 입력으로 전파합니다. 기존 SciPy 상태공간 전파기를
사용합니다. 정확한 연속 분포 선로 해나 Maxwell FDTD 솔버를 뜻하지 않습니다.

```python
import numpy as np
from sipi import rlgc_ladder_response

t = np.linspace(0., 12e-9, 1201)
r = rlgc_ladder_response(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C=200e-12, length=.1, cells=128,
    source_resistance=25., load_resistance=100.)
assert r.voltage.shape == (1201, 2)
assert r.node_voltage.shape == (1201, 129)
assert np.all(r.energy >= 0) and r.power_balance_relative_error <= 1e-10
assert not r.voltage.flags.writeable
assert 'node_voltage_v' not in r.to_dict()
assert 'node_voltage_v' in r.to_dict(include_states=True)
```

## 입력과 경계

SI 단위 R [ohm/m], G [S/m]는 비음수, L [H/m], C [F/m], length [m]는 양수인
유한 실수입니다. bool은 거부합니다. `cells`는 명시적 1..256 정수이며 기본값이나
자동 정확도 판정이 없습니다. `time`은 정확히 0에서 시작하는 2..10000개 유한
실수이며 엄격히 증가합니다. 간격은 상대 1e-10, 절대 0 허용 범위에서 균일해야
합니다. `source_voltages`는 같은 형상이며 첫 값은 정확히 0입니다. 표본 사이는
선형, 마지막 이후는 마지막 값으로 유지합니다. 이상 소스의 초기 비영 step은
커패시터 impulse가 필요하므로 이 모델에서 허용하지 않습니다.

소스와 부하 저항은 유한한 비음수입니다. 소스 0은 이상 전압원, 부하 0은 단락,
부하 `None`은 개방입니다. 무한 저항, 초기 저장 에너지, 주파수 표, skin 법칙,
결합 도체, 리액티브/비선형 외부 종단을 추정하지 않습니다.

dx=length/cells일 때 각 구간은 직렬 R*dx, L*dx이고 각 노드는 병렬 G*dx, C*dx이며
양 끝은 절반 값을 가집니다. 이상 소스/단락의 고정 전압 노드는 동적 상태에서
제거하지만 끝 커패시터 에너지와 누설은 유지합니다. 이상 소스 전류에는 첫 구간
전류 외에 C_end*dV/dt + G_end*V를 포함합니다. 입력 knot의 미분은 오른쪽 선형
기울기이고 마지막 표본의 기울기는 0입니다.

## 결과와 에너지 검사

`voltage`, `current`는 소스/부하 순서 `(표본 수,2)` 배열입니다. 양쪽 전류 모두
선로 안을 향하므로 부하 전달 전력은 부하 V*I의 음수입니다. `node_voltage`는
cells+1열, `segment_current`는 cells열이며 전류는 소스에서 부하 방향입니다.
배열은 복사된 읽기 전용 자료이고 `inputs`는 단위를 포함한 독립 사전입니다.
`to_dict()`는 입력, 포트, 에너지/전력을 반환하며 `include_states=True`일 때
내부 노드/구간 위치와 상태도 포함합니다. 결과 기록이며 버전 저장 입력은 아닙니다.

에너지는 sum(C_node*V**2 + L_segment*I**2)/2입니다. `energy_rate`는 표본 에너지의
차분이 아니라 회로 우변으로 계산합니다. `series_loss`, `shunt_loss`, `line_power`,
`source_power`, `source_resistor_loss`, `load_resistor_loss`는 물리 부호를 유지하고
돌아오는 포트 전력을 0으로 자르지 않습니다. E_dot - line_power + series_loss +
shunt_loss 잔차를 E_dot, line_power, 전체 내부 손실 중 가장 큰 시각별 절댓값으로
나눕니다(정확히 0인 결과는 0). 상대 잔차 1e-10 초과나 비유한 계수/상태/진단은
부분 결과 없이 오류입니다. 이 대수적 전력 검사는 공간·시간·소스 수렴을 보장하지
않습니다. 특히 비감쇠 반사와 급한 입력에서 각각 확인해야 합니다. 셀/표본 상한은
실행 시간·메모리·정확도 보장이 아닙니다.

## 독립 기준과 범위

1셀 이상 소스의 RL/단락 및 LC/개방 ramp 해를 독립 해석식과 비교하며 끝 절반
커패시터 전류와 에너지도 포함합니다. 같은 32셀 회로를 별도 DOP853으로 적분한
전압은 상태공간 결과와 1e-8 V 이내입니다. 이는 전파 알고리즘 비교이며 독립적인
두 공간 이산화가 아닙니다. 시간/임피던스 스케일, 0 입력, 개방/단락/정합 경계,
음의 귀환 전력 및 엄격한 입력도 검사합니다.

L=500 nH/m, C=200 pF/m, 길이 .1 m, R=G=0, 0..2 ns에 1 V까지 상승하는 입력,
0..12 ns의 1201표본에서 정확 무손실 지연 해가 연속 선로 기준입니다.
Rs=25옴/Rl=100옴의 32/64/128셀 오차는 .006821/.004185/.002662 V입니다.
6개 저항/이상/개방/단락 조합은 최종 세분에서 .02 V와 .0005 A 이하이며 오차가
감소해야 합니다. **이상 소스/개방은 128셀에서 .022030 V로 .02 V 기준에 실패**했습니다.
실패 기록과 기준을 유지하고 256셀로 세분하면 .013921 V, .000288 A로 수락합니다.
이는 해당 입력의 수렴이며 모든 입력에 대한 256셀 정확도 주장이 아닙니다.

R=20 ohm/m, G=.002 S/m, 나머지 같은 선로와 Rs=25/Rl=100에서 scikit-rf 2.2.0
분포 선로 ABCD를 독립 500 MHz 기준으로 사용합니다. 20주기, 주기당 256표본,
끝 중복점 제외 마지막 4주기의 phasor를 비교합니다. 32/64/128셀 복소 포트 전압
오차 .000803/.000205/.0000644 V가 감소하고 128셀에서 1e-3 V 이하입니다.
입력 보간 오차도 포함합니다. 무손실/유손실 에너지율 잔차는 1e-10 이하이고 저장
에너지는 비음수여야 합니다. SciPy 1.18.1과 시험 전용 scikit-rf 2.2.0의 기존
BSD-3-Clause 사용을 유지하며 새 실행 의존성을 추가하지 않습니다.

상수 단일 RLGC는 임의 재료 분산, skin 효과, 다중모드/결합 선로, 일반 TDR 추론,
eye/BER나 실측 기판 정확도를 의미하지 않습니다. 브라우저/Windows 연결은 별도
검증이 필요합니다.

[정확 무손실 응답](startup.md) · [주기 응답](periodic.md) ·
[English](../../../../../packages/sipi/rlgc_startup.md)
