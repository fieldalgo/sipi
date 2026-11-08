# 외부 직렬 RL 분기를 포함한 결합 시작 응답

`coupled_reactive_ladder_response`는 부하 커패시턴스·도체별 저항 종단과 병렬인
명시적 두 전류 **직렬 RL 분기**를 추가하고 `ReactiveRLGCLadderResponse`를 반환합니다.
[용량성 API](coupled_capacitive_startup.md)와 저장 v3의 계약은 그대로이며 이 별도 API에는
명시적 저장 v4를 아래 링크에서 설명합니다.

```python
import numpy as np
from sipi import coupled_reactive_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
response = coupled_reactive_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
assert response.voltage.shape == (121, 4)
assert response.load_branch_current.shape == (121, 2)
assert response.total_power_balance_relative_error <= 1e-10
assert np.all(response.load_branch_energy >= 0)
assert np.all(response.load_branch_resistor_loss >= 0)
assert not response.to_dict()['states_included']
```

## 물리 계약과 단위

선로는 상수 실수 정확 대칭 2x2 R/G PSD, 조건을 만족하는 L/C SPD 행렬, 양의 길이와
명시적 1..128셀을 사용합니다. 시간은 0에서 시작하는 균일 2..10000 표본(상대 간격
오차 1e-10)이고 두 열의 PWL 소스는 첫 행이 0입니다. 초기 전압·전류도 0입니다.
소스 저항은 유한 비음수 2개(0=이상 소스), 병렬 부하 저항은 비음수(0=단락) 또는
null/None(저항 경로 없음)입니다.

외부 `load_capacitance` [F], `load_branch_resistance` [ohm],
`load_branch_inductance` [H]는 모두 명시적인 유한 실수 정확 대칭 2x2 행렬입니다.
커패시턴스와 분기 저항은 영행렬/rank-one을 포함한 PSD이며, 분기 인덕턴스는 고유값
비가 1e-12보다 큰 SPD입니다. 음의 고유값을 보정하지 않습니다. 특이/영 인덕턴스,
스칼라 확장·bool·복소수·비유한 값·비대칭 행렬은 거부합니다. 외부 C/L은 집중 소자로
선로 C[F/m]·L[H/m]와 구별합니다. 임의 RLC netlist나 초기 인덕터 전류 모델은 아닙니다.

분기 전류 `ib`는 선로에서 외부로 향하며 `Lb*dib/dt=Vfar-Rb*ib`, 커패시터 전류는
`ic=Cload*dVfar/dt`입니다. 원단 노드 KCL에 `-ib`를 포함합니다. 단락 노드의 선로 포트
전류도 내부 끝점 C/G와 직렬 flux로 계산합니다. 상호 인덕턴스 때문에 전압 0으로 고정한
단자의 분기 전류가 0이 아닐 수 있습니다.

유한 질량 행렬 회로에 분기 전류 상태 2개를 추가하며 혼합 경계 제거와 PWL 전파를
유지합니다. 이상 소스는 오른쪽 기울기와 마지막 값 유지 규약입니다. 외부 분기 에너지와
손실을 내부 선로 진단에 섞지 않습니다. 셀·소스 표본 수렴은 입력별로 확인해야 하며
셀/표본 상한이 정확도를 인증하지 않습니다.

## 응답과 전력 구분

복사된 읽기 전용 응답은 노드/구간 상태와 선로 안으로 들어가는 4포트 전류를 유지합니다.
`load_branch_current`는 외부 RL 분기로 향합니다. `load_branch_energy`,
`load_branch_energy_rate`, `load_branch_resistor_loss`는 상호항을 포함한 두 도체의 합입니다.

- 내부 선로 `energy`, `energy_rate`, `series_loss`, `shunt_loss`, `line_power`는 기존 뜻입니다.
- 커패시터 에너지/전력은 별도입니다. 분기 에너지는 `ib.T*Lb*ib/2`, 변화율은
  `ib.T*Lb*dib/dt`, 저항 손실은 `ib.T*Rb*ib`입니다.
- `load_resistor_loss`는 원래 병렬 저항의 `V²/R`만 의미하며 분기 손실을 포함하지 않습니다.
  커패시터/분기 전류를 합해 제곱하지 않습니다.
- `total_energy`와 `total_energy_rate`는 선로·외부 C·분기 L을 포함합니다. 소스 전력에서
  소스/병렬부하/분기/내부 손실을 빼면 전체 에너지 변화율입니다. 분기 단자 전력은 분기
  에너지 변화율과 저항 손실의 합입니다.

내부·합계 RHS 전력 보존의 상대 오차는 각각 1e-10 이하여야 합니다. 비유한 동역학/진단과
음의 수동 에너지/손실은 거부합니다. 기본 `to_dict()`는 내부 선로 상태를 생략하지만
외부 분기 전류와 모든 구분된 에너지/전력을 담습니다. `include_states=True`는 선로 상태도
포함합니다. scope는 `finite-passive-two-signal-reactive-load-rlgc-startup`입니다.

## 독립 검증과 한계

1셀 무손실 L-C-L ramp/hold 해석식으로 전압·전류·각 에너지를 rtol1e-10/atol1e-12에서
검사합니다. scikit-rf 모드 ABCD의 `Yload=1/R+jwC+1/(Rb+jwLb)`와 500MHz·20주기·주기당
256표본·마지막 4주기 phasor를 비교합니다. 32/64/128셀 오차가 감소하며 최종 1mV 이하를
요구합니다. 비대칭 독립 노드 KCL/DOP853 비교는 전압 1e-8V·전류 1e-9A 이하입니다.
DC·무손실 pulse 뒤 에너지 교환·혼합 단락/개방·상호 분기 전류·시간/임피던스/순열/중첩
불변식·출력 복사·엄격 입력·기존 용량성 동작도 검사합니다.

이 근거는 명시한 유한 수동 회로 범위입니다. 임의 주파수 분산·비선형 부하·추가 도체·
Maxwell 시간 해석·일반 TDR/eye/BER·실측 정확도·브라우저/Windows 동등성은 확인하지 않습니다.

[용량성 부하](coupled_capacitive_startup.md) · [혼합 경계](coupled_boundary_startup.md) ·
[English](../../../../../packages/sipi/coupled_reactive_startup.md)

[리액티브 저장 v4](coupled_reactive_startup_document.md)
