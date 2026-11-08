# 결합 Debye 시작 응답 입력 저장

`CoupledDebyeRLGCLadderDocument`는 명시적
[두 신호 Debye 회로](coupled_debye_startup.md)를
`sipi.coupled-debye-rlgc-startup/1`로 저장합니다. 물리 입력 계약으로 검증하며
상태 전파나 행렬·극점 변경을 수행하지 않습니다.

```python
import numpy as np
from sipi import CoupledDebyeRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

d = CoupledDebyeRLGCLadderDocument([0., 1e-9, 2e-9], [[0., 0.], [1., 0.], [1., 0.]],
    R=[[20., 3.], [3., 20.]], L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12, relaxation_hz=[1e9],
    length=.1, cells=8, source_resistance=[25., 25.], load_resistance=[100., 100.])
text = normalize_saved(d.dumps())
r = CoupledDebyeRLGCLadderDocument.loads(text).analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert out['input'] == d.to_dict() and out['status'] == 'complete'
assert r.polarization_charge.shape == (3, 9, 1, 2)
```

필수 루트 키는 정확히 13개입니다: `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`,
`relaxation_hz`. 단일 신호 스키마와 달리 R/L/G/C_inf는 2×2 행렬,
강도는 (극점,2,2), 입력은 (시간,2), 각 저항 벡터는 (2,) 형상입니다.
추가 키·미지원 버전·중복 키·잘못된 단위·비유한 값 및 암묵적인
스칼라→행렬 변환을 거부합니다.

정확한 대칭, R/G 준정부호, L/C_inf 정부호 검사를 유지합니다.
1–2개 강도 행렬은 정규화 고유값 비율이 1e-12보다 큰 정부호 또는 정확히
0이어야 합니다. 순서·0 강도·같은 양의 완화 주파수를 보존합니다.
저장한다고 일반 특이 강도나 이상·개방·단락 종단을 허용하지 않습니다.

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
파동 스키마 v1/v2/v3/v4는 이 별도 종류를 거부합니다. 이 엔진 저장 계약은
웹·Windows 연결, 일반 재료 추출이나 실측 정확도를 검증한 것이 아닙니다.

[물리 API](coupled_debye_startup.md) · [단일 신호 저장](debye_startup_document.md) ·
[English](../../../../../packages/sipi/coupled_debye_startup_document.md)

[명시적 저장 버전5](startup_waves_document.md)가 결합 Debye 입력을 추가합니다.
