# 다신호 Debye 직렬 RL 입력 저장

[English](../../../../../packages/sipi/multiconductor_debye_reactive_startup_document.md) | **한국어**

`MulticonductorDebyeReactiveLadderDocument`는
[외부 C와 직렬 RL이 있는 3·4신호 Debye 회로](multiconductor_debye_reactive_startup.md)의 명시 입력을 저장합니다.
별도 스키마는 `sipi.multiconductor-debye-reactive-startup/1`입니다.
기존 커패시터 문서는 새 branch 필드를 계속 거부합니다.

```python
import numpy as np
from sipi import MulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t=np.linspace(0.,4e-9,41)
doc=MulticonductorDebyeReactiveLadderDocument(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=doc.dumps()
assert normalize_saved(text)==text
assert len(doc.to_dict())==17
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-reactive-startup/1'
assert doc.to_dict()['schema'] in saved_schemas()
assert MulticonductorDebyeReactiveLadderDocument.loads(text).dumps()==text
```

정확히 17개 키만 허용합니다:
`schema`, `time_s`, `source_voltages_v`, `signals`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`,
`relaxation_hz`, `load_capacitance_f`, `load_branch_resistance_ohm`,
`load_branch_inductance_h`.

외부 정전용량은 F, branch 저항은 ohm, 인덕턴스는 H 단위입니다.
외부 행렬은 모두 실수·정확 대칭 N×N입니다. Cload/Rbranch는 0·rank-one·
작은 양의 값을 포함하는 PSD, Lbranch는 정규화 고유값 비가 1e-12보다 큰
SPD입니다. 읽기/정규화는 원래 물리 validator를 사용하지만 전파하지 않습니다.
단위·누락 branch·대칭 복구·rank 임계값·pole 순서 변경·재샘플링·버전 승격을
추론하지 않습니다. 미지정/중복 키·비유한 수·유효하지 않은 입력은 거부합니다.

신호 3/4, cells 1–64, 선언한 pole 1–2개, 0에서 시작하는 균일 시간
2–10000행 계약을 유지합니다. drive는 (time,N)에 첫 행 0이며 양단 저항은
양의 벡터입니다. 선로 R/G/강도는 PSD, L/C_inf는 SPD입니다. 특이 행렬
근처를 포함해 계산한 PSD 고유값이 음수이면 보수적으로 거부합니다.

```python
r=MulticonductorDebyeReactiveLadderDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==doc.to_dict() and out['result']==r.to_dict()
assert r.voltage.shape==(41,6) and r.load_branch_current.shape==(41,3)
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
np.testing.assert_allclose(r.current[:,3:],
    -r.voltage[:,3:]/100-r.load_capacitor_current-r.load_branch_current,
    rtol=1e-10,atol=1e-12)
for key in ['load_capacitance_f','load_branch_resistance_ohm','load_branch_inductance_h']:
    assert r.inputs[key]==doc.to_dict()[key]
assert not np.any(r.polarization_charge[:,:,0,1:])
assert not np.any(r.polarization_voltage[:,:,1])
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
```

`max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행 수입니다.
정수 예산 2–10000이 저장 샘플보다 작으면 엔진 호출 전에 거부합니다.
시간을 자르거나 cell 수를 줄이지 않습니다. 공통 실행은 정규 입력을 보존하고
간결한 결과를 반환합니다. 직접 `analyze`는 읽기 전용 상태를 반환하며
`to_dict(include_states=True)`로 전체 상태를 명시적으로 내보냅니다.

정확한 결과형·입력·시간·drive·모든 배열 형상을 확인합니다. 외부 branch와
커패시터 전류는 (time,N), 에너지/변화율/손실은 (time,)입니다. line 에너지는
내부 순간·분극 저장, total 에너지는 외부 C와 branch L까지 포함합니다.
병렬 저항과 branch 저항의 손실을 구분하고 far 전류는 세 부하 경로를 모두
포함합니다. 선언한 0 강도는 0열과 pole 순서를 유지합니다. null 방향 보조
전압은 비영일 수 있지만 분극 에너지는 0입니다. 원래 유한 범위·전파·전력
실패를 그대로 전달합니다.

coupled/대각/RG0 × ramp/pulse 12개 전체 상태 재생, 0/rank-one/근영
C/Rbranch, SPD Lbranch 경계, PSD 선로 손실·null-only 소스·근영/순서변경
강도, 58개 결과 identity/형상 손상, 외부 행렬 변조·복사·모든 키·예산을
검사합니다. 저장 파동 v1–12는 이 종류를 계속 거부합니다. 공통 registry에
스키마 하나를 추가해 이 추가 시점 85스키마·37단면 template이며, 실제 새
문서 fixture와 기존 정확 집합 검사를 유지합니다. 수치 엔진이나 정확도 근거를
추가하지 않습니다. 물리 API의 원래 8주기 정착 실패와 별도 긴 관측시간 수락
범위는 그대로이며 저장 기능이 이를 확대하지 않습니다. 새 의존성·파동 adapter·
앱·플랫폼 지원을 추론하지 않습니다. [공통 실행](execution.md)을 참고하세요.
