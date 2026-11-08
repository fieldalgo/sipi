# 다신호 Debye 혼합 소스 단자 파동 저장

[English](../../../../../packages/sipi/startup_waves_document_v15.md) | **한국어**

명시 `StartupPortWavesDocument(..., version=15)`는 v14 종류에
[16키 혼합 소스 입력](multiconductor_debye_mixed_startup_document.md)을 추가합니다.
기본1과 v1–14는 원래 수락 범위를 유지하며 새 종류를 자동 승격하지 않고
거부합니다. 스키마는 `sipi.startup-port-waves/15`입니다.

```python
import numpy as np
from sipi import MixedSourceMulticonductorDebyeReactiveLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t/1e-9,1.)
sources=[dict(kind='current',current_a=(.02*drive).tolist(),shunt_conductance_s=0.),
         dict(kind='voltage',voltage_v=(-.4*drive).tolist(),series_resistance_ohm=50.),
         dict(kind='current',current_a=(.004*drive).tolist(),shunt_conductance_s=.01)]
nested=MixedSourceMulticonductorDebyeReactiveLadderDocument(
    t,sources,signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
from sipi.execution import normalize_saved,execute_saved
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-mixed-startup/1'
assert len(nested.to_dict())==16 and nested.samples==41
assert nested.to_dict()['sources']==sources
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=15)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/15'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

루트 키는 정확히 `schema`, `startup`, `z_ref_ohm`입니다. 내부 입력은 지원하는
물리 문서여야 하며 재귀 파동 문서는 거부합니다. 명시 signals3/4에는6·8개
양의 실수 기준 저항이 필요하며 기존2·4단자의 형상은 그대로입니다. 기준은
일정한 대각 값이고 특성·모드 임피던스를 추론하지 않습니다.

각 소스는 원래3키를 저장합니다. 전압 종류·V 표본·양의 직렬 저항 또는
전류 종류·A 표본·음이 아닌 병렬 컨덕턴스입니다. 등가 주입 전류/컨덕턴스나
검사용 임시 저항을 저장하지 않습니다. 전류원 병렬0은 이상 전류원이며,
이상 전압·short·단위 추론·저항 alias는 계속 미지원입니다. 선로 PSD 손실/
강도/null·SPD L/C_inf·외부 C/Rbranch PSD·branch L SPD 규칙은 그대로입니다.
읽기/정규화는 전파하지 않으며 미지정/중복 키·비유한 값·잘못된 기준을 조기 거부합니다.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
assert out['input']['startup']['sources']==sources
for j,source in enumerate(sources):
    expected=(np.asarray(source['voltage_v'])-w.voltage[:,j])/source['series_resistance_ohm'] if source['kind']=='voltage' else np.asarray(source['current_a'])-source['shunt_conductance_s']*w.voltage[:,j]
    np.testing.assert_allclose(w.current[:,j],expected,rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_series_resistor_loss-physical.source_shunt_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

near 전류는 소스 종류에 따라 `(Vs-Vnear)/Rs` 또는 `Iinj-Gs*Vnear`입니다.
혼합 V/A 표본으로 단자 전류를 대체하지 않습니다. near 전력에서 전압원
직렬 손실과 전류원 병렬 손실을 모두 뺍니다. far 전력의 저항·커패시터·
branch L/R 분할과 외부 저장을 제외한 내부 line 에너지 수지를 유지합니다.
원래 유한 범위·전파·전력 실패는 그대로 전달합니다.

`max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행2–10000을 셉니다.
예산 거부는 엔진1회와 파동 변환1회 전에 일어나며 기존 무손실 지연 예산의
의미도 유지합니다. 시간·V/I·기준·포트 이름·소스 종류·모든 파동 형상을
출력 identity 검사로 보존합니다.

27종×2drive·모든24typed조합×2drive와 v1–14의 기존 정규 입력/전체 파동 해시
392개를 재생합니다.20개 identity 손상·소스 단위/키/변환 범위·실제 예산·
읽기 중 미전파·엔진/파동 각1회·외부 C/Rbranch0/rank/근영·branch L SPD·
PSD null/pole·원래 실패를 검사합니다. 기존14 registry와 영향 없는5 method의
구문 트리를 정확히 유지하며 실제 v15 fixture로 registry 정확 집합 비교를
유지합니다(이 추가 시점90스키마·37템플릿).

수치 엔진과 파동 수식은 그대로입니다. 실패한 저손실 PWL/짧은 관측 조건과
별도 감쇠 연속선로 수락 범위를 유지합니다. 저장이 임의 과도 정확도·FFT/TDR·
새 플랫폼 지원을 증명하지 않습니다. [직접 파동](multiconductor_debye_mixed_startup_waves.md)과
[공통 실행](execution.md)을 참고하세요.
