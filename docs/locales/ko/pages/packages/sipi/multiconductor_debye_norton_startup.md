# 다신호 Debye 전류원 시작 응답

[English](../../../../../packages/sipi/multiconductor_debye_norton_startup.md) | **한국어**

`psd_multiconductor_debye_norton_reactive_ladder_response`는 별도 결과형
`NortonMulticonductorDebyeReactiveLadderResponse`를 반환합니다.
[외부 C·직렬 RL 부하가 있는3·4신호 PSD Debye 회로](multiconductor_debye_reactive_startup.md)에
명시 주입 전류와 병렬 소스 컨덕턴스를 연결합니다.

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
```

`source_currents`는 A 단위(time,N)이며 첫 행은0입니다.
`source_shunt_conductance`는 유한·비음수 S 단위 N벡터이고0은 이상 전류원입니다.
스칼라 확장·Thevenin 입력 추론·이상 단락·혼합 소스 유형은 수락하지 않습니다.
정규 입력 필드는 `source_currents_a`, `source_shunt_conductance_s`이며 소스
전압·저항·직렬 저항 손실의 별칭을 제공하지 않습니다.

near 선로 유입 전류는 `Iin-Gs*Vnear`, 소스 공급 전력은 `sum(Iin*Vnear)`,
`source_shunt_resistor_loss`는 별도 `sum(Gs*Vnear**2)`입니다. 양의 Gs는
명시 `Vs=Iin/Gs, Rs=1/Gs`와 선로 응답이 같지만 소스 전력 분할은 다릅니다.
시간·선로·부하 입력 검증을 재사용하는 내부 양의 임시 저항은 실제 전파나
내보내기 입력에 사용하지 않습니다.

```python
near=r.voltage[:,:3]
np.testing.assert_allclose(r.current[:,:3],drive-near*[0.,.02,0.],rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,np.sum(drive*near,axis=1),rtol=1e-10,atol=1e-15)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.total_energy_rate,
    r.source_power-r.source_shunt_resistor_loss-r.load_resistor_loss
    -r.load_branch_resistor_loss-r.series_loss-r.shunt_loss-r.relaxation_loss,
    rtol=1e-10,atol=1e-15)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.source_currents.flags.writeable
