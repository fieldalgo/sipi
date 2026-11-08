# 다신호 혼합 종단 단자 파동

[English](../../../../../packages/sipi/multiconductor_boundary_startup_waves.md) | **한국어**

`startup_port_waves`는 `MixedBoundaryMulticonductorRLGCLadderResponse`를
6·8개의 양의 실수 기준 저항과 함께 명시적으로 수락합니다.
[상수 혼합 종단 회로](multiconductor_boundary_startup.md)의 단자 V/I 표본을
다시 전파하지 않고 변환합니다. 기준은 일정한 대각 단자 저항이며 특성·모드
임피던스를 추론하지 않습니다.

```python
import numpy as np
from sipi import multiconductor_boundary_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
r=multiconductor_boundary_ladder_response(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
assert r.voltage.shape==r.current.shape==(41,6)
assert r.node_voltage.shape==(41,9,3) and r.segment_current.shape==(41,8,3)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
assert r.current[0,0]!=0.  # A prescribed ramp includes endpoint displacement current.
from sipi import startup_port_waves
w=startup_port_waves(r,z_ref=[35.,45.,55.,65.,75.,85.])
assert w.source_kind=='MixedBoundaryMulticonductorRLGCLadderResponse'
assert w.incident.shape==w.reflected.shape==(41,6)
```

near N개 뒤에 far N개가 오며 양끝 전류는 선로 안으로 향합니다. 원래 수식
`a=(V+Zref*I)/(2*sqrt(Zref))`, `b=(V-Zref*I)/(2*sqrt(Zref))`와 sqrt(W)
단위를 유지합니다. 단자별 `a²-b²=V*I`입니다. 이상 전압원에서도 상호 endpoint C를
포함한 전체 변위 전류를 보존하며 구간 전류로 단자 전류를 대체하지 않습니다.
개방은 I=0·a=b, 단락은 V=0·a=-b이고 둘 다 단자 전력0입니다. 유한 저항으로
종단을 근사하지 않습니다.

```python
root_z=np.sqrt(w.z_ref)
np.testing.assert_allclose(root_z*(w.incident+w.reflected),r.voltage,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose((w.incident-w.reflected)/root_z,r.current,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    r.source_power-r.source_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -r.load_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    r.energy_rate+r.series_loss+r.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(w.incident[:,3],w.reflected[:,3])
np.testing.assert_array_equal(w.incident[:,4],-w.reflected[:,4])
other=startup_port_waves(r,z_ref=2*w.z_ref)
np.testing.assert_array_equal(other.port_power,w.port_power)
assert not w.incident.flags.writeable
assert max(w.voltage_reconstruction_relative_error,w.current_reconstruction_relative_error,
           w.power_balance_relative_error)<=1e-10
```

near 전력에서 소스 저항 손실을 제외하며 far 전력은 부하 저항 손실의 음수입니다.
단자 전력 합은 내부 에너지 변화율과 R/G 손실의 합입니다. 원래 상대1e-10
복원/전력 기준·독립 읽기 전용 출력·유한 범위 거부를 유지합니다. 변환기의
import 하나·문서화된 결과형 목록·명시 결과형 조건 두 곳만 바꾸며 파동 수식과
물리 엔진은 그대로입니다.

결합/대각/무손실 ramp/pulse12개와 Rs0/25·부하0/개방/100·양쪽 신호 수·
2drive의 스칼라 모드 대조24개를 검사합니다.1512개 종단 조합에서 개방/단락
파동 항등식을 확인합니다. 1cell 이상/단락 pure-L ramp 해석해2개는 상호
endpoint 변위 전류를 독립 확인합니다. PSD 근영 손실·신호 순열·기준 불변·
엄격한 형상/종류/유한 기준·재전파 없음도 검사합니다.

독립6·8단자 합성 phasor는 scikit-rf2.2.0 Z-to-S와1e-10 sqrt(W) 이내로
일치합니다. 선로 전파 정확도가 아닌 변환 검사입니다. 이전27종×2drive×2기준의
전체 파동 출력108개는 소스/설치본에서 정확한 해시를 보존합니다. 기존 독립
KCL·명시 공간 수렴 범위는 유지되며 새 field/실측/임의 과도 정확도를 뜻하지 않습니다.

[입력 저장](multiconductor_boundary_startup_document.md)은 지원합니다.
저장 파동 v1–15는 별도 종류를 계속 거부합니다.직접 파동 추가 시점91스키마·37템플릿이었고 기존
브라우저/데스크톱 후보는 그대로입니다. 새 의존성·FFT/TDR·모드 추출은
추가하지 않습니다. [시작 응답 전력 파동](startup_waves.md)을 참고하세요.


[명시 저장 파동 버전16](startup_waves_document_v16.md)은 v1–15를 유지하며 다신호 혼합 종단 입력을 추가합니다. 이 추가로92스키마·37템플릿입니다.
