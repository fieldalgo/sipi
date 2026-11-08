# 실수 기준 임피던스의 시작 응답 포트 파형

`startup_port_waves(response, z_ref=...)`는 기존 시작 응답 단자 V/I 표본을 입사/반사
실수 전력파로 변환합니다. `LosslessLineResponse`와 결합·혼합·용량성·RL 부하를 포함한
`RLGCLadderResponse` 및 별도 `NortonReactiveRLGCLadderResponse`,
`MixedSourceRLGCLadderResponse`를 받아
복사된 읽기 전용 `StartupPortWaves`를 반환합니다.
전파·FFT·재표본·지연 정렬·주기 연장·누락 DC 추정은 하지 않습니다.

```python
import numpy as np
from sipi import lossless_line_response, startup_port_waves

time = np.linspace(0., 8e-9, 801)
response = lossless_line_response(time,
    source_times=[0., 1e-9], source_voltages=[0., 1.],
    z0_ohm=50., delay_s=1e-9, source_resistance=50., load_resistance=None)
waves = startup_port_waves(response, z_ref=[50., 50.])
assert waves.port_names == ('source', 'load')
assert waves.incident.shape == (801, 2)
assert waves.power_balance_relative_error <= 1e-10
np.testing.assert_allclose(waves.incident[:, 1], waves.reflected[:, 1], atol=1e-12)
np.testing.assert_array_equal(waves.port_power[:, 1], 0.)
# Reference changes preserve V/I and physical port power, not wave amplitudes.
changed = startup_port_waves(response, z_ref=[35., 75.])
np.testing.assert_array_equal(changed.voltage, waves.voltage)
np.testing.assert_array_equal(changed.current, waves.current)
np.testing.assert_array_equal(changed.port_power, waves.port_power)
```

## 명시적 기준과 방향

`z_ref`는 포트마다 유한 양의 실수 저항[ohm]을 하나씩 담는 명시적 벡터입니다.
스칼라 확장·0/음수·bool·복소수·비유한 기준을 거부합니다. 응답의 시간 격자·전압/전류·
포트 이름을 정확히 유지합니다. 원응답에서 유효하다면 불균일 관측 시간과 단일 표본도
허용합니다. 지원 응답은 single-ended 2포트 또는 4포트입니다.

전류가 **선로 안으로** 향할 때 `a=(V/sqrt(Z)+I*sqrt(Z))/2`는 입사파,
`b=(V/sqrt(Z)-I*sqrt(Z))/2`는 반사/출사파이며 단위는 sqrt(W)입니다. 기준이 특성
임피던스와 같으면 scalar 선로의 소스 측 입사/반사는 forward/backward 전압파를
sqrt(Z)로 나눈 값입니다. 원단 포트에서는 방향이 바뀌어 입사는 backward, 출사는
forward입니다. 개방 원단은 두 파가 같아 순전력이 0이고 단락은 반대여서 전압이 0입니다.

상수 실수 대각 기준은 사용자가 선언하는 대수적 선택입니다. 고유모드 임피던스를
추정하거나 결합 전파를 대각화하지 않습니다. 기준 변경은 V/I·단자 전력을 보존하면서
파형 값을 바꿉니다. 일반 TDR 임피던스 역산이나 주파수 의존/인과적 기준을 제공하지
않습니다. 영/작은 신호에서 `b/a`·`V/I`·반사 gating·임계값을 추정하지 않습니다.

## 수치 수락과 출력

V/I를 기준에 맞게 스케일한 뒤 반합/반차를 계산합니다. 복원한 물리 V와 I는 각각
해당 포트의 전체 표본 중 원래 V/I 최댓값으로 정규화해 상대 오차 1e-10 이하를
요구합니다. 원래 열이 0이면 복원도 정확히 0이어야 합니다. 수치 상쇄 때문에 작은
전류/전압을 잃는 경우 조용히 버리지 않고 거부합니다.

