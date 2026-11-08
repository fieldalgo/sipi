# 두 신호 시작 회로의 명시적 용량성 부하

`coupled_capacitive_ladder_response`는 [혼합 경계 유한 회로](coupled_boundary_startup.md)에
**F 단위의 far 부하 커패시턴스 행렬**을 추가합니다. 선로의 단위 길이 C [F/m]와
별도이며 소스·선로·외부 커패시터의 초기 에너지는 0입니다. 기하·파형 대역·저항에서
커패시턴스를 추정하지 않습니다.

```python
import numpy as np
from sipi import coupled_capacitive_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
r = coupled_capacitive_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12)
assert r.power_balance_relative_error <= 1e-10
assert r.total_power_balance_relative_error <= 1e-10
np.testing.assert_array_equal(r.total_energy, r.energy+r.load_capacitor_energy)
assert r.load_capacitor_current.shape == (121, 2)
record = r.to_dict()
assert 'load_capacitance_f' in record['input'] and not record['states_included']
```

## 모델과 경계

`load_capacitance`는 유한 실수의 정확히 대칭인 2x2 양의 준정부호 행렬입니다.
0과 rank-one을 허용하고 음의 고유값·숫자 bool·비유한 값·스칼라 생략·비대칭은
거부합니다. 음의 고유값 보정이나 소자 연결 토폴로지 추출은 하지 않습니다.
상수 선형 수동 구성 관계를 직접 지정합니다.

기존 혼합 경계 core 계약을 유지합니다. 상수 대칭 2x2 PSD R/G, 조건을 만족하는
SPD L/C, 명시적 1..128셀, 0 시작의 균일 2..10000시간, 첫 행 0의 `(표본 수,2)`
PWL 소스와 마지막 값 유지입니다. 소스 저항은 유한 비음수/0=이상 소스, 부하는
유한 비음수/0=단락 또는 None=개방입니다. 여기서 개방은 **병렬 부하 저항 없음**을
뜻하며 명시한 커패시터는 전류를 흘립니다. 단락은 커패시터가 있어도 해당 전압을
고정합니다. 임의 유도성·비선형·능동·분산 외부 부하는 없으며 기존 저장 버전을
자동 확장하지 않습니다.

고정 전압 제거 전에 전체 far 노드 질량 블록에 Cload를 더합니다. 같은 자유 상태
변환으로 선로와 부하의 상호 커패시턴스를 유지합니다. 유한/개방 far 포트의 선로 안
전류는 −V/R−Cload*V_dot(개방은 V/R 제외)입니다. 단락의 선로 포트 전류는 내부
선로 끝 C/G와 구간 flux의 결합 항까지 포함합니다. 별도 커패시터 전류의 양의
방향은 **선로에서 외부 커패시턴스 행렬로**입니다. 개별 값은 어느 부호든 가능하며
오른쪽 PWL 기울기/마지막 0 기울기와 4개 선로 안 포트 부호를 유지합니다.

## 내부와 외부 에너지 구분

`CapacitiveRLGCLadderResponse`는 읽기 전용 포트/내부 상태와 선택적 직렬화를
상속합니다. 입력은 `load_capacitance_f`, scope는 용량성 부하 모델을 명시합니다.
기존 `energy`, `energy_rate`, `series_loss`, `shunt_loss`, `line_power`는 내부
선로만 가리킵니다. 새 배열은 2열 `load_capacitor_current`와 전체 합계인
`load_capacitor_energy`, `load_capacitor_power`입니다.

Eload=.5*Vfar^T*Cload*Vfar, Pload=Vfar^T*Cload*Vfar_dot입니다. 읽기 전용
`total_energy`, `total_energy_rate`는 이 외부 항을 선로 값에 더합니다. 부하 저항
손실은 sum(V**2/R)로 계산합니다. 커패시터를 포함한 전체 포트 I²R을 쓰면 무효
전류를 손실로 잘못 셉니다. 단락/개방에는 저항 손실이 없습니다.

