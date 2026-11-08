# 결합 수동 Debye 시작 응답

`coupled_debye_rlgc_ladder_response`는 초기 상태가 0인 명시적 두 신호 회로를
계산합니다. 상수 실수 대칭 2×2 R/L/G/C_inf와 1–2개 행렬 Debye 강도를
사용합니다.

C*(f) = C_inf + sum(delta_C[k] / (1 + j f / relaxation_hz[k])).

R [ohm/m]과 G [S/m]는 양의 준정부호, L [H/m]과 C_inf [F/m]는 정규화한
고유값 비율이 1e-12보다 큰 양의 정부호여야 합니다. 각 강도 [F/m]는
정확히 0인 행렬 또는 같은 조건의 양의 정부호입니다. 행렬은 정확히
대칭이어야 하며 일반 특이·계수 1 강도와 음의 고유값은 보정 없이
거부합니다. R/G의 계수 부족은 허용합니다. 극점 순서와 0 선언을 보존합니다.

```python
import numpy as np
from sipi import coupled_debye_rlgc_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.minimum(t/2e-9, 1.)[:, None]*[1., -.4]
a = coupled_debye_rlgc_ladder_response(t, drive,
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]], [[50., -10.], [-10., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
assert a.voltage.shape == (121, 4)
assert a.polarization_charge.shape == (121, 17, 2, 2)
assert a.total_power_balance_relative_error <= 1e-10
assert np.min(a.total_energy) >= 0.
```

소스·부하 저항 벡터는 각각 유한한 양수 ohm 값 2개입니다. 시간은 0부터
시작하는 균일 표본 2–10000개이며 소스 전압은 (시간,2) 형상과 첫 행 0을
요구합니다. SciPy lsim이 직선 보간 입력을 전파합니다. 셀 1–128개와 극점
1–2개 제한은 자원 상한이며 정확도나 실행 시간을 보장하지 않습니다.
극점·시간·셀을 자동 추정하지 않습니다.

포트 순서는 near_0,near_1,far_0,far_1입니다. 포트 전류는 모두 선로 내부
방향이고 구간 전류는 원단 방향입니다. 노드·구간 배열의 마지막 축은 신호
2개입니다. 분극 전압·전하·전류 배열은 (시간,노드,선언 극점,신호)이며
단위는 V/C/A입니다. 전하·전류는 집중 노드 정전용량과 양끝 절반 가중치를
포함합니다. 교차 항 때문에 개별 전하는 음수일 수 있고, 수동성은 전체
이차형식 에너지로 판단합니다.

활성 극점마다 tau*w'=V-w, tau=1/(2 pi relaxation_hz)입니다.
`energy`/`energy_rate`는 순간 C_inf/L 저장 항만 포함하고,
`polarization_energy`/`polarization_energy_rate`는 sum(wᵀ C_pole w)/2와
변화율을 포함합니다. `relaxation_loss`는
sum((V-w)ᵀ C_pole (V-w)/tau)입니다. total 속성은 두 저장 항을 합칩니다.
에너지는 J, 변화율·손실은 W이며 전체 선로·두 신호를 합한 값입니다.
에너지나 반환 전력을 잘라내지 않습니다. 선로 포트 및 소스 공급 전력의
상대 잔차 기준은 각각 1e-10이며 양종단 저항 손실도 포함합니다.
계수·상태·진단은 유한해야 하고 전파된 첫 상태는 0이어야 합니다.

`CoupledDebyeRLGCLadderResponse`는 단일 신호 클래스와 별개이며 기존
단일 신호 파동·저장 어댑터에 암묵적으로 들어가지 않습니다. 배열은 복사된
읽기 전용이고 입력 사전은 별도 복사본입니다. `to_dict()`는 포트·에너지를,
`to_dict(include_states=True)`는 내부 배열도 반환합니다. 이 결과는 실행
가능한 저장 요청이 아닙니다.

## 독립 검증과 제한

분리된 두 선로와 교환 대칭 공통/차동 모드는 단일 신호 Debye 2개와
1e-10 V/1e-12 A 이내로 일치합니다. 강도 0은 기존 상수 결합 RLGC 응답과
일치합니다. 비가환 행렬의 독립 전하 상태 노드 KCL·DOP853 계산은
1e-8 V/1e-9 A 이내로 일치하며 후보의 조립 질량·강성 행렬을 사용하지 않습니다.

예제의 교환 대칭 행렬과 [1,-.4] 사인 입력에서 연속 모드별 scikit-rf
ABCD 대비 32/64/128셀의 오차는 다음과 같습니다.

| 주파수 / 명시 시간 설정 | 최대 단자 전압 오차 |
|---|---|
| 100 MHz, 8주기, 주기당 1024표본 | 22.6771 / 5.30428 / 1.83043 microvolt |
| 500 MHz, 20주기, 주기당 256표본 | 1.49727 / .377406 / .100628 mV |
| 1 GHz, 20주기, 주기당 256표본 | 5.74077 / 1.43556 / .362797 mV |

모두 감소하며 128셀에서 1 mV 이하입니다. 100 MHz/128셀에서 주기당
256/512/1024표본으로 늘리면 독립 유한 pi 모드 주파수해 대비 오차는
39.9698/9.92406/2.48102 microvolt로 감소합니다. 7/8/9주기 phasor 차이는
1e-8 V 이내입니다. 이는 명시된 사례의 검증이며 일반 정확도 상한이 아닙니다.
펄스·0 입력·준정부호 R/G·극점/신호 순열·배율·복사/읽기 전용·엄격한
행렬 입력·수치 실패 검사를 함께 사용합니다.

이상·개방·단락·전류원·리액티브 외부 종단, 일반 준정부호 강도,
자동 기하·재료 추출, 도체 주파수 의존성, 임의 맞춤, TDR 해석 및 실측
기판 정확도는 범위 밖입니다. 웹·Windows 연결은 별도입니다. [단자 파동 어댑터](startup_waves.md)는 이 응답을 명시적으로 받으며 저장 파동 v1..4는 그대로입니다. 기존 NumPy/SciPy와 시험 전용 scikit-rf 버전·라이선스를
유지하며 새 의존성은 없습니다.

[단일 신호 Debye](debye_startup.md) · [상수 결합 RLGC](coupled_startup.md) ·
[English](../../../../../packages/sipi/coupled_debye_startup.md)

[입력 저장](coupled_debye_startup_document.md)은 별도의 실행 가능한 요청입니다.
