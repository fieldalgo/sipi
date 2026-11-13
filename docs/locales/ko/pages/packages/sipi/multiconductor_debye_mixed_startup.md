# 명시 전압원·전류원을 섞는 다신호 Debye 회로

[English](../../../../../packages/sipi/multiconductor_debye_mixed_startup.md) | **한국어**

`psd_multiconductor_debye_mixed_reactive_ladder_response`는3/4신호·PSD Debye
분극·외부 커패시터/직렬 RL 부하에 명시 전압원·전류원을 함께 연결합니다.
별도 결과형 `MixedSourceMulticonductorDebyeReactiveLadderResponse`를 반환합니다.
기존 [전류원 회로](multiconductor_debye_norton_startup.md)를 한 번 전파하며,
각 소스의 원래 값과 단위를 보존합니다.

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
```

`sources`는 정확히 `signals`개 객체의 list/tuple이며 각 객체의 키는3개입니다.
종류는 문자열이어야 하며 NumPy 배열은 전파 전에 거부합니다.
전압 객체는 `kind='voltage'`, 시간 행별 V 값 `voltage_v`, 유한한
`series_resistance_ohm>0`을 씁니다. 전류 객체는 `kind='current'`, A 단위
`current_a`, S 단위의 유한한 `shunt_conductance_s>=0`을 씁니다. 컨덕턴스0은
이상적 전류원입니다. 전류 소스의 저항 alias·스칼라 파형 확장·암묵적 단위
추론·이상적 전압원·near Dirichlet·단락은 이 API에서 허용하지 않습니다.

모든 열은0부터 시작하는 균일한 시간 행2–10000개를 공유하며 초기 값은0입니다.
유한한 양수1/Rs와 Vs/Rs로 기존 Norton 회로에 연결합니다. 비유한 변환이나
비영 전압이 underflow로0전류가 되는 경우 전파 전에 거부합니다. 변환한 전류
alias 대신 원래 typed 소스를 내보냅니다. `source_values` 열 단위는
`source_units`에 명시됩니다.

```python
near_v=r.voltage[:,:3];near_i=r.current[:,:3]
np.testing.assert_allclose(near_i[:,0],r.source_values[:,0],rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(near_i[:,1],(r.source_values[:,1]-near_v[:,1])/50.,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(near_i[:,2],r.source_values[:,2]-.01*near_v[:,2],rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_series_resistor_loss,50.*near_i[:,1]**2,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_shunt_resistor_loss,.01*near_v[:,2]**2,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    np.sum(near_v*near_i,axis=1),rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(r.total_energy,r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert 'source_currents_a' not in r.inputs and 'source_voltages_v' not in r.inputs
out=r.to_dict(include_states=True)
assert out['source_units']==['A','V','A'] and not r.source_values.flags.writeable
```

전압원 공급 전력은 Vs*Iterminal, 전류원 공급 전력은 Iinjected*Vnear입니다.
직렬 저항 손실은 전압원에서만, 병렬 저항 손실은 전류원에서만 합산합니다.
양끝 단자 전류는 선로 안으로 향합니다. near 단자 전력은 두 소스 손실을
제외합니다. far 전력은 병렬 R·커패시터·직렬 RL의 개별 항을 유지합니다.
내부 `line_energy`는 순간/분극 저장을 포함하고 `total_energy`는 외부 C/L까지
포함합니다. 기존 선로 수지와 typed 소스 전체 수지는 상대1e-10 이내여야 합니다.
비유한 진단·음의 수동 손실은 실패하며 값을 clipping하지 않습니다.

기존 행렬/자원 규칙을 유지합니다. signals3/4·cells1–64·양의 완화 주파수
1–2개(Hz), 정확 대칭 실수 PSD R/G/DeltaC/Cload/Rbranch, 고유값 비가1e-12보다
큰 SPD L/C_inf/Lbranch를 요구합니다. 계산된 PSD 부호의 보수적 거부도 유지합니다.
배열·pole 순서·null 방향·유한 범위 실패를 보존하며 개수 제한은 정확도 보장이 아닙니다.

3/4신호의 모든 전압/전류 조합24개·동종 Thevenin/Norton 전체 상태·분극강도0의
기존2신호 상수 혼합회로 블록 한계4조건을 대조합니다. 독립 비가환 charge/branch
KCL을 입력 꺾임점에서 나눠 SciPy DOP853으로 적분하며 기준은1e-8V·1e-9A입니다.
엄격한 형/키/단위/유한 변환·전파 실패·읽기전용/복사·선형성·시간/임피던스 배율·
도체 순열·pole 순서를 검사합니다. 기존 전체 상태128개는 소스/설치본에서 정확한
해시를 유지합니다.

별도 주파수 수락은 uniformGs=.02S, 번갈아 지정한 소스 종류와 원저손실 fixture의
R/G를10배로 한 감쇠 modal 조건입니다. 100MHz는16/18/19주기·주기당512샘플,
500MHz는64/72/76주기·128샘플을 씁니다. 마지막4주기 phasor의 관측시간 차이는
1e-8V 이하여야 합니다. 입력128/256/512 세분 오차는 감소해야 하며, 공간16/32/64
cell의 같은 PWL 연속선로 오차는 엄격히 감소하고 최종1e-3V 이하여야 합니다.
scikit-rf2.2.0 ABCD에서 주기 PWL alias8192/16384/32768을 합산하고 참조/상수전달
계수 기준1e-8을 검사합니다. 별도 finite-pi KCL alias32/64/128도 각 시간 결과와
1e-8V 이내로 맞아야 합니다. 명시 fixture에 대한 수락이며 임의 대역/관측시간을
보장하지 않습니다. 이전 저손실 PWL/짧은 관측시간 실패는 계속 수락 범위 밖입니다.

field 추출·일반 분산/초기 에너지·실측 정확도·자동 시간 선택·새 의존성·앱/플랫폼
연결을 추가하지 않습니다. [엄격한 typed 소스 저장](multiconductor_debye_mixed_startup_document.md)은
이제 가능하며 명시6·8단자 파동 변환도 지원합니다. 이 저장 추가로 registry는89스키마·37template입니다.
기존 [2신호 상수 혼합 API](mixed_startup.md)의 경계 계약은 별개이며 그 API의
이상적 전압/단락 옵션을 여기서 추론하지 않습니다.


[다신호 혼합 소스 단자 파동](multiconductor_debye_mixed_startup_waves.md)은 단자 전류를 보존하고 소스 직렬·병렬 손실을 모두 제외합니다.


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
