# 다신호 Debye 직렬 RL 단자 파동

[English](../../../../../packages/sipi/multiconductor_debye_reactive_startup_waves.md) | **한국어**

`startup_port_waves`는 `MulticonductorDebyeReactiveLadderResponse`를
6·8개의 양의 실수 기준 저항과 함께 명시적으로 수락합니다.
[3·4신호 reactive 회로](multiconductor_debye_reactive_startup.md)의 단자 샘플을
그대로 쓰고 다시 전파하지 않습니다. 기준 저항은 시간에 대해 일정한 명시
대각 벡터이며 특성/모드 임피던스를 추론하지 않습니다.

```python
import numpy as np
from sipi import psd_multiconductor_debye_reactive_ladder_response
t=np.linspace(0.,4e-9,41)
r=psd_multiconductor_debye_reactive_ladder_response(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.load_branch_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MulticonductorDebyeReactiveLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

단자 순서는 near N개 뒤에 far N개입니다. 전류는 양끝 모두 선로 안으로
향하며 branch 전류·소스 drive·내부 구간 전류로 대체할 수 없습니다.
원래 변환식 `a=(V+Zref*I)/(2*sqrt(Zref))`,
`b=(V-Zref*I)/(2*sqrt(Zref))`를 유지합니다. 단위는 sqrt(W)이며
각 단자에서 `a²-b²=V*I`입니다.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.incident**2-w.reflected**2,r.voltage*r.current,rtol=1e-10,atol=1e-12)
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

near 전력은 소스 전력에서 소스 저항 손실을 뺀 값입니다. far 전력은 병렬
저항 손실·커패시터 전력·branch 인덕터 에너지 변화율·branch 저항 손실
합의 음수입니다. 외부 저장이 전력을 돌려줄 수 있으므로 개별 far 단자
전력을 항상 음수로 제한하지 않습니다. 단자 전력 합에는 내부
`line_energy_rate`를 사용하며 외부 C/L을 포함한 total 변화율을 대입하지
않습니다. 원래 상대 1e-10 복원/전력 기준을 유지하고 출력 배열은 독립 복사·
읽기 전용이며 표현할 수 없는 스케일은 실패합니다.

결합/대각/RG0 × ramp/pulse 12개와 외부 C가 0/전체인 모드 합성 8개를
검사합니다. 각 활성 모드에는 기존 2신호 PSD reactive 회로와 비결합·미구동
dummy 채널을 사용합니다. 6·8단자 합성 phasor는 독립 scikit-rf2.2.0
Z-to-S와 절대 1e-10 sqrt(W)로 비교합니다. 이는 파동 변환 검증이며 새로운
선로 전파 기준이 아닙니다. 신호/pole 순열·null-only 분극·0/근영 강도·
rank-one/근영 C·0/rank-one/근영 branch 저항·명시 기준 저항·기존 결과형
거부·유한 범위를 검사합니다. 수정 전 21종 × 2drive × 2기준 저항의
파동 출력 84개는 소스/설치본에서 정확한 해시를 보존합니다.

물리 엔진은 바꾸지 않습니다. 원래 8주기 정착 실패와 별도 긴 관측시간 수락
범위도 유지합니다. 임의 transient 정확도·FFT/TDR·전파 솔버·런타임 의존성을
추가하지 않습니다. [물리 입력 저장](multiconductor_debye_reactive_startup_document.md)은
가능하며 [명시 저장 파동 버전13](startup_waves_document_v13.md)이 이 종류를
수락합니다. 기존 v1–12는 계속 거부합니다. 이 추가 시점
85스키마·37template을 유지하며 앱·플랫폼 연결은 별도입니다.
[시작응답 파동](startup_waves.md)을 참고하세요.