assert 'source_voltages_v' not in r.inputs
assert r.to_dict()['scope']=='finite-passive-multiconductor-psd-debye-norton-reactive-startup'
```

원래 수동 선로·부하 계약을 유지합니다: N=3 또는4, cells1–64, 양의 길이[m],
0에서 시작하는 균일 시간2–10000행, 양의 Debye pole[Hz]1–2개, 실수·정확
대칭 행렬입니다. R[ohm/m]·G[S/m]·DeltaC[F/m]·Cload[F]·Rbranch[ohm]는 PSD,
L[H/m]·C_inf[F/m]·Lbranch[H]는 정규화 고유값 비율>1e-12인 SPD입니다.
부하 저항은 유한·양의 N벡터입니다. 계산한 PSD 고유값이 음수면 보수적으로
거부하며 대칭 복구·클리핑·rank 기준을 적용하지 않습니다. 작은 양의 강도와
선언한0 pole 열은 보존합니다.

far 선로 유입 전류는 `-Vfar/Rload-Cload*dVfar/dt-Ibranch`이고 가지는
`Lbranch*dIbranch/dt=Vfar-Rbranch*Ibranch`와0 초기 상태를 유지합니다.
병렬 부하 저항·가지 저항 손실은 구분합니다. `line_energy/rate`는 내부 순간·
분극 저장, `total_energy/rate`는 외부 C/L 저장까지 포함합니다. 두 상대1e-10
전력 기준, 유한·비음수 저장/손실, 읽기 전용 배열과 독립 입력/내보내기 복사를
유지합니다. 개수 제한은 자원 상한이며 정확도·실행 시간 보장이 아닙니다.

독립 물리 검사는 양Gs Thevenin 등가·Debye 강도0인 기존2신호 블록·비가환
전하/가지 KCL DOP853(V1e-8/I1e-9/가지I1e-9)·Gs→0 한계·해석 짧은 선로
PWL RL 한계를 포함합니다. 소스/설치 회귀에서 기존 전체 상태112개 해시를 보존합니다.

주파수와 과도 응답의 근거를 구분합니다. 순수 주파수 finite-pi KCL은
100/500MHz16/32/64cell에서 scikit-rf2.2.0 연속 modal ABCD로 오차가 엄격히
감소하고 최종<=1e-3V입니다. 주기당 N개 표본의 PWL 입력은 `k=1+m*N`
고조파 전달에 `sinc(k/N)**2`를 곱해 표본 기본파를 합산합니다. 음의 주파수는
켤레 전달을 사용합니다. 직선 보간한 입력을 연속 사인파로 취급하지 않습니다.
원 fixture의72주기128표본 과도 단자는 독립 finite-pi PWL KCL과1e-8V 이내로
일치합니다. 이는 유한 회로 대조이며 연속 선로 공간 수렴을 뜻하지 않습니다.

원 저손실100MHz16/18/19주기 정착 검사는 최대8.889e-7V로1e-8V 기준에
실패했습니다.128표본48/60/72주기로 늘리면 정착은 통과하지만 같은 PWL 연속
기준으로 맞춘 뒤에도 공간 오차의 엄격 감소는 실패했습니다. 고정24조건의
주파수 조사에서도100MHz128/256표본 일부가 비단조였습니다. 실패 조건은
미수락으로 유지합니다. 선로 R/G만10배인 별도 주파수 fixture의 짧은
100MHz8/8.5/9주기·500MHz28/30/32주기도 각각 최대1.259e-5V·1.454e-7V로
정착 기준에 실패했으며 허용 오차를 바꾸어 수락하지 않았습니다.

같은 추가 감쇠 fixture에서 수락한 긴 관측은100MHz512표본16/18/19주기와
500MHz128표본64/72/76주기입니다.1e-8V 정착 기준을 통과하며 입력 보간
128/256/512표본 오차도 감소합니다. 공간16/32/64cell 대조는 각각19주기512표본,
76주기128표본입니다. 동일 PWL 연속 기준의 alias8192/16384/32768 차는1e-8V,
상수 전달 계수 검사는1e-8 이내이며 공간 오차가 엄격 감소·최종<=1e-3V입니다.
각 공간점의 후보 단자는 독립 finite-pi PWL alias32/64/128과도1e-8V 이내로
일치하여 실제 정착을 별도로 검사합니다. 후보 방정식·허용 오차는 변경하지
않았습니다. 지정 fixture이며 임의 대역·관측 시간·실측 보드 정확도 보장이
아닙니다. 위상 추정에 쓰는 마지막4주기 구간 자체가 정착해야 합니다.

별도 결과형은 엄격한 저장 문서로 재실행하고 명시6·8단자 파동으로 변환할 수 있습니다. 일반 SPICE
토폴로지·이상 소스 단락·장 추출·FFT/TDR·플랫폼 연결·새 실행 의존성은 추가하지 않습니다.


[전류원 입력 저장](multiconductor_debye_norton_startup_document.md)은 엄격한 버전 스키마로 명시 전류·소스 컨덕턴스를 보존합니다.


[다신호 전류원 단자 파동](multiconductor_debye_norton_startup_waves.md)은 단자 전류를 보존하고 near 전력에서 소스 병렬 손실을 제외합니다.


[명시 전압원·전류원 혼합](multiconductor_debye_mixed_startup.md)은 각 소스 단위와 직렬/병렬 손실을 구분하며 이 회로를 재사용합니다.


## 수치 상태 스케일과 분기 없는 극한

저장 행렬 기반의 대각 상태 스케일을 전파 전에 적용하고 출력은 물리 단위로
복원합니다. 분극 전압은 대응 노드 전압의 스케일을 공유합니다. 큰 유한 분기
인덕턴스에서 작은 전류를 보존하며 소스 종류·물리 행렬·JSON 버전·전력 검사는
바꾸지 않습니다.

큰 인덕턴스 회귀는 전하 KCL·직렬 RL·Debye 분극 방정식으로 분기 없는 유한
pi 회로를 별도로 구성합니다. 파형 절점을 나누어 DOP853으로 끝단 전압을
적분합니다. 기준 정밀도 1e-9·1e-11의 자속 상대 차이는 1e-7 이하여야 합니다.
양의 소스 컨덕턴스에서는 별도의 capacitive 회로 Thevenin 변환도 사용하며,
그 전압의 Simpson 적분과 상대 1e-5 이내로 일치해야 합니다.

3·4신호, 램프·펄스, 양수 또는 0인 전류원 병렬 컨덕턴스, 교대 전압·전류원을
1e6·1e7·1e8 H와 분기 저항·부하 커패시턴스 0에서 검사합니다. `Lbranch * Ibranch`와
1/L에 비례하는 분기 에너지의 상대 오차는 각각 1e-5 이하여야 합니다. 기존
KCL·전력·소스 동등성·순열·저장 파형 기준을 유지합니다. 수치 스트레스 값은
PCB 부품 권장값이나 임의 회로·실측 정확도 인증을 의미하지 않습니다.
