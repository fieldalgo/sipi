# PSD 강도를 갖는 두 신호 Debye 시작 응답

`psd_coupled_debye_rlgc_ladder_response`는 명시적 유한 회로에서 특이한
양의 준정부호(PSD) 완화 강도를 받습니다. rank-one 강도는 한 전압 조합에만
작용할 수 있습니다. 별도 API·응답 클래스이며 기존 [양의 정부호 API](coupled_debye_startup.md)와
저장 문서의 지원 범위는 유지합니다.

## 물리 계약

모든 행렬은 정확히 대칭인 실수2×2입니다. R/G 및1–2개 DeltaC 강도는 PSD,
L/C_inf는 정규화 고유값 비율이1e-12보다 큰 양의 정부호입니다. 계산된 음의
고유값은 크기에 관계없이 거부하고 대칭 보정·클리핑하지 않습니다. DeltaC의
양의 고유값을0으로 만드는 rank 임계값은 없습니다. 정전용량은
C_inf+sum(DeltaC/(1+j*f/relaxation_hz))이며 단위는 ohm/m,H/m,S/m,F/m,Hz,m입니다.
소스와 부하는 각각 두 개의 유한한 양의 저항입니다. ideal/open/short,
리액티브 종단과 전류 소스는 지원하지 않습니다.

명시적1–128셀·양 끝 절반 션트,0에서 시작하는 균일 시간2–10000개,
첫 행이0인 두 열 소스 전압을 사용합니다. SciPy lsim이 초기 상태0에서
PWL 보간을 전파합니다. 개수 제한은 자원 한계이며 수렴·시간 보장이 아닙니다.
관측 시간을 자동으로 늘리지 않습니다.

## 특이 강도의 역행렬 없는 전파

0이 아닌 각 강도에 대해 tau*w'=V-w, tau=1/(2*pi*relaxation_hz)를 직접
전파하며 DeltaC 역행렬을 계산하지 않습니다. 노드 전하는
weight*dx*DeltaC*w이고 전류는 그 시간 미분입니다. null 방향의 w는 선택한
초기0 저역통과 내부 상태이며 관측 가능한 재료 분극을 뜻하지 않습니다.
그 방향의 전하·에너지·완화 손실은0입니다. 정확히0인 강도는 내부 상태를
생략하고 출력 열을0으로 보존하며 극점 순서·중복은 그대로입니다.

분극 에너지는 .5*weight*dx*w.T*DeltaC*w, 완화 손실은
weight*dx*(V-w).T*DeltaC*(V-w)/tau입니다. 순간 C_inf/L 에너지는 별도입니다.
유한한 비음수 에너지·손실과 선로/소스 전력 상대 오차1e-10을 요구하고
클리핑하지 않습니다. 표현 불가능한 계수·0으로 underflow된 비영 강도,
비유한 전파·초기0 위반을 거부합니다. 기존 SPD 경로는 원래 mass/coupling
연산·입력 검사를 유지하고 전파·진단 코드만 공유합니다.

```python
from sipi import psd_coupled_debye_rlgc_ladder_response
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]],
                      [[50., 50.], [50., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
assert response.voltage.shape == (121, 4)
assert response.polarization_charge.shape == (121, 17, 2, 2)
assert response.power_balance_relative_error <= 1e-10
assert response.total_power_balance_relative_error <= 1e-10
np.testing.assert_allclose(response.line_power,
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
assert response.to_dict()['scope'] == 'finite-passive-two-signal-psd-debye-ladder-startup'
```

## 출력·검증 범위

`PSDCoupledDebyeRLGCLadderResponse`의 배열은 유한한 읽기 전용 복사본입니다.
네 단자는 near_0,near_1,far_0,far_1이고 전류는 선로로 들어가는 방향입니다.
분극 전압·노드 전하·전류는(time,node,pole,conductor) 모양입니다.
JSON 내부 상태는 include_states=True일 때만 포함합니다. 독립된 이 응답은
기존 계약에 암묵적으로 들어가지 않습니다. [단자 파동](startup_waves.md)은 이제 이 응답을 명시적으로 받으며 저장 파동 v1..5는 PSD 저장 입력을 계속 거부합니다.

독립 대각·교환대칭 단일모드, 강도0 기존 RLGC 및 원래 SPD 전체상태 한계를
검사합니다. 비가환 rank-one 전하 KCL을 후보 회로행렬과 별도로 DOP853로
적분하여 단자1e-8V/1e-9A 기준을 적용합니다. 단일모드 기준은1e-10V/1e-12A입니다.
100MHz 유한π 기준에서는 주기당256/512/1024표본의 오차가 감소하고
7/8/9주기 phasor 차가1e-8V 이내입니다. 연속 modal ABCD 기준에서100MHz,
500MHz,1GHz 모두32/64/128셀 오차가 감소하며 마지막은1mV 이내입니다.
100MHz는8주기·주기당1024표본,500MHz/1GHz는20주기·주기당256표본을
사용합니다. 특정 회로의 검증이며 일반적인 셀 선택 규칙은 아닙니다.

rank-one·거의 특이한 행렬·null 전하, 스케일·순열, 엄격한 입력·복사,
수치 실패·원래 전파 예외를 검사합니다. 기존 SPD16사례의 전체 물리/저장/
파동 JSON hash도 그대로 유지합니다. 기존 NumPy/SciPy 및 시험 전용 scikit-rf
버전·라이선스를 재사용하며 새 의존성은 없습니다. 기하·재료 추출, 일반 fitting,
실측 정확도, 웹·Windows 연결을 검증한 것은 아닙니다.

[English](../../../../../packages/sipi/psd_debye_startup.md)

[별도 PSD 저장 입력](psd_debye_startup_document.md)은 특이 행렬과 원래 시간 표본을 보존합니다. 파동 저장은 별도입니다.
