# 실수 기준 임피던스의 시작 응답 포트 파형

`startup_port_waves(response, z_ref=...)`는 기존 시작 응답 단자 V/I 표본을 입사/반사
실수 전력파로 변환합니다. `LosslessLineResponse`와 결합·혼합·용량성·RL 부하를 포함한
`RLGCLadderResponse` 및 별도 `NortonReactiveRLGCLadderResponse`를 받아
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
이번 직접 어댑터는 해당 닫힌 레지스트리를 바꾸지 않습니다.
