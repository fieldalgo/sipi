# 외부 정전용량과 직렬 RL 부하 Debye 입력 저장

`DebyeReactiveLadderDocument`는 명시적
[두 신호 Debye 회로](debye_reactive_startup.md)를
`sipi.debye-reactive-startup/1`로 저장합니다. 물리 입력 계약으로 검증하며
상태 전파나 행렬·극점 변경을 수행하지 않습니다.

```python
import numpy as np
from sipi import DebyeReactiveLadderDocument
from sipi.execution import normalize_saved, execute_saved

d = DebyeReactiveLadderDocument([0., 1e-9, 2e-9], [[0., 0.], [1., 0.], [1., 0.]],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -150.], [-150., 150.]]])*1e-12, relaxation_hz=[1e9],
    length=.1, cells=8, source_resistance=[25., 25.], load_resistance=[100., 100.],
    load_capacitance=np.array([[30., -5.], [-5., 30.]])*1e-12,
    load_branch_resistance=[[150., 20.], [20., 150.]],
    load_branch_inductance=np.array([[200., 30.], [30., 200.]])*1e-9)
text = normalize_saved(d.dumps())
r = DebyeReactiveLadderDocument.loads(text).analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert out['input'] == d.to_dict() and out['status'] == 'complete'
assert r.polarization_charge.shape == (3, 9, 1, 2)
```

필수 루트 키는 정확히 16개입니다: `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`,
`relaxation_hz`, `load_capacitance_f`, `load_branch_resistance_ohm`, `load_branch_inductance_h`. 단일 신호 스키마와 달리 R/L/G/C_inf는 2×2 행렬,
강도는 (극점,2,2), 입력은 (시간,2), 각 저항 벡터는 (2,) 형상입니다.
추가 키·미지원 버전·중복 키·잘못된 단위·비유한 값 및 암묵적인
스칼라→행렬 변환을 거부합니다.

R/G의 정확대칭 PSD와 L/C_inf의 SPD 조건은 유지합니다. 1–2개 강도는
정확대칭 PSD여야 하며 특이하거나 거의 특이한 행렬도 받습니다. 음의 고유값
수정이나 rank 클리핑 없이 검증하고 극점 순서·강도0·중복 양의 주파수를
보존합니다. 종단은 유한한 양의 저항이며 저장이 ideal/open/short를
허용하지 않습니다. null 방향 내부 전압은 선택한 실현 상태이며 관측된
재료 분극으로 해석하지 않습니다.

셀 1–128개와 0에서 시작하는 균일 시간 표본 2–10000개를 유지합니다.
`max_evaluations`는 기본값 128인 정수 2–10000으로 전파 전에 실제 시간
행 수를 제한합니다. 셀·극점 개수가 아니며 입력을 재표본화하거나
시간을 연장하지 않습니다. [공통 실행기](execution.md)의 바이트·진단
제한도 계산 전에 검사합니다. 정규화는 수치 전파 조건이나 물리 수렴을
인증하지 않습니다.

재실행은 정확한 응답 타입, 전체 정규 입력, 시간·입력 파형,
노드 (시간,셀+1,2), 구간 (시간,셀,2), 4단자 배열,
분극 3종 배열 (시간,셀+1,극점,2), 모든 에너지·변화율·손실 벡터를
확인합니다. 실패는 부분 성공이 아니라 원래 예외로 전달합니다.
입력·결과는 분리된 복사본이며 일반 실행은 내부 상태를 생략하고
`analyze().to_dict(include_states=True)`로 포함할 수 있습니다.

대각·교환 대칭·비가환 행렬의 ramp/pulse 저장 재실행은 물리 API 전체
응답과 일치합니다. 1/2/0/같은/순서 변경 극점, 필수 키, 예산 실패,
오염된 배열 크기와 원래 실행 예외도 시험합니다. 단일 신호 Debye 저장 및
원래 SPD 저장과 파동 스키마 v1/v2/v3/v4/v5/v6/v7는 이 별도 종류를 거부합니다. 이 엔진 저장 계약은
웹·Windows 연결, 일반 재료 추출이나 실측 정확도를 검증한 것이 아닙니다.

[물리 API](debye_reactive_startup.md) · [단일 신호 저장](debye_startup_document.md) ·
[English](../../../../../packages/sipi/debye_reactive_startup_document.md)

`load_capacitance_f`는 외부 부하의 정확대칭 2×2 PSD 행렬이며 단위는 F입니다.
0 또는 rank-one 행렬도 허용합니다. 내부 재료 `C_inf_f_per_m` 및
`delta_C_f_per_m`의 F/m와 구분하며, 단위 추측이나 음의 고유값 수정을 하지 않습니다.
외부 전류는 (시간,2), 외부 에너지·전력은 (시간,) 형상으로 검사합니다.
선로 `line_energy`는 순간 저장과 분극 저장을 포함하고, `total_energy`는
외부 커패시터와 가지 인덕터까지 포함합니다. 저장·재실행이 이 구분을 바꾸지 않습니다.
PSD/기존 SPD/단일 신호 저장과 파동 저장 v1–7은 이 별도 종류를 거부합니다.

`load_branch_resistance_ohm`와 `load_branch_inductance_h`는 외부 가지의
Ω·H 값이며 선로 Ω/m·H/m와 구분합니다. 저항은 정확대칭 PSD,
인덕턴스는 고유값 비1e-12 초과 SPD입니다. 필수값 생략·가지 추론·
L0의 저항 변환은 하지 않습니다. 가지 전류(시간,2), 저장·변화율·저항
손실(시간,)을 검증하고 내부/외부 전력 구분을 재현합니다.
기존 정전용량 전용 저장과 파동 v1–7은 이 별도 종류를 거부합니다.

[명시적 저장 버전8](startup_waves_document.md)이 외부 직렬 RL Debye 입력을 추가합니다.
