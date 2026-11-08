# 다신호 Debye 외부 커패시터 시작 응답

[English](../../../../../packages/sipi/multiconductor_debye_capacitive_startup.md) | **한국어**

`psd_multiconductor_debye_capacitive_ladder_response`는3·4신호 영 초기 상태
유한 회로에서 부하 저항에 병렬 연결된 수동 커패시터를 모델링합니다.
별도 `MulticonductorDebyeCapacitiveLadderResponse`를 반환하며
[PSD Debye 선로 계약](psd_multiconductor_debye_startup.md)을 유지합니다.

```python
import numpy as np
from sipi import psd_multiconductor_debye_capacitive_ladder_response
t=np.linspace(0.,4e-9,41)
r=psd_multiconductor_debye_capacitive_ladder_response(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12)
assert r.voltage.shape==r.current.shape==(41,6)
assert r.load_capacitor_current.shape==(41,3)
assert not np.any(r.polarization_voltage[:,:,1])
assert not np.any(r.load_capacitor_current[:,1])
```

`load_capacitance`는 단위 F의 실수·정확 대칭 N×N PSD 행렬이며0과 rank-one도
수락합니다. 대칭 복구·고유값 클리핑·rank 임계값을 사용하지 않습니다.
특이점 근처 수치 부호 모호성을 포함해 계산한 정규화 고유값이 하나라도 음수면
거부하므로 수학적 PSD의 모든 부동소수점 표현을 수락하지는 않습니다.
작지만 양인 대각 정전용량은0으로 바꾸지 않습니다. R[ohm/m]·G[S/m]·1–2개의
DeltaC[F/m]는 PSD, L[H/m]·C_inf[F/m]는 정규화 고유값 비율>1e-12의 SPD이며
완화 주파수는 양의 Hz입니다.

명시 signals3/4, cells1–64, 양의 길이[m],0에서 시작하는 균일 시간2–10000행을
요구합니다. drive(time,N)의 첫 행은0이고 소스/부하 저항은 각각 N개의 양의
유한 ohm 값입니다. 개수 상한은 자원 제한이며 정확도/실행 시간 보장이 아닙니다.
스칼라 확장이나 ideal/open/short/전류/인덕터 종단을 추론하지 않습니다.
기존2신호 및 저항 종단 다신호 경로의 연산과 전체 상태 출력 해시를 유지합니다.

far 노드 질량은 `dx/2*C_inf+Cload`이며 들어오는 선분 전류에서 저항·병렬·분극
전류를 빼 도함수를 계산합니다. 선로 안으로 향하는 단자 전류는
`I_far=-Vfar/Rload-Cload*dVfar/dt`입니다. 부하 저항 손실은
`sum(Vfar**2/Rload)`이며 커패시터 전류가 포함된 전체 단자 전류를 I²R에 넣으면
안 됩니다. 외부 커패시터는 보조 상태를 추가하지 않습니다. 내부 Debye 전압의
`tau*w'=V-w`, DeltaC 역행렬 미사용, pole 순서, 정확0 강도 열을 유지합니다.

```python
far=r.voltage[:,3:]
np.testing.assert_allclose(r.current[:,3:],-far/100-r.load_capacitor_current,
                           rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,r.line_energy+r.load_capacitor_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_resistor_loss-r.load_resistor_loss
    -r.series_loss-r.shunt_loss-r.relaxation_loss,rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.load_capacitor_energy.flags.writeable
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-capacitive-startup'
```

`line_energy/rate`는 순간·분극 저장만, `total_energy/rate`는 외부
`.5*Vfar.T*Cload*Vfar`와 전력까지 포함합니다. load_capacitor_current는(time,N),
부하 에너지/전력은(time,)입니다. 단자 순서는 near N개 다음 far N개이며 양쪽
전류가 선로 안으로 향합니다. 배열은 독립 읽기 전용이며 전체 노드/분극 상태는
`to_dict(include_states=True)`에 포함됩니다. 선로/소스 수지의 상대1e-10 기준,
유한·비음수 저장/손실, 클리핑 금지를 유지합니다. 방전 중 부하 전력은 음수일 수
있습니다.

독립 수락은2+1/2+2 블록 회로 및 외부C=0 한계를 절대 V1e-10/I1e-12로 대조합니다.
1개 활성 채널은 기존2신호 API에 비결합·미구동 dummy를 추가한 것이며 별도 scalar
API가 아닙니다. 비가환 전하 상태 node KCL DOP853 기준은 V1e-8/I1e-9입니다.
PWL lumpedRC 해석 한계는 길이.01/.001/.0001m 오차 감소와 최종<=1e-3V를 요구합니다.
scikit-rf2.2.0 독립 modal ABCD의 `Yload=1/R+jωCload`는100/500MHz에서16/32/64cell
오차 감소·최종<=1e-3V를 요구합니다. 별도128/256/512샘플·8/9/10주기 검사는
PWL/정착 오차를 확인하며 horizon 차<=1e-8V입니다. 지정 fixture 기준이며 임의
대역·실측 보드 정확도 보장이 아닙니다.

0/rank-one/근영 부하·pole 열·신호/pole 순열·선형/시간/임피던스 스케일·전류/저장
분리·복사·유한성·원래 예외를 검사합니다. 별도 결과형은 아직 저장/파동 API에
연결하지 않습니다. 장 추출·임의 종단·분산 피팅·FFT/TDR·플랫폼·실측 정확도를
추가하지 않습니다. 기존 의존성과 고지를 유지하며 새 의존성은 없습니다.
[2신호 커패시터 계약](debye_capacitive_startup.md)을 참고하세요.
