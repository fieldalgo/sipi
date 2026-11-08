# 다신호 Debye 직렬 RL 부하 시작 응답

[English](../../../../../packages/sipi/multiconductor_debye_reactive_startup.md) | **한국어**

`psd_multiconductor_debye_reactive_ladder_response`는 별도
`MulticonductorDebyeReactiveLadderResponse`를 반환합니다.
[3·4신호 PSD Debye 회로](multiconductor_debye_capacitive_startup.md)의 기존 부하
저항·외부 커패시터에 병렬로 명시한 직렬 RL 가지를 연결합니다.

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
```

외부 행렬은 실수·정확 대칭 N×N입니다. Cload[F]와 Rbranch[ohm]는0/rank-one을
포함한 PSD, Lbranch[H]는 정규화 고유값 비율>1e-12인 SPD입니다. 누락된 가지·
대칭 복구·고유값 클리핑·rank 임계값을 추론하지 않습니다. 특이점 근처라도
계산한 PSD 고유값이 음수면 보수적으로 거부하므로 수학적 PSD의 모든 부동소수점
표현을 수락하지는 않습니다. 작지만 양인 원소는 그대로 유지합니다.

원래 선로 R[ohm/m]·G[S/m]·1–2 DeltaC[F/m] PSD, L[H/m]·C_inf[F/m] SPD
비율>1e-12, 양의 완화 주파수[Hz] 계약을 유지합니다. 명시 signals3/4·cells1–64·
양의 길이[m],0에서 시작하는 균일 시간2–10000행,첫 행0인 drive(time,N), 각각
N개의 양의 유한 소스/부하 저항이 필요합니다. 개수 제한은 자원 상한이며 정확도/
실행 시간 보장이 아닙니다. 자동 horizon·스칼라 확장·임의 종단을 추론하지 않습니다.

가지 전류는 far 선로에서 부하로 나가며0에서 시작합니다:
`Lbranch*di/dt=Vfar-Rbranch*i`. far 노드 질량은 `dx/2*C_inf+Cload`이며 유입
전류에서 가지 전류를 추가로 뺍니다. 선로 안으로 향하는 far 단자 전류는
`-Vfar/Rload-Cload*dVfar/dt-i`입니다. 병렬 저항 손실 `sum(Vfar**2/Rload)`와
가지 저항 손실 `i.T*Rbranch*i`는 구분하며 전체 단자 전류를 저항 전류로 쓰지
않습니다. 가지는 N개 상태를 추가하고 Debye 보조 전압의 정규 `tau*w'=V-w`,
pole 순서, 정확0 강도 열은 유지합니다.

```python
far=r.voltage[:,3:]
np.testing.assert_allclose(r.current[:,3:],
    -far/100-r.load_capacitor_current-r.load_branch_current,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_resistor_loss-r.load_resistor_loss
    -r.load_branch_resistor_loss-r.series_loss-r.shunt_loss-r.relaxation_loss,
    rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.load_branch_current.flags.writeable
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-reactive-startup'
```

`line_energy/rate`는 내부 순간·분극 저장만, `total_energy/rate`는 외부
커패시터와 가지 인덕터 저장까지 포함합니다. 가지 에너지는 `.5*i.T*Lbranch*i`,
그 변화율은 `Vfar.T*i`에서 가지 저항 손실을 뺀 값입니다. 가지 전류는(time,N),
에너지/변화율/손실은(time,)입니다. 저장·손실은 유한·비음수여야 하고 방전 중
변화율은 음수일 수 있습니다. 선로·소스 전력의 상대1e-10 기준과 클리핑 금지를
유지합니다. 단자는 near N개 뒤 far N개이며 양단 전류는 선로 안으로 향합니다.
출력은 독립 읽기 전용이고 `to_dict(include_states=True)`가 내부 노드·분극
상태를 포함합니다. 기존2신호와 가지 없는 다신호의 연산·전체 출력은 보존합니다.

독립 대조는 기존2신호 reactive2+1/2+2 회로를 절대 V1e-10/I1e-12로 검사합니다.
1개 활성 채널에는 비결합·미구동 dummy를 추가하며 별도 scalar reactive API로
표현하지 않습니다. 가지 전류 상태를 포함한 비가환 전하 KCL DOP853은
V1e-8/I1e-9·가지 전류1e-9A를 요구합니다. Lbranch×100/1000/10000은 기존
커패시터 모델로 오차 감소·최종<=1e-3V를 요구합니다. Cload·선로R/G·분극 강도0인
길이.01/.001/.0001m는 해석 PWL lumpedRL 한계로 오차 감소·최종<=1e-3V를 요구합니다.

scikit-rf2.2.0 독립 modal ABCD는 `Yload=1/R+jωCload+1/(Rbranch+jωLbranch)`를
사용합니다.100/500MHz의16/32/64cell 오차 감소·최종<=1e-3V, 별도 finite-pi
주파수 기준의128/256/512샘플 시간 오차 감소를 요구합니다. 원3신호8→9주기
정착 차1.0230294e-7V는1e-8V 기준을 넘었습니다. 이 실패를 보존하며 수락으로
표현하지 않습니다. 별도 긴 관측 검증은 같은 기준을512샘플9/10/11주기와
1024샘플9/9.25/9.5주기에 적용합니다. 공간 대조는100MHz9주기1024샘플과
500MHz30주기256샘플이며10000행 이내입니다. 후보 수치 코드와 허용 오차는
바꾸지 않았습니다. 지정 fixture이며 임의 대역·관측 시간·실측 보드 정확도
보장이 아닙니다.

0/rank-one/근영 외부 행렬·저장/전류 분리·선형/시간/임피던스/신호/pole 불변식·
선언한0 강도·엄격 입력·읽기 전용 복사·원래 실패를 검사합니다. 기존 전체 상태
출력96개는 소스/설치본에서 정확한 해시를 유지합니다. 별도 결과형은 아직 저장/
파동 API에 연결하지 않습니다. 일반 RLC 토폴로지·장 추출·재료 피팅·FFT/TDR·
플랫폼 연결·새 의존성은 추가하지 않습니다.
[2신호 reactive 계약](debye_reactive_startup.md)을 참고하세요.
