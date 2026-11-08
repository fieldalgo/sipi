# 다신호 Debye 외부 커패시터 입력 저장

[English](../../../../../packages/sipi/multiconductor_debye_capacitive_startup_document.md) | **한국어**

`MulticonductorDebyeCapacitiveLadderDocument`는
[외부 커패시터가 있는3·4신호 PSD Debye 회로](multiconductor_debye_capacitive_startup.md)의 명시 입력을
저장합니다. 별도 스키마는 `sipi.multiconductor-debye-capacitive-startup/1`이며
기존 문서의 허용 범위는 유지합니다. 저항 종단 PSD 문서는 새 외부 정전용량
필드를 계속 거부합니다.

```python
import numpy as np
from sipi import MulticonductorDebyeCapacitiveLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t = np.linspace(0., 4e-9, 41)
doc = MulticonductorDebyeCapacitiveLadderDocument(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 0., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, 0.]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([150., 0., 0.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12)
text = doc.dumps()
assert normalize_saved(text) == text
assert doc.to_dict()['schema'] == 'sipi.multiconductor-debye-capacitive-startup/1'
assert doc.to_dict()['schema'] in saved_schemas()
assert MulticonductorDebyeCapacitiveLadderDocument.loads(text).dumps() == text
```

정확히15키만 허용합니다: `schema`, `time_s`, `source_voltages_v`, `signals`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`, `relaxation_hz`,
`load_capacitance_f`.
R/G와 강도는0 방향·작은 양의 값을 포함해 원래 PSD 행렬의 모든 원소를
보존합니다. 외부 정전용량은 F 단위의 정확 대칭·실수 N×N PSD 행렬이며
0/rank-one/작은 양의 값을 유지하고 단위 변환을 추론하지 않습니다.
읽기/정규화는 물리 validator를 호출하지만 전파하지 않습니다.
rank 클리핑·고유벡터 변환·재샘플링·숨은 소스·pole 재정렬·버전 승격은
없습니다. 미지정/중복 키·비유한 값·잘못된 단위/형상·불리언/복소 값·유효하지
않은 물리 입력을 거부합니다.

명시한 신호3/4·선언한1–2pole·cells1–64·0에서 시작하는 균일 시간2–10000행
계약을 유지합니다. source drive는(time,signals) 형상에 첫 행0이며 양단 저항은
양의 벡터입니다. PSD 부호와 SPD L/C_inf 조건 검사는 물리 API와 같고,
특이 행렬 근처 계산 고유값이 음수일 때 보수적으로 거부하는 규칙도 유지합니다.

```python
loaded = MulticonductorDebyeCapacitiveLadderDocument.loads(text)
r = loaded.analyze(max_evaluations=41)
out = execute_saved(text, max_evaluations=41)
assert out['status'] == 'complete' and out['error'] is None
assert out['input'] == doc.to_dict() and out['result'] == r.to_dict()
assert r.voltage.shape == (41, 6)
assert r.load_capacitor_current.shape == (41,3)
np.testing.assert_array_equal(r.total_energy,r.line_energy+r.load_capacitor_energy)
assert r.inputs['load_capacitance_f']==doc.to_dict()['load_capacitance_f']
assert np.any(r.polarization_voltage[:, :, 0, 1:])
assert not np.any(r.polarization_charge[:, :, 0, 1:])
assert not np.any(r.polarization_voltage[:, :, 1])
assert r.inputs['delta_C_f_per_m'] == doc.to_dict()['delta_C_f_per_m']
assert max(r.power_balance_relative_error, r.total_power_balance_relative_error) <= 1e-10
```

`max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행 수 정수 예산
2–10000입니다. 저장 샘플 수보다 작으면 단 한 번의 엔진 호출 전에 거부하고
cell 수를 재설정하거나 시간을 자르지 않습니다. 공통 실행은 정규 입력을
보존하고 간결한 물리 결과를 반환하며 같은 예산을 사용합니다. 직접 `analyze`는
전체 읽기 전용 상태를 제공하고 `to_dict(include_states=True)`로 내보냅니다.

정확한 결과형·원래 입력값·시간·drive·모든 배열 형상을 확인합니다. 분극 축은
(time,node,pole,signal), 외부 커패시터 전류는(time,N), 에너지/전력은(time,)입니다.
line 에너지는 순간+분극 저장만, total 에너지는 외부 커패시터 저장까지 포함합니다.
far 전류는 저항과 커패시터 전류를 포함하지만 저항 손실은 Vfar²/Rload만 씁니다.
정규 null 보조 전압은 비영일 수 있지만 그 방향의
분극 전하/전류·에너지·손실은0입니다. 정확히0인 강도는0열과 pole 순서를
유지합니다. 원래 유한 범위·전파·전력 실패를 클리핑하거나 재시도하지 않습니다.

검증은 coupled/대각/RG0×ramp/pulse12개 전체 상태 재생,0/rank-one/근영 부하·
rankone 손실·null-only
소스·근영 강도0/1e-13/1e-20·one/zero/순서변경pole·50가지 결과 identity/형상
손상·외부C 입력 변조·모든 키·엄격 입력·예산·원실패를 포함합니다. 기존 strict 문서는 특이
입력을 계속 거부하며 저장 파동v1–11도 새 종류를 수락하지 않습니다.
공통 registry는 명시 스키마1개를 추가해이 추가 시점83스키마·37단면 template이고 실제
문서 fixture의 정확한 집합 일치를 유지합니다. 수치 코드·솔버·의존성·정확도
인증·파동 adapter·앱·플랫폼 지원을 추가하지 않습니다.
[공통 실행](execution.md)을 참고하세요.
