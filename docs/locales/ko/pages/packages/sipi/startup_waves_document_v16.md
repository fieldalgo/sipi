# 다신호 혼합 종단 단자 파동 저장

[English](../../../../../packages/sipi/startup_waves_document_v16.md) | **한국어**

명시 `StartupPortWavesDocument(..., version=16)`는 v15 종류에
[12키 혼합 종단 입력](multiconductor_boundary_startup_document.md)을 추가합니다.
기본1과 v1–15는 원래 수락 범위를 유지하며 새 종류를 자동 승격하지 않고
거부합니다. 스키마는 `sipi.startup-port-waves/16`입니다.

```python
import numpy as np
from sipi import MixedBoundaryMulticonductorRLGCLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
nested=MixedBoundaryMulticonductorRLGCLadderDocument(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
from sipi.execution import normalize_saved,execute_saved
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-boundary-startup/1'
assert len(nested.to_dict())==12 and nested.samples==41
assert nested.to_dict()['source_resistance_ohm']==[0.,25.,0.]
assert nested.to_dict()['load_resistance_ohm']==[None,0.,75.]
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=16)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/16'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

루트 키는 정확히 `schema`, `startup`, `z_ref_ohm`입니다. 내부는 지원하는
물리 문서여야 하며 재귀 파동 문서는 거부합니다. 명시 signals3/4에는6·8개
양의 실수 기준 저항이 필요하고 기존2·4단자 형상은 그대로입니다. 기준은
일정한 대각 값이며 특성·모드 임피던스를 추론하지 않습니다.

내부12키는 원래 전압 표본, Rs>=0(0이상 전압), 부하null=개방/0=단락/양수=저항을
보존합니다. PSD R/G null과 조건부 SPD L/C의 엔진 계약은 그대로입니다.
단위 추론·스칼라 broadcast·작은 저항 대체는 추가하지 않습니다. 읽기/정규화는
전파하지 않고 미지정/중복 키·비유한 값·잘못된 기준을 엔진 전에 거부합니다.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
assert out['input']['startup']['source_resistance_ohm']==[0.,25.,0.]
assert out['input']['startup']['load_resistance_ohm']==[None,0.,75.]
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.energy_rate+physical.series_loss+physical.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_array_equal(w.incident[:,3],w.reflected[:,3])
np.testing.assert_array_equal(w.incident[:,4],-w.reflected[:,4])
assert not w.incident.flags.writeable
```

near 전력에서 소스 저항 손실을 제외하고 far 전력은 부하 저항 손실의 음수입니다.
이상 전압원 단자 전류에 전체 상호 endpoint C 변위 전류를 보존합니다.
개방/단락 단자 전류를 구간 전류나 저항 alias로 대체하지 않습니다. 개방은
 a=b, 단락은 a=-b이고 단자 전력은0입니다. 단자 전력 합은 내부 에너지
변화율과 R/G 손실의 합입니다. 원래 물리/파동의 유한 범위·전파·복원 실패는
그대로 전달합니다.

`max_evaluations`는 cell/신호 수와 별개인 실제 시간 행2–10000을 셉니다.
예산 거부는 엔진1회·변환1회 전에 일어나며 기존 무손실 지연 예산의 의미도
유지합니다. 시간·V/I·기준·포트 이름·소스 종류·모든 파동 형상을 identity
검사로 보존합니다.

29종×2drive와 v1–15의 기존 정규 입력/전체 파동 해시446개를 재생합니다.
균일 종단/구동24개·1512개 종단 조합의 무전파 정규화·20개 파동 identity 손상·
엄격한 종단 벡터/단위/키·실제 예산·엔진/파동 호출 수·PSD null/근영 손실·
원래 실패를 검사합니다. 기존15 registry와 영향 없는5 method의 구문 트리를
정확히 유지하며 실제 v16 fixture로 registry 정확 집합 비교를 유지합니다
(이 추가 시점92스키마·37템플릿).

수치 엔진과 파동 수식은 그대로입니다. 물리 엔진의 독립 KCL·명시 공간/표본
수렴 범위도 유지합니다. 저장이 새 field/실측/임의 과도 정확도·FFT/TDR·
플랫폼 지원을 증명하지 않습니다. [직접 파동](multiconductor_boundary_startup_waves.md)과
[공통 실행](execution.md)을 참고하세요.