`a²-b²=V*I`도 포트별 상대 1e-10을 요구합니다. 정규화 분모는 해당 포트의
`a²+b²`와 `abs(V*I)` 중 전체 표본 최댓값이며 상쇄 근처의 작은 순전력이 아닙니다.
따라서 임의로 작은 순전력의 상대 정확도를 주장하는 기준이 아닙니다. 비유한 중간값/
결과·표현 불가능한 척도는 거부하고 값을 자르지 않습니다. 반환 `port_power`는 음수를
포함한 직접 `V*I`입니다.

응답에는 읽기 전용 `time`, `voltage`, `current`, `z_ref`, `incident`, `reflected`,
`port_power`, 포트 이름·원응답 클래스 이름·세 복원/전력 진단이 있습니다. `to_dict()`는
scope `explicit-real-reference-startup-port-waves`, basis `single-ended`의 유한 SI JSON을
냅니다. 원물리 응답이나 에너지 항을 바꾸지 않습니다.

정합/개방/단락/저항 부하의 지연 반사와 비정합 소스의 유한 반사 급수를 독립 검사합니다.
2/4포트 scikit-rf 전력파 Z-to-S와 별도 V=ZI phasor 해석도 비교합니다. 후자는 수동
임피던스 표본 fixture이며 전파된 선로라고 주장하지 않습니다. 모든 지원 응답 타입·
선로 전력 합·기준 변경·중첩·기준/포트 순열·임피던스 스케일·영/불균일/단일 표본·복사·
엄격 입력·유한 척도/상쇄 실패를 검사합니다. 소스 수렴·선로 정확도·일반 TDR/eye/BER·
브라우저/Windows 연결을 인증하는 진단은 아닙니다.

[무손실 시작 응답](startup.md) · [RL 부하 시작 응답](coupled_reactive_startup.md) ·
[English](../../../../../packages/sipi/startup_waves.md)

[시작 응답 포트 파형 저장](startup_waves_document.md)

## 전류 구동 단자 전력파

[Norton 응답](norton_startup.md)은 4개 단자 포트를 가집니다. 두 주입 전류
`source_currents` 대신 단자 `current`를 사용합니다. 근단 단자 전력은 소스 공급 전력에서
외부 소스 병렬 손실을 뺀 값입니다. 원단의 선로 유입 전력은 병렬 부하 저항 손실·외부
커패시터 전력·분기 인덕터 에너지 변화율·분기 저항 손실 합의 음수입니다.

유한 양의 병렬 저항은 Vs=Iinj*Rsh인 Thevenin 등가를 가집니다. 동일한 선로 V/I는 같은
기준에서 같은 전력파를 주지만 공급 전력과 소스 저항 손실은 다릅니다. 이상 전류원·
단락·혼합 경계는 특이한 소스 변환 없이 직접 처리합니다. `source_kind`는 원래 클래스명
`NortonReactiveRLGCLadderResponse`를 보존합니다.

```python
import numpy as np
from sipi import coupled_norton_reactive_ladder_response

time = np.linspace(0., 12e-9, 121)
current = np.column_stack((.02*np.minimum(time/2e-9, 1.), -.01*np.minimum(time/3e-9, 1.)))
response = coupled_norton_reactive_ladder_response(time, current,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_shunt_resistance=[None, 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.voltage.shape == (121, 4)
np.testing.assert_array_equal(response.current[:, 0], current[:, 0])
assert response.total_power_balance_relative_error <= 1e-10
assert np.all(response.source_shunt_resistor_loss >= 0)
assert 'source_currents_a' in response.inputs and 'source_voltages_v' not in response.inputs
assert not response.to_dict()['states_included']

from sipi import startup_port_waves
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'NortonReactiveRLGCLadderResponse'
assert waves.incident.shape == (121, 4)
np.testing.assert_allclose(waves.port_power[:, :2].sum(axis=1),
    response.source_power - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

ramp/pulse Norton–Thevenin 등가, 6개 혼합 경계, 영/rank-one 외부 항, 영 입력, 기준 변경,
독립 읽기 전용 결과와 주입 전류 형상의 거부를 검사합니다. 기존 복원·전력 기준은 그대로
유지합니다. 저장 startup-port-waves/1 wrapper는 여전히 Norton 입력을 거부합니다.
[저장 version2](startup_waves_document.md)는 version1을 보존하면서 Norton을 명시적으로 추가합니다.

## 혼합 소스 단자 전력파

[전압원·전류원 혼합 시작 응답](mixed_startup.md)을 명시적으로 지원합니다.
`source_values`의 각 열은 V/A 단위가 다를 수 있으므로4개 단자 전압/전류 열을 대신할 수
없습니다. 진단은 단자 표본과 원래 클래스명 `MixedSourceRLGCLadderResponse`를 보존합니다.

근단 파동 전력은 공급 전력에서 전압원 직렬 손실과 전류원 병렬 손실 **둘 다** 뺀 값입니다.
원단의 선로 유입 파동 전력은 외부 커패시터/분기/저항 전력의 음수입니다. 유한 혼합 소스와
Thevenin 등가 회로는 같은 기준에서 같은 단자 파형을 갖지만 공급 전력·개별 소스 손실은
다릅니다. 동종 소스 한계는 기존 전압원/전류원 파동 결과와 같습니다.

```python
import numpy as np
from sipi import coupled_mixed_source_ladder_response