두 균형을 상대 잔차 1e-10 이하로 검사합니다: 선로 E_dot=선로 포트 전력−내부
R/G 손실, 전체 E_dot=소스 전력−소스/부하 저항 손실−내부 R/G 손실. 각각 에너지율·
입력·전체 손실 중 가장 큰 크기로 정규화하고 전체 0 응답은 잔차 0입니다. 내부/외부
저장 에너지와 내부 손실은 비음수이고 음의 귀환 전력을 보존합니다. 비유한 질량
행렬·상태·진단은 부분 결과 없이 오류입니다. 균형만으로 수렴/실제 재료 정확도를
인증하지 않습니다.

## 독립 근거와 정착 시간

Cload0은 혼합 회로 상태를 재현합니다. 양쪽 far 노드가 단락이면 명시한 행렬은
전압·전류·에너지가 0이고 선로 상태를 바꾸지 않습니다. 한쪽 단락의 rank-one
행렬은 단자 간 커패시터 전류를 유지합니다. 시간/임피던스 스케일·도체 순열·0 입력·
저항 손실 분리·무손실 포획 에너지 교환도 검사합니다. 기존 API의 12개 전체 상태
ramp/pulse 재현은 이전 설치 빌드와 정확히 같습니다.

독립 1셀 LC ramp 해는 길이 1m, L=I H/m, C=.4I F/m, R=G=0, 이상 소스,
부하 저항 없음, Cload=diag(.3,.7)F를 사용합니다. far 용량은 .2+Cload이므로
omega**2=1/(L*(.2+Cload))입니다. 0..4s의 401표본, 0..1s에 [1,−.4]까지 상승하는
입력에서 포트 전압/전류·내부/외부 에너지가 rtol1e-10/atol1e-12 이내이며 소스
절반 커패시터 전류도 포함합니다.

독립 scikit-rf2.2.0 연속 모드 ABCD에 Yload=1/100+jw*Cload_mode를 적용해
500MHz를 비교합니다. 양의 저항 API 예제의 교환 대칭 RLGC, .1m, 각 Rs25/RL100,
Cload[[30,−5],[−5,30]]pF, 첫 소스 정현파 20주기/주기당256표본/마지막4주기 phasor의
32/64/128셀 오차는 .002345/.000593/.000154V로 감소하고 .001V 기준을 통과합니다.
PWL 보간 오차도 포함합니다. 코드 예제의 비대칭 행렬/종단/Cload의 16셀은 별도
노드별 KCL/DOP853과 1e-8V/1e-9A 이내입니다(rtol1e-10,atol1e-12,최대 step은
최소 선로 모드 지연/(5*cells)). 같은 회로의 다른 전파 알고리즘이며 독립 공간
이산화가 아닙니다. 기존 SciPy1.18.1과 시험 전용 scikit-rf2.2.0은 BSD-3-Clause입니다.

DC 검사는 처음 200ns에서 잔차 1.515e-8V로 실패했습니다. 시간 간격 세분과 별도
상태 좌표 변환에도 같았고, 안정한 느린 모드의 감쇠 시간은 26.24ns입니다.
300/400/500ns 전압 잔차는 3.724e-10/2.514e-12/9.515e-14V, 커패시터 전류는
9.895e-12/9.575e-14/2.577e-15A로 감소합니다. 400/500ns는 원 DC rtol1e-10/
atol1e-12 및 전류 1e-13A 기준을 통과합니다. 원 200ns 실패를 보존하고 시험의
시간만 명시적 500ns로 정했습니다. API는 사용자 시간을 자동 연장하지 않습니다.
600/1000ns 전압은 반올림 수준에서 같아지므로 그 이전 구간에서 엄격 감소를
검사합니다. 수식/허용 오차 변경은 없습니다.

상수 두 신호 유한 회로이므로 입력마다 공간·소스·시간 수렴과 정착을 확인해야
합니다. 부하 C 저장 입력, 앱 폼·브라우저/Windows 연결 및 실측 정확도는 별도입니다.

[혼합 저항 경계](coupled_boundary_startup.md) · [양의 저항 두 신호 회로](coupled_startup.md) ·
[English](../../../../../packages/sipi/coupled_capacitive_startup.md)

[용량성 저장 v3](coupled_capacitive_startup_document.md)

[외부 직렬 RL 분기](coupled_reactive_startup.md)
