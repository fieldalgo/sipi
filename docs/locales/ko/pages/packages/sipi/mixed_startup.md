# 전압원·전류원 혼합 시작 응답

`coupled_mixed_source_ladder_response(time, sources, ...)`는 기존 외부 C·직렬 RL 부하를
가진 상수 수동 두 신호 선로에 종류를 명시한 소스 2개를 연결합니다. 별도 응답
`MixedSourceRLGCLadderResponse`를 반환하며 기존 전압원/전류원 API 계약은 유지합니다.

```python
import numpy as np
from sipi import coupled_mixed_source_ladder_response

time = np.linspace(0., 12e-9, 121)
sources = [dict(kind='voltage', voltage_v=np.minimum(time/2e-9, 1.),
                series_resistance_ohm=0.),
           dict(kind='current', current_a=-.008*np.minimum(time/3e-9, 1.),
                shunt_resistance_ohm=None)]
response = coupled_mixed_source_ladder_response(time, sources,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=16, load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.source_kinds == ('voltage', 'current')
assert response.source_units == ('V', 'A')
np.testing.assert_array_equal(response.voltage[:, 0], sources[0]['voltage_v'])
np.testing.assert_array_equal(response.current[:, 1], sources[1]['current_a'])
assert response.total_power_balance_relative_error <= 1e-10
assert not response.to_dict()['states_included']
assert np.all(response.source_series_resistor_loss == 0.)
assert np.all(response.source_shunt_resistor_loss == 0.)
```

## 단위가 명시된 입력과 경계

`sources`는 정확히 2개 dictionary의 list/tuple입니다. 각각 정확히 3개 키를 가집니다.

| kind | 파형 키와 단위 | 저항 키와 의미 |
|---|---|---|
| voltage | `voltage_v`, V | `series_resistance_ohm`, 유한 비음수;0은 근단 전압 지정 |
| current | `current_a`, A | `shunt_resistance_ohm`, 유한 비음수 또는 None;0은 근단 단락,None은 병렬 저항 제거 |

파형은 시간 행 길이에 맞는 유한 실수 1차원 배열이며 첫 값은0입니다. 다른 종류의 키·
추가/누락 키·모호한 단위·bool·복소수/비유한 값·스칼라 확장을 거부합니다. 전압원 저항은
None일 수 없습니다. 두 소스가 같은 종류인 경우와 두 혼합 순서 모두 지원합니다.

기존 선로/부하 조건을 공유합니다. 시간은0에서 시작하는2..10000개 균일 행이며 PWL와
최종값 유지, 명시1..128셀·양의 길이·유한 실수 정확 대칭 PSD 선로R/G·조건을 만족하는
SPD 선로L/C를 요구합니다. 집중 Cload[F]/Rbranch[ohm]는 PSD, Lbranch[H]는 고유값
비>1e-12인 SPD입니다. 영/rank-one C/R을 허용하되 음의 고유값을 보정하지 않습니다.
도체별 부하 저항은 유한 비음수 또는 None입니다. 초기 저장 에너지0인 기존 병렬
C/직렬RL/저항 부하이며 임의 netlist가 아닙니다.

이상 전압/전류 혼합 경계에서도 근단 상호 C를 보존합니다. 지정 전압을 변환한 질량
상태로 제거하고 단자 전류에는 endpoint C*dV/dt+G*V와 직렬 흐름을 포함합니다.
복원은 PWL 오른쪽 기울기와 마지막 기울기0을 사용합니다. 병렬 저항0인 전류원은
선로 대신 단락으로 전류를 흘릴 수 있고 공급 전력은0입니다. 특이한 소스 등가 변환은
필요하지 않습니다.

## 단위·전력·출력

`source_values` 형상은 `(times,2)`이며 각 열의 `source_kinds`와 `source_units`(V/A)를
명시합니다. `inputs['sources']`도 종류별 파형·저항 키를 보존합니다. 모호한 source
전압/전류 alias는 없습니다. 4개 단자 `current`는 모두 선로 안쪽 방향입니다.

공급 전력은 전압원 `Vs*Iterminal`과 전류원 `Iinj*Vterminal`의 합입니다.
`source_series_resistor_loss`에는 전압원의 R*Iterminal²만,
`source_shunt_resistor_loss`에는 양의 유한 병렬 저항을 가진 전류원의 Vterminal²/Rsh만
포함합니다. 둘 다 비음수이며 구분합니다. 유한 소스 등가 변환은 단자 V/I와 순전달
전력을 보존하지만 공급 전력·개별 소스 손실은 일반적으로 달라집니다.

선로 에너지/변화율·직렬/병렬 손실, 외부 커패시터 전류/에너지/전력, 분기 전류/인덕터
에너지/변화율/저항 손실, 병렬 부하 저항 손실을 구분합니다. `total_energy`와
`total_energy_rate`는 선로와 외부 C/L을 합칩니다. 선로와 전체 공급/손실/RHS 보존은
상대1e-10을 요구합니다. 유한 회로 보존 검사이며 공간/시간/정착 정확도 검사는 아닙니다.

모든 배열·합계 에너지 배열은 복사된 읽기 전용 유한 값입니다. `to_dict()`는 기본적으로
내부 선로 상태를 생략하고 `include_states=True`는 포함합니다. scope는
`finite-passive-two-signal-mixed-source-reactive-startup`입니다. 이 별도 응답의 저장 입력
스키마와 포트 파동 연결은 아직 없으며 각각 별도 계약으로 연결해야 합니다.

## 독립 검증과 한계

분리된1셀의 이상 전압/전류 ramp/hold를 독립 직렬L·LC 해석해와 rtol1e-10/atol1e-12로
비교합니다. 후보 조립 행렬을 재사용하지 않는 비대칭 직접 nodeKCL/DOP853으로 이상
소스 순열과 유한25/37ohm 경계를 V≤1e-8V·단자/분기I≤1e-9A에서 검사합니다. 유한
소스 등가는 V≤1e-10V/I≤1e-12A 및 전력 분할을 검사합니다.

scikit-rf 연속 모드ABCD를4포트 admittance로 바꾸고 동일 혼합 유한 소스·외부 부하를
연결합니다.500MHz·20주기/주기당256표본·마지막4주기 phasor에서32/64/128셀 전압 오차는
1.753→.449→.120mV로 감소해 최종1mV 기준을 통과합니다. 한 유한 소스 조건의 근거이며
이 결과로 이상 전류원의 정착을 추정하지 않습니다.

동종 소스 한계·혼합6경계·무손실pulse후 에너지·영/rank-one 부하·영 입력·선형/시간/
임피던스/순열 불변식·복사·엄격 입력도 검사합니다. 기존7API의38개 ramp/pulse/경계
fixture는 전체 상태/JSON이 정확히 같습니다. 자동 시간/메시 변경·주파수 분산·초기
에너지·비선형 소자·일반TDR/eye/BER·실측 정확도·브라우저/Windows 일치를 뜻하지 않습니다.

[전압원 리액티브 시작 응답](coupled_reactive_startup.md) ·
[전류원 시작 응답](norton_startup.md) · [English](../../../../../packages/sipi/mixed_startup.md)
