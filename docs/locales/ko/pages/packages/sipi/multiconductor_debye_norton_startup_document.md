# 다신호 Debye 전류원 입력 저장

[English](../../../../../packages/sipi/multiconductor_debye_norton_startup_document.md) | **한국어**

`NortonMulticonductorDebyeReactiveLadderDocument`는 명시
[전류원 회로](multiconductor_debye_norton_startup.md)를
`sipi.multiconductor-debye-norton-startup/1`로 보존합니다. 파싱·정규화는 상태를
전파하지 않고 입력만 검증합니다. 물리 엔진과 수락한 정확도 범위는 그대로입니다.

```python
import numpy as np
from sipi import NortonMulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved,execute_saved
t=np.linspace(0.,4e-9,41)
doc=NortonMulticonductorDebyeReactiveLadderDocument(
    t,.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-debye-norton-startup/1'
assert len(doc.to_dict())==17 and doc.samples==41
```

루트는 정확히17개 키입니다: schema, signals, time_s, source_currents_a,
R_ohm_per_m, L_h_per_m, G_s_per_m, C_inf_f_per_m, length_m, cells,
source_shunt_conductance_s, load_resistance_ohm, delta_C_f_per_m,
relaxation_hz, load_capacitance_f, load_branch_resistance_ohm,
load_branch_inductance_h. 중복·알 수 없는 키, 비유한 JSON, 암묵적 단위 변환을
거부합니다. 전압원 스키마를 자동 이전하거나 소스 전압·저항 별칭을 허용하지
않습니다. 물리 입력 검증의 임시 저항은 저장하지 않고 명시 컨덕턴스를 저장합니다.

주입 전류는 A 단위(time,N), 첫 행0입니다. 소스 컨덕턴스는 S 단위의 유한·
비음수 N벡터이며0은 이상 전류원입니다. 원 선로·PSD 강도/손실·SPD 저장·외부
C/RL 행렬 계약을 유지합니다. 계산한 음의 PSD 고유값은 보수적으로 거부하고
pole 순서·0 열·rank 클리핑 금지를 유지합니다. 표본과 작은 양의 컨덕턴스를
그대로 보존하며 재표본화하거나 Thevenin 입력으로 변환하지 않습니다.

```python
loaded=NortonMulticonductorDebyeReactiveLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['result']==r.to_dict()
assert out['input']==loaded.to_dict()
assert r.inputs['source_shunt_conductance_s']==[0.,.02,0.]
assert 'source_resistance_ohm' not in r.inputs
assert 'source_voltages_v' not in r.inputs
np.testing.assert_array_equal(r.source_currents,r.inputs['source_currents_a'])
np.testing.assert_array_equal(r.total_energy,
    r.line_energy+r.load_capacitor_energy+r.load_branch_energy)
assert r.to_dict(include_states=True)['states_included'] is True
```

`max_evaluations`는 실제 시간 행 수이며2–10000 정수입니다. 신호·셀 개수와
별도로 물리 API를 한 번 호출하기 전에 검사합니다. 공통 실행의 입력 byte·
diagnostics 검사도 유지합니다. 반환형·정규 입력·정확한 시간/전류와 모든
상태/진단 배열 형상을 확인합니다. 원래 전파·유한 스케일 실패는 오류로
유지합니다. `to_dict()`·`dumps()`는 독립 입력 복사, 계산 배열은 읽기 전용입니다.

이상/혼합/양의 소스 컨덕턴스와 ramp/pulse 입력의 직접·저장·공통 실행 전체
상태를 대조합니다. PSD null/근영·pole, 외부 C/Rbranch의0/rank-one/근영,
SPD Lbranch와 소스·병렬부하·가지 전력 분할을 유지합니다. 입력 동일성 손상·
예산·엄격 JSON·소스 별칭 거부를 검사합니다. 기존 저장 namespace는 그대로이며
단자 파동 문서1–13버전은 새 종류를 수락하지 않습니다.

라이브러리 스키마와 공통 실행 경로의 추가입니다. 브라우저·데스크톱 엔진 갱신,
새 물리 정확도 주장, 혼합 소스·이상 전압 단락 추론, 기존 수락한 연속 선로·
관측 시간 범위 확장은 포함하지 않습니다.
