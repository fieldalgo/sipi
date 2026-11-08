# 다신호 Debye 혼합 소스 단자 파동

[English](../../../../../packages/sipi/multiconductor_debye_mixed_startup_waves.md) | **한국어**

`startup_port_waves`는 `MixedSourceMulticonductorDebyeReactiveLadderResponse`를
6·8개의 양의 실수 기준 저항과 함께 명시적으로 수락합니다.
[혼합 소스 회로](multiconductor_debye_mixed_startup.md)의 단자 표본을 변환하며
다시 전파하지 않습니다. 대각 기준 벡터는 시간에 대해 일정하고 특성·모드
임피던스를 추론하지 않습니다. 원래 V/A 소스 표본과 선로 안으로 향하는
단자 전류를 구분합니다.

```python
import numpy as np
from sipi import psd_multiconductor_debye_mixed_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
r=psd_multiconductor_debye_mixed_reactive_ladder_response(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.source_kinds==('current','voltage','current')
assert r.source_units==('A','V','A')
assert r.inputs['sources']==sources
assert r.voltage.shape==r.current.shape==(41,6)
assert r.source_values.shape==(41,3)
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MixedSourceMulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

near N개 뒤에 far N개가 오며 양끝 단자 전류는 선로 안으로 향합니다.
전압원의 near 전류는 `(Vs-Vnear)/Rs`, 전류원은 `Iinj-Gs*Vnear` 암페어입니다.
혼합 단위 `source_values`로 단자 전류를 대체하지 않습니다. 내부 구간·
커패시터·가지 전류도 구분합니다. 원래 변환
`a=(V+Zref*I)/(2*sqrt(Zref))`, `b=(V-Zref*I)/(2*sqrt(Zref))`를 유지하며
단위는 sqrt(W), 각 단자의 `a²-b²`는 `V*I`입니다.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -r.load_resistor_loss-r.load_capacitor_power-r.load_branch_energy_rate-r.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    r.line_energy_rate+r.series_loss+r.shunt_loss+r.relaxation_loss,rtol=1e-10,atol=1e-12)
other=startup_port_waves(r,z_ref=2*w.z_ref)
np.testing.assert_array_equal(other.port_power,w.port_power)
assert not w.incident.flags.writeable
assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,
           w.power_balance_relative_error)<=1e-10
```

near 전력에서 전압원 직렬 손실과 전류원 병렬 손실을 모두 제외합니다.
far 전력은 병렬 저항 손실·커패시터 전력·가지 인덕터 에너지 변화율·가지
저항 손실 합의 음수이며 외부 저장이 전력을 돌려줄 수 있습니다. 합에는
외부 C/L 에너지를 제외한 내부 `line_energy_rate`를 사용합니다. 원래 상대
1e-10 복원/전력 기준·독립 읽기 전용 출력·표현 불가능한 스케일 거부를 유지합니다.

3·4신호의 모든24개 V/I 조합과2개 구동을 양의 컨덕턴스에서 명시 Norton·
Thevenin 단자 파동과 비교합니다. 이상 전류원·일부 병렬·근영 병렬 손실,
소스별 공급/손실 분리, 결합/대각/RG0 ramp/pulse12개와 기준 불변도 검사합니다.
Debye 강도0의 모드 대조8개는 균일 Gs.02S·외부 C0/전체와 기존 상수2신호
Norton 회로의 미구동 dummy를 사용합니다. 등가 주입 암페어만 모드로
변환하며 혼합 V/A 표본을 같은 물리 벡터로 취급하지 않습니다.

독립6·8단자 합성 phasor는 scikit-rf2.2.0 Z-to-S와1e-10 sqrt(W) 이내로
일치합니다. 선로 전파 정확도가 아닌 변환 검사입니다. 신호/pole 순열·
null 분극·PSD 근영 강도·외부 C/Rbranch rank·명시 기준·소스/단자 구분·
유한/형상 기준도 검사합니다. 수정 전25종×2drive×2기준의 파동 출력100개는
소스/설치본에서 정확한 해시를 보존합니다.

명시 결과형 수락만 바꾸며 물리 수식과 파동 계산은 그대로입니다. 원래
저손실/짧은 관측 실패와 수락한 추가 감쇠 PWL 연속선로 범위도 유지합니다.
임의 과도 정확도·FFT/TDR·모드 추출·새 의존성을 주장하지 않습니다.
[혼합 입력 저장](multiconductor_debye_mixed_startup_document.md)은 가능하지만
파동 문서1–14버전은 새 종류를 거부합니다.89스키마·37템플릿과 기존
브라우저/데스크톱 후보는 그대로입니다. [시작 응답 전력 파동](startup_waves.md)을 참고하세요.
