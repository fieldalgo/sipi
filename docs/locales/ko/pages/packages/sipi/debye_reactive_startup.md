# 외부 정전용량과 직렬 RL 부하를 포함한 PSD Debye 시작 응답

`psd_coupled_debye_reactive_ladder_response`는 명시적
[PSD Debye 회로](psd_debye_startup.md)에 부하 C와 직렬 RL 가지를 연결합니다.
두 부하 저항에 병렬로 연결되며 별도 `DebyeReactiveLadderResponse`를 반환합니다.
기존 물리·저장·파동 입력 계약은 유지합니다.

외부 입력은 모두 필수인 정확대칭 실수 2×2 행렬입니다.
`load_capacitance` [F]와 `load_branch_resistance` [ohm]는 PSD로 0/rank-one도
허용합니다. `load_branch_inductance` [H]는 고유값 비가1e-12보다 큰 SPD입니다.
가지 생략·스칼라 자동 확장·음의 고유값 수정·rank 클리핑을 하지 않습니다.
인덕턴스0을 저항 가지로 자동 해석하지 않습니다.

원래 선로 조건도 같습니다: R/G PSD, 고유값 비1e-12 초과 L/C_inf SPD,
1–2개 PSD 강도[F/m]와 대응 양의 주파수[Hz], 양의 길이,1–128셀,
0에서 시작하는 균일 시간 표본2–10000개, 첫 행0인 2열 PWL 입력 전압.
소스 및 병렬 부하 저항은 각각 두 개의 유한한 양의 값입니다.
ideal/open/short/current-source 경계를 추가하지 않습니다.

선로에서 부하로 나가는 가지 전류 i는 초기0이며 Lb*di/dt=Vfar-Rb*i입니다.
far 선로로 들어가는 전류는 -Vfar/Rload-Cload*dVfar/dt-i입니다.
병렬 부하 저항 손실은 sum(Vfar**2/Rload), 가지 저항 손실은 i.T*Rb*i로
분리합니다. 내부 순간·분극 저장은 `line_energy`, 외부 C와 가지 L까지
합친 값은 `total_energy`입니다. 변화율도 같은 구분을 유지합니다.
가지 에너지는 .5*i.T*Lb*i, 변화율은 i.T*Lb*di/dt입니다. 저항 손실은
음수가 아니며 저장 변화율은 방전 때 음수일 수 있습니다. 선로 및 전체
소스 전력 수지는 모두 상대1e-10을 통과해야 하고, 유한·비음수 저장/손실
검사를 유지하며 표현 불가능한 값을 클리핑하지 않습니다.

```python
import numpy as np
from sipi import psd_coupled_debye_reactive_ladder_response

time = np.linspace(0., 12e-9, 121)
r = psd_coupled_debye_reactive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]], [[50., 50.], [50., 50.]]])*1e-12,
    relaxation_hz=[1e9, 1e8], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12,
    load_branch_resistance=[[150., 20.], [20., 150.]],
    load_branch_inductance=np.array([[200., 30.], [30., 200.]])*1e-9)
np.testing.assert_allclose(r.line_power,
    r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,
    rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.total_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss
    +r.source_resistor_loss+r.load_resistor_loss+r.load_branch_resistor_loss,
    rtol=1e-10, atol=1e-12)
assert r.load_branch_current.shape == (121, 2)
assert r.to_dict()['scope'] == 'finite-passive-two-signal-psd-debye-reactive-startup'
```

`load_branch_current`는(시간,2), `load_branch_energy`,
`load_branch_energy_rate`, `load_branch_resistor_loss`는(시간,) 형상입니다.
외부 C 진단과 함께 복사된 읽기 전용 배열이며 일반 JSON에 단위와 함께
포함합니다. 내부 노드·구간·분극 배열은 `include_states=True`일 때 포함합니다.
이 독립 응답을 기존 파동·저장 어댑터에 암묵적으로 허용하지 않습니다.

코드 간 비교와 수렴을 구분합니다. 강도0이면 기존 상수 reactive 회로를
재현합니다. 명시적인 대각1e6 H 가지는 지정12ns 입력에서 부하 C 회로에
1e-10 V/1e-12 A 이내로 접근하지만 가지를 제거한 것은 아닙니다.
별도로 작성한 비가환 전하 KCL/DOP853 비교 기준은1e-8 V/1e-9 A입니다.
독립 scikit-rf 연속 모드 ABCD는 부하 어드미턴스
1/R+j*omega*C+1/(Rb+j*omega*Lb)를 사용합니다. 교환 대칭 입력에서
32/64/128셀 오차는100MHz/500MHz/1GHz 모두 감소하고 최종1mV 이내입니다.
100MHz는8주기/주기당1024표본, 고주파는20주기/256표본입니다.
100MHz에서256/512/1024 시간 세분은 유한 pi 주파수 기준으로 수렴하고
7/8/9주기 phasor 차는1e-8 V 이내입니다. 특정 입력의 근거이며 자동
표본수·관측 길이 결정 규칙이 아닙니다.

외부 PSD·가지 SPD 조건, pulse 저장/손실, 크기·시간·임피던스·순열·null,
복사·원래 실패 전달을 검사합니다. 기존 SPD/PSD/부하 C의48개 전체
물리·저장·파동 JSON hash를 보존합니다. 기존 NumPy/SciPy와 test-only
scikit-rf 버전·고지를 재사용하며 새 의존성은 없습니다. 기하·재료 추출,
임의 RLC 구조, Maxwell 시간 솔버, 실측 정확도나 웹·Windows 통합을
검증한 것이 아닙니다.

[부하 C API](debye_capacitive_startup.md) ·
[English](../../../../../packages/sipi/debye_reactive_startup.md)

[외부 RL 입력 저장](debye_reactive_startup_document.md)은 Ω·H·F와 선로의 단위당 길이 입력을 구분합니다.

[단자 파동](startup_waves.md)이 이 응답을 명시 수락하며 내부 선로/외부 C/L 전력을 구분합니다. 저장 파동 v1–7의 입력 종류는 그대로입니다.
