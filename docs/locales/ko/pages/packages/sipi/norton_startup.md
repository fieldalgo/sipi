# 수동 리액티브 부하의 전류 구동 결합 시작 응답

`coupled_norton_reactive_ladder_response`는 상수 수동 두 신호 RLGC 선로와 기존 병렬
커패시터/직렬RL/병렬저항 부하를 명시적 Norton 전류원 두 개로 구동합니다. 전류 단위와
병렬 소스 손실 이름을 가진 별도 `NortonReactiveRLGCLadderResponse`를 반환합니다.
기존 [전압원 API](coupled_reactive_startup.md) 계약은 유지합니다.

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
```

## 전류원 경계 계약

`source_currents`는 첫 행0인 유한 실수 `(시간 수,2)` 배열이며 단위는 **A**입니다.
시간은0에서 시작하는 균일2..10000행(상대 간격1e-10)이며 PWL 전류와 마지막 값 유지
규약입니다. 초기 내부/외부 저장 에너지는0입니다. `source_shunt_resistance`는 유한
비음수 또는 None인 명시적 두 항목입니다. None은 병렬 저항 없는 이상 전류원,0은
근단 단락입니다. 무한대·bool·복소수·스칼라 확장·잘못된 형상은 거부합니다.

유한 양의 병렬 저항에서 근단 선로 전류는 `Iinj-Vnear/Rsh`, 저항이 없으면 정확히
`Iinj`입니다. 근단 단락에서는 전압0이고 선로 전류는 내부 끝점 C/G와 직렬 flux로
정합니다. 주입 전류가 선로를 거치지 않고 단락으로 흘러도 공급 전력은0입니다.
공통 질량 행렬 전파가 상호 끝점 커패시턴스와 고정 단락 노드를 보존합니다.

선로/부하는 기존 리액티브 API 계약입니다. 정확 대칭 실수2x2 PSD 선로R/G, 조건을
만족하는 SPD 선로L/C, 양의 길이, 명시적1..128셀, PSD 집중 Cload[F]/Rbranch[ohm],
고유값 비>1e-12인 SPD Lbranch[H]입니다. 부하 저항은 유한 비음수/None이며0은
단락입니다. 음의 고유값을 보정하지 않고 특이 분기L을 거부합니다. 명시적 집중 부하
구조이며 임의 RLC topology나 주파수 분산은 아닙니다.

## 소스 전력과 손실 구분

4포트 전류는 모두 선로 안으로 향하고 `source_currents`는 주입 소스 전류입니다.
소스 공급 전력은 `sum(Vnear*Iinj)`이며 별도 `source_shunt_resistor_loss`는 유한 양의
병렬 저항에서의 `sum(Vnear²/Rsh)`입니다. Thevenin 소스의 직렬 손실과 다릅니다.
단위가 혼동되는 `source_voltages`나 `source_resistor_loss` alias는 제공하지 않습니다.

유한 양의 병렬 저항은 `Vs=Iinj*Rsh`, 직렬 저항Rsh의 전압원과 등가입니다. 선로V/I와
내부/부하 저장 에너지는 같지만 공급 소스 전력과 소스 저항 손실은 일반적으로
다릅니다. 그 차이인 순전달 전력만 같습니다. 개방/단락 병렬 저항은 특이 등가 변환
없이 직접 처리합니다.

선로 `energy/energy_rate`, 내부R/G손실, 부하 커패시터 에너지/전류/전력, 분기
에너지/변화율/저항 손실, 원래 병렬 부하 저항 손실을 각각 유지합니다.
`total_energy/total_energy_rate`는 선로·Cload·Lbranch 합계입니다. 소스 전력에서
모든 소스/내부/부하 손실을 빼면 합계 에너지 변화율입니다. 선로·합계 RHS 보존은
상대1e-10, 수동 에너지/손실 비음수, 유한 연산을 요구합니다. 소스/포트 전력은 음수도
보존합니다.

상태/진단 배열은 복사된 읽기 전용입니다. `inputs`는 `source_currents_a`,
`source_shunt_resistance_ohm`을 포함한 SI 입력 복사를 반환합니다. 기본 유한 JSON은
내부 선로 상태를 생략하고 `to_dict(include_states=True)`는 포함합니다. scope는
`finite-passive-two-signal-norton-reactive-startup`입니다. [입력 저장](norton_startup_document.md)은 별도 전류 단위 스키마를 사용합니다.
[직접 포트 파동 진단](startup_waves.md)은 단자 V/I로 이 응답을 지원합니다.
[파동 저장](startup_waves_document.md)은 Norton에 명시적 version2를 요구하며
version1은 Norton 입력을 계속 거부합니다.

## 독립 수락과 정착 한계

유한25/37ohm 소스 등가성은 선로V≤1e-10V/I≤1e-12A와 에너지를 검사합니다. 이상
전류 구동1셀LC ramp/hold는 독립 해석식과 rtol1e-10/atol1e-12에서 비교합니다.
비대칭 노드KCL/DOP853은 근단[None,37]·원단[91,None]에서 V≤1e-8V/I≤1e-9A입니다.

scikit-rf 연속 모드ABCD와500MHz 마지막4주기 phasor를 비교합니다. 유한50ohm 소스는
20주기·주기당256표본에서32/64/128셀 오차가 약81uV로 감소합니다. 이상 전류원은 별도로
검증한 긴 관측을 요구합니다.64주기·주기당128표본·8193행에서32/64/128셀 오차는
1.506/.545/.291mV입니다.128셀의20/40/64주기 오차3.335/1.045/.291mV는 감소하며 마지막만
1mV를 만족합니다. 독립 유한π셀ABCD곱의 공간 오차는 연속 기준 대비128셀에서93.2uV로
감소합니다. 원래20주기·256표본의 이상 소스는3.357mV로1mV에 실패했고36주기도 최종
오차가1mV 이내지만 단조 공간 수렴에 실패했습니다. 실패 근거를 보존하며 격자/시간을
자동 변경하지 않습니다.

근단[None,37]·원단[91,113]·G0·8셀의 DC 시험은500ns에서 원래 엄격 전압 기준에
실패했습니다(3.109nV). 고정.2ns 표본의600/800/1000ns 각각 마지막20ns의101표본 전체를
검사합니다. 전압/전류 window 최댓값이 감소하고800/1000ns 두 구간은 원래
rtol1e-10/atol1e-12 DC 기준을 만족합니다. 가장 느린 감쇠 시간은 약34.6ns입니다.
해당 입력의 정착 근거이며 보편적 시간 권장값이나 허용오차 완화가 아닙니다.

혼합 소스/부하 저항·영/rank-one항·무손실 pulse 뒤 에너지·DC·시간/임피던스/순열/중첩
불변식·복사·엄격 입력도 검사합니다. 혼합V/I 소스 종류·초기 에너지·일반TDR/eye/BER·
실측 정확도·브라우저/Windows 동등성·최신head 전체 검증을 추정하지 않습니다.

[전압 구동 리액티브 시작 응답](coupled_reactive_startup.md) ·
[English](../../../../../packages/sipi/norton_startup.md)
