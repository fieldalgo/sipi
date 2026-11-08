# 다신호 Debye 전류원 단자 파동

[English](../../../../../packages/sipi/multiconductor_debye_norton_startup_waves.md) | **한국어**

`startup_port_waves`는 `NortonMulticonductorDebyeReactiveLadderResponse`를
6·8개의 양의 실수 기준 저항과 함께 명시적으로 수락합니다.
[전류원 회로](multiconductor_debye_norton_startup.md)의 단자 표본을 변환하며
다시 전파하지 않습니다. 명시 대각 기준 벡터는 시간에 대해 일정하고
특성·모드 임피던스를 추론하지 않습니다.

```python
import numpy as np
from sipi import psd_multiconductor_debye_norton_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
drive=.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2]
r=psd_multiconductor_debye_norton_reactive_ladder_response(
    t,drive,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.source_currents.shape==r.load_branch_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='NortonMulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

단자는 near N개 뒤에 far N개이며 양끝 전류는 선로 안으로 향합니다.
near 전류는 주입 전류에서 `Gs*Vnear`를 뺀 값이므로 주입 A로 단자 전류를
대체하지 않습니다. 내부 구간·커패시터·가지 전류도 구분합니다. 원래 변환
`a=(V+Zref*I)/(2*sqrt(Zref))`, `b=(V-Zref*I)/(2*sqrt(Zref))`를 유지하며
단위는 sqrt(W), 각 단자의 `a²-b²`는 `V*I`입니다.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
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

near 단자 전력에는 소스 병렬 손실이 포함되지 않습니다. far 전력은 병렬
저항 손실·커패시터 전력·가지 인덕터 에너지 변화율·가지 저항 손실 합의
음수입니다. 외부 저장이 전력을 돌려줄 수 있어 개별 단자 전력을 항상
음수로 제한하지 않습니다. 합에는 내부 `line_energy_rate`를 사용하며
외부 C/L 저장을 포함한 total 변화율을 넣지 않습니다. 원래 상대1e-10
복원/전력 기준·독립 읽기 전용 출력·표현 불가능한 스케일 거부를 유지합니다.

결합/대각/RG0의 ramp/pulse, 이상/일부 병렬/양수/근영 소스 컨덕턴스,
전체 Debye의 양Gs Thevenin 파동 등가, Debye 강도0의 모드 합성16개를
검사합니다. 모드 합성은 변환과 교환 가능한 균일 Gs0/.02S, 외부 C0/전체,
미구동 dummy 채널을 붙인 기존 상수2신호 Norton reactive 회로를 사용합니다.
존재하지 않는2신호 Norton Debye API를 기준으로 가정하지 않습니다.

6·8단자 합성 phasor는 독립 scikit-rf2.2.0 Z-to-S와1e-10 sqrt(W) 이내로
일치하며 선로 전파가 아닌 변환을 검사합니다. 신호/pole 순열·null 분극·
PSD 근영 강도·외부 C/Rbranch rank·명시 기준·소스/단자 구분·유한/형상
기준을 검사합니다. 수정 전23종×2drive×2기준의 파동 출력92개는
소스/설치본에서 정확한 해시를 보존합니다.

명시 결과형 수락만 바꾸며 파동 수식·물리 엔진은 그대로입니다. 엔진의
저손실 PWL/짧은 관측 실패와 수락한 추가 감쇠 연속 선로 범위도 유지합니다.
임의 과도 정확도·FFT/TDR·고유 모드 추출·새 의존성은 추가하지 않습니다.
엄격한 [전류원 입력 저장](multiconductor_debye_norton_startup_document.md)은
가능하지만 파동 문서1–13버전은 새 종류를 거부합니다. 라이브러리 등록은
87스키마·37템플릿이며 브라우저/데스크톱 배포는 바꾸지 않습니다.
[시작 응답 전력 파동](startup_waves.md)을 참고하세요.
