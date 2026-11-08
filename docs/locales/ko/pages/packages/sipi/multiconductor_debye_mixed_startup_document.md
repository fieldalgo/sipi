# 다신호 Debye 명시 소스 입력 저장

[English](../../../../../packages/sipi/multiconductor_debye_mixed_startup_document.md) | **한국어**

`MixedSourceMulticonductorDebyeReactiveLadderDocument`는 원래의
[명시 전압원·전류원](multiconductor_debye_mixed_startup.md)을
`sipi.multiconductor-debye-mixed-startup/1`로 보존합니다. 읽기/정규화는 상태를
전파하지 않고 검증하며, 물리 수식과 정확도 수락 범위는 바꾸지 않습니다.

```python
import numpy as np
from sipi import MixedSourceMulticonductorDebyeReactiveLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
doc=MixedSourceMulticonductorDebyeReactiveLadderDocument(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
from sipi.execution import normalize_saved,execute_saved
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-mixed-startup/1'
assert len(doc.to_dict())==16 and doc.samples==41
assert doc.to_dict()['sources']==sources
```

최상위 키는 정확히16개입니다. schema, time_s, sources, signals, R_ohm_per_m,
L_h_per_m, G_s_per_m, C_inf_f_per_m, length_m, cells, load_resistance_ohm,
delta_C_f_per_m, relaxation_hz, load_capacitance_f, load_branch_resistance_ohm,
load_branch_inductance_h를 씁니다. 중복/미지정 키·비유한 JSON·암묵적 소스
스키마 이전은 거부합니다.

각 소스의 키는 정확히3개입니다. 전압원은 `kind='voltage'`, V 단위 샘플
`voltage_v`, `series_resistance_ohm>0`을 보존합니다. 전류원은 `kind='current'`,
A 단위 샘플 `current_a`, S 단위 `shunt_conductance_s>=0`을 보존합니다.
종류는 문자열이어야 합니다. 내부 계산용 등가 전류/컨덕턴스나 검증용 임시
저항은 저장하지 않습니다. 작은 컨덕턴스와 원래 샘플을 정확히 유지하며
병렬 컨덕턴스0은 이상적 전류원입니다. 이상적 전압/단락·암묵적 저항/컨덕턴스
alias는 허용하지 않습니다.

공통 입력 검증기는 선로 PSD/강도/null·SPD 저장·외부 C/RL·선언 pole 순서·
유한 변환 규칙을 유지합니다. 읽기 중 샘플을 바꾸거나 작은 rank를 clipping하거나
전파하지 않습니다. 소스 변환 overflow나 비영 값의 underflow는 엔진 호출 전에
거부합니다.

```python
loaded=MixedSourceMulticonductorDebyeReactiveLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['result']==r.to_dict() and out['input']==loaded.to_dict()
assert r.source_units==('A','V','A') and r.inputs['sources']==sources
assert 'source_currents_a' not in r.inputs and 'source_voltages_v' not in r.inputs
assert 'source_shunt_conductance_s' not in r.inputs and 'source_resistance_ohm' not in r.inputs
np.testing.assert_allclose(r.source_power-r.source_series_resistor_loss-r.source_shunt_resistor_loss,
    np.sum(r.voltage[:,:3]*r.current[:,:3],axis=1),rtol=1e-10,atol=1e-12)
assert r.to_dict(include_states=True)['states_included'] is True
assert not r.source_values.flags.writeable
```

`max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행2–10000개를 세며,
정확히 한 번의 물리 API 호출 전에 검사합니다. 공통 실행의 입력 바이트·진단
제한도 유지합니다. 반환형·정규 typed 입력·시간/source_values·모든 상태/진단
배열 형상을 검사합니다. source_values 열은 원래 V/A 단위를 유지합니다.
기존 전파/유한 범위 실패는 오류로 전달하며 내보내기는 변경 가능한 입력과 분리됩니다.

3/4신호의 모든 전압/전류 조합과 램프/펄스에 대해 직접·저장·공통 실행의 전체
상태를 비교합니다. 엄격한 최상위/내부 키·단위·소스 종류 거부·변환·실제 예산·
소스/입력/배열 identity 손상·소스 직렬/병렬 전력·외부 C/Rbranch의0/rank/근영 값·
branch L SPD·PSD null·pole 순서를 검사합니다. 기존88스키마의 정규화 해시는
소스/설치본에서 유지하며 실제 새 fixture를 넣어 registry의 정확 집합 비교를
유지합니다(이 추가 시점89스키마·37template).

이 라이브러리 스키마는 물리 엔진이나 실패/수락된 PWL/관측시간 범위를 바꾸지
않습니다. 명시 [직접 단자 파동](multiconductor_debye_mixed_startup_waves.md)은
이제 결과형을 수락하며 저장 파동 v1–14는 이 문서 종류를 계속 거부합니다. 실측 정확도·임의 과도 보장·새 의존성·브라우저/데스크톱 엔진 업데이트·
플랫폼 연결을 추가하지 않습니다. [공통 실행](execution.md)을 참고하세요.
