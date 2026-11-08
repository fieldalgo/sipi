# 외부 부하 정전용량을 연결한 PSD Debye 시작 응답

`psd_coupled_debye_capacitive_ladder_response`는 명시적
[PSD Debye 회로](psd_debye_startup.md)에 두 신호의 병렬 외부 커패시터를
연결합니다. 별도 API·응답 클래스이며 기존 저장·파동 입력 계약은 유지합니다.

## 입력과 회로 의미

필수 load_capacitance의 단위는 F이며 정확대칭 실수2×2 PSD 행렬입니다.
0·rank-one을 허용하지만 음의 고유값·비대칭은 보정 없이 거부합니다.
F/m 단위의 선로 C_inf·DeltaC와 다른 외부 집중 부하입니다. 원단 노드 mass에
더하며 선로 양 끝 절반 션트를 유지합니다. 기존 PSD강도1–2개·양의 Hz,
R/G PSD·L/C_inf SPD·1–128셀·0에서 시작하는 균일 시간2–10000개·첫 행0의
PWL 소스 조건을 따릅니다. 소스·부하는 각각 두 유한한 양의 저항입니다.
ideal/open/short·전류 소스·외부 인덕터 가지는 추가하지 않습니다.

원단으로 들어가는 전류는 -Vfar/Rload-Cload*dVfar/dt입니다. 저항 손실은
sum(Vfar**2/Rload)이며 전체 단자 전류에 R을 곱해 제곱하면 무효 전류까지
손실로 잘못 계산합니다. 외부 커패시터 에너지는 .5*Vfar.T*Cload*Vfar,
부호 있는 전력은 Vfar.T*Cload*dVfar/dt입니다. 음의 전력은 저장 에너지의
반환을 의미합니다.

## 선로와 전체 회로 에너지의 구분

energy/energy_rate는 순간 C_inf/L, polarization_energy와 변화율은 내부
Debye 저장입니다. line_energy/line_energy_rate는 이 내부 항들의 합이며,
total_energy/total_energy_rate는 외부 커패시터까지 더합니다. 선로 단자
전력은 line_energy_rate와 series/shunt/relaxation 손실의 합입니다.
소스 전력은 total_energy_rate와 같은 내부 손실 및 소스·부하 저항 손실의
합입니다. 두 균형 모두 상대1e-10을 요구하며 저장·손실은 유한한 비음수여야
합니다. 클리핑 없이 표현 불가능한 계수와 잘못된 전파 상태를 거부합니다.

```python
from sipi import psd_coupled_debye_capacitive_ladder_response
import numpy as np

time = np.linspace(0., 12e-9, 121)
r = psd_coupled_debye_capacitive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12)
assert r.voltage.shape == (121, 4) and r.load_capacitor_current.shape == (121, 2)
np.testing.assert_allclose(r.line_power,
    r.line_energy_rate + r.series_loss + r.shunt_loss + r.relaxation_loss,
    rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.total_energy_rate + r.series_loss + r.shunt_loss + r.relaxation_loss
    + r.source_resistor_loss + r.load_resistor_loss, rtol=1e-10, atol=1e-12)
assert r.power_balance_relative_error <= 1e-10
assert r.total_power_balance_relative_error <= 1e-10
```

DebyeCapacitiveLadderResponse는 원래 네 단자·내부 배열에 읽기 전용 복사본
load_capacitor_current(time,2), load_capacitor_energy와power(time,)를 추가합니다.
JSON scope는 finite-passive-two-signal-psd-debye-capacitive-startup이며 선로·전체
에너지와 외부 부하 진단을 SI 키로 구분합니다. 내부 노드·구간·분극 배열은
include_states=True일 때만 포함합니다. 독립된 이 클래스는 기존 파동·저장
어댑터에 암묵적으로 들어가지 않습니다.

## 검증과 한계

외부C가0이면 기존 PSD 회로, Debye 강도가0이면 같은 유한 저항 경계의
기존 상수 결합 capacitive 회로를 회복합니다. 원단 Cload mass를 따로
구성한 비가환 전하 KCL을 DOP853으로 적분해 단자1e-8V/1e-9A를 검사합니다.
연속 modal ABCD의 부하는 Yload=1/Rload+j*omega*Cload입니다.100MHz/500MHz/
1GHz 모두32/64/128셀에서 오차가 감소하고 마지막은1mV 이내입니다.
100MHz는8주기·주기당1024표본,500MHz/1GHz는20주기·256표본입니다.
100MHz256/512/1024표본의 유한π 오차도 감소하고7/8/9주기 phasor 차는
1e-8V 이내입니다.

0·rank-one·fullPSD 부하, ramp/pulse 방전, null 상태, 스케일·순열,
엄격한 입력·복사·원래 예외를 검사합니다. 기존 SPD/PSD32사례의 전체
물리/저장/파동 JSON hash도 보존합니다. 유한 회로와 특정 입력의 수렴
근거이며 실측 정확도나 일반적인 메시·관측 길이 보장은 아닙니다.
기존 도구 버전·라이선스를 재사용하며 새 의존성·기하/재료 추출·웹/Windows
연결·자동 재표본화를 추가하지 않습니다.

[English](../../../../../packages/sipi/debye_capacitive_startup.md)