time = np.linspace(0., 12e-9, 121)
sources = [dict(kind='voltage', voltage_v=np.minimum(time/2e-9, 1.),
                series_resistance_ohm=0.),
           dict(kind='current', current_a=-.008*np.minimum(time/3e-9, 1.),
                shunt_resistance_ohm=None)]
response = coupled_mixed_source_ladder_response(time, sources,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=16, load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.source_kinds == ('voltage', 'current')
assert response.source_units == ('V', 'A')
np.testing.assert_array_equal(response.voltage[:, 0], sources[0]['voltage_v'])
np.testing.assert_array_equal(response.current[:, 1], sources[1]['current_a'])
assert response.total_power_balance_relative_error <= 1e-10
assert not response.to_dict()['states_included']
assert np.all(response.source_series_resistor_loss == 0.)
assert np.all(response.source_shunt_resistor_loss == 0.)

from sipi import startup_port_waves
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'MixedSourceRLGCLadderResponse'
assert waves.incident.shape == (121, 4)
np.testing.assert_allclose(waves.port_power[:, :2].sum(axis=1),
    response.source_power - response.source_series_resistor_loss
    - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

혼합6경계·ramp/pulse 등가·동종 한계·영/rank-one 부하·영 입력·기준 변경·읽기 전용
복사와2열 혼합 입력의 거부를 검사합니다. 복원/전력 기준과 전파는 바뀌지 않습니다.
저장 startup-port-waves version1/2는 혼합 입력 스키마를 여전히 거부하며 저장 계약 확장은
[저장 version3](startup_waves_document.md)에서 명시적으로 지원합니다.

## 명시적 Debye 단자 파동

`DebyeRLGCLadderResponse`도 명시적으로 수락합니다. 두 단자 전압과 선로
안으로 들어가는 전류를 사용하며 내부 분극 전류로 단자 전류를 대신할 수
없습니다. 기존 재구성·전력 기준을 그대로 적용합니다. 근단 파동 전력은
소스 공급 전력에서 소스 저항 손실을 뺀 값이고, 원단은 부하 저항 손실의
음수입니다. 합계는 순간·분극 에너지 변화율과 직렬·누설·완화 손실의
합입니다. 기준 임피던스를 바꿔도 단자 전력은 보존합니다.

```python
from sipi import debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = debye_rlgc_ladder_response(time, np.minimum(time/2e-9, 1.),
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=16, source_resistance=25., load_resistance=100.)
waves = startup_port_waves(response, z_ref=[35., 75.])
assert waves.source_kind == 'DebyeRLGCLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

6종 경계의 ramp/pulse, 독립 1셀 완화·인덕터 해석 파동, 강도 0의 상수
RLGC 한계, 4극점 분할, 0 입력, 복사, 엄격한 기준값 및 내부 배열 거부를
시험합니다. 분산 고유모드나 TDR 역해석이 아니라 단자 분해입니다.
저장 파동 스키마 v1/v2/v3는 여전히 Debye 입력 문서를 거부합니다.
[Debye 물리 입력](debye_startup.md)과 [저장 입력](debye_startup_document.md)의
명시적 시간·셀·극점 계약은 유지합니다.

[명시적 저장 버전4](startup_waves_document.md)는 Debye 입력을 포함합니다.

## 명시적인 두 신호 Debye 단자 파동

[결합 Debye 시작 응답](coupled_debye_startup.md)의
`CoupledDebyeRLGCLadderResponse`를 명시적으로 받습니다. near_0, near_1,
far_0, far_1 순서의 네 단자 V/I를 사용하며, 두 소스 전압이나 4차원 내부
분극 전류를 단자 전류로 쓰지 않습니다. 네 개의 유한한 양의 실수 기준
임피던스가 필요하며 기존 복원·전력 오차 기준은 그대로입니다.
근단 두 파동 전력의 합은 소스 전력에서 소스 저항 손실을 뺀 값이고,
원단 합은 부하 저항 손실의 음수입니다. 전체 합에는 순간·분극 에너지
변화율과 R/G/완화 손실이 모두 포함됩니다. 기준 임피던스를 바꾸면
파동 값은 달라져도 단자 전력은 같습니다.

```python
from sipi import coupled_debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'CoupledDebyeRLGCLadderResponse'
assert waves.port_names == ('near_0', 'near_1', 'far_0', 'far_1')
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

대각·교환대칭 행렬의 독립 단일신호 모드, 비가환 행렬, ramp/pulse,
강도 0의 기존 결합 모델 한계, 극·도체 순열, 입력 0, 복사·엄격한 기준
입력을 검사합니다. 분산 고유모드나 TDR 임피던스를 추정하지 않습니다.
저장 파동 v1..4는 여전히 [결합 Debye 문서](coupled_debye_startup_document.md)를
거부하며 버전을 자동으로 올리지 않습니다.

[명시적 저장 버전5](startup_waves_document.md)가 결합 Debye 입력을 추가합니다.

## PSD 강도의 명시적 네 단자 파동

[PSD Debye 응답](psd_debye_startup.md)도 `PSDCoupledDebyeRLGCLadderResponse`로
명시적으로 받습니다. near_0,near_1,far_0,far_1의 단자 V/I와 네 개의 양의
실수 기준 임피던스를 사용하며 원래 복원·전력 기준은 유지합니다. 두 소스
전압이나 내부 분극 전류로 단자 전류를 대체하지 않습니다. null 방향의
내부 필터 전압을 별도의 파동·손실로 해석하지 않습니다.

근단 합은 source_power−source_resistor_loss, 원단 합은 −load_resistor_loss이며
전체는 total_energy_rate+series_loss+shunt_loss+relaxation_loss입니다.

```python
from sipi import psd_coupled_debye_rlgc_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_rlgc_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'PSDCoupledDebyeRLGCLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
```

rank-one 대각·교환대칭 단일모드, 비가환 강도·ramp/pulse, 강도0 및 원래
SPD 파동 한계, null 방향의 기존 상수 선로 한계, 거의 특이한 강도,
극/도체 순열·복사·엄격한 기준·잘못된 내부배열 대입 거부를 검사합니다.
저장 파동 v1..5는 여전히 PSD 저장 입력을 거부합니다. 이 연결은 일반
분산 고유모드·TDR 역산·실측 정확도나 웹·Windows 수락을 뜻하지 않습니다.

[명시적 저장 버전6](startup_waves_document.md)이 PSD Debye 입력을 추가합니다.

## 외부 정전용량을 포함한 명시 4단자 파동

[외부 부하 C Debye 응답](debye_capacitive_startup.md)의
`DebyeCapacitiveLadderResponse`를 명시적으로 받습니다. 4단자 전압과 선로로
들어가는 전류, 4개의 양의 실수 기준 저항을 사용하며 기존 계산·오차 기준은
그대로입니다. 입력 전압·분극 전류·외부 커패시터 전류를 단자 전류로 대체하지 않습니다.

near 전력은 source_power-source_resistor_loss, far 전력은
-load_resistor_loss-load_capacitor_power입니다. 전체 단자 전력은
line_energy_rate+series_loss+shunt_loss+relaxation_loss이며 외부 저장까지
포함하는 total_energy_rate와 구분합니다. 커패시터 전력은 충·방전에서
양수/음수일 수 있지만 에너지와 저항 손실은 음수가 아닙니다.

```python
from sipi import psd_coupled_debye_capacitive_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_capacitive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12)
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'DebyeCapacitiveLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.line_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(waves.port_power[:, 2:].sum(axis=1),
    -response.load_resistor_loss-response.load_capacitor_power, rtol=1e-10, atol=1e-12)
```

CL0에서 독립 단일 신호 모드·기존 PSD 파동, 강도0에서 기존 상수 C 부하
파동, 비가환 행렬/ramp/pulse, 0/rank-one/full C 부하·null/거의 특이 강도·
순열·기준 전력·복사·내부 배열 거부를 검사합니다. 저장 파동 v1–6은
[외부 C 저장](debye_capacitive_startup_document.md)을 계속 거부합니다.
이 연결은 분산 고유모드/TDR 추론, 실측 정확도나 웹·Windows 통합을 뜻하지 않습니다.

[명시적 저장 버전7](startup_waves_document.md)이 외부 정전용량 Debye 입력을 추가합니다.

## 외부 정전용량·직렬 RL 부하의 명시 4단자 파동

[외부 부하 C Debye 응답](debye_reactive_startup.md)의
`DebyeReactiveLadderResponse`를 명시적으로 받습니다. 4단자 전압과 선로로
들어가는 전류, 4개의 양의 실수 기준 저항을 사용하며 기존 계산·오차 기준은
그대로입니다. 입력 전압·분극 전류·외부 커패시터·가지 전류를 단자 전류로 대체하지 않습니다.

near 전력은 source_power-source_resistor_loss, far 전력은
-load_resistor_loss-load_capacitor_power-load_branch_energy_rate-load_branch_resistor_loss입니다. 전체 단자 전력은
line_energy_rate+series_loss+shunt_loss+relaxation_loss이며 외부 저장까지
포함하는 total_energy_rate와 구분합니다. 커패시터 전력은 충·방전에서
양수/음수일 수 있지만 에너지와 저항 손실은 음수가 아닙니다.

```python
from sipi import psd_coupled_debye_reactive_ladder_response, startup_port_waves
import numpy as np

time = np.linspace(0., 12e-9, 121)
response = psd_coupled_debye_reactive_ladder_response(time,
    np.minimum(time/2e-9, 1.)[:, None]*[1., -.4],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12,
    load_branch_resistance=[[150., 20.], [20., 150.]],
    load_branch_inductance=np.array([[200., 30.], [30., 200.]])*1e-9)
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65.])
assert waves.source_kind == 'DebyeReactiveLadderResponse'
np.testing.assert_allclose(waves.port_power.sum(axis=1),
    response.line_energy_rate + response.series_loss + response.shunt_loss
    + response.relaxation_loss, rtol=1e-10, atol=1e-12)
np.testing.assert_allclose(waves.port_power[:, 2:].sum(axis=1),
    -response.load_resistor_loss-response.load_capacitor_power
    -response.load_branch_energy_rate-response.load_branch_resistor_loss, rtol=1e-10, atol=1e-12)
```

CL0/큰 가지 L의 독립 단일 신호 모드와 큰 가지 L의 기존 C 부하 파동, 강도0의 기존 상수 RL 부하
파동, 비가환 행렬/ramp/pulse, 0/rank-one/full C 부하·null/거의 특이 강도·
순열·기준 전력·복사·내부 배열 거부를 검사합니다. 저장 파동 v1–7은
[외부 C 저장](debye_reactive_startup_document.md)을 계속 거부합니다.
이 연결은 분산 고유모드/TDR 추론, 실측 정확도나 웹·Windows 통합을 뜻하지 않습니다.

가지 전류는 선로에서 부하로 나갑니다. 가지 단자 전력은 가지 에너지
변화율과 저항 손실의 합이며 병렬 부하 저항 손실과 분리합니다.
0/rank-one/full 가지 저항과 pulse 에너지 방출을 검사합니다. 가지 또는
커패시터 전류만을 선로 단자 전류로 쓰지 않습니다. 전체 회로 에너지는
외부 C와 L 저장을 모두 포함합니다.
