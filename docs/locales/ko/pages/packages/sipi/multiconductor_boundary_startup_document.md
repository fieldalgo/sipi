# 다신호 혼합 종단 입력 저장

[English](../../../../../packages/sipi/multiconductor_boundary_startup_document.md) | **한국어**

`MixedBoundaryMulticonductorRLGCLadderDocument`는 별도
[상수 혼합 종단 회로](multiconductor_boundary_startup.md)를
`sipi.multiconductor-boundary-startup/1`로 보존합니다. 읽기·정규화는 전파 없이
검증하며 기존 양저항 스키마를 자동 승격하거나 재해석하지 않습니다.

```python
import numpy as np
from sipi import MixedBoundaryMulticonductorRLGCLadderDocument
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
doc=MixedBoundaryMulticonductorRLGCLadderDocument(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
from sipi.execution import normalize_saved,execute_saved
text=doc.dumps()
assert normalize_saved(text)==text
assert doc.to_dict()['schema']=='sipi.multiconductor-boundary-startup/1'
assert len(doc.to_dict())==12 and doc.samples==41
assert doc.to_dict()['source_resistance_ohm']==[0.,25.,0.]
assert doc.to_dict()['load_resistance_ohm']==[None,0.,75.]
```

루트12키는 schema,time_s,source_voltages_v,signals,R_ohm_per_m,L_h_per_m,
G_s_per_m,C_f_per_m,length_m,cells,source_resistance_ohm,load_resistance_ohm입니다.
소스의 유한 Rs>=0(0이상 전압)과 부하의 null=개방/0=단락/유한양수=저항을
그대로 저장합니다. 스칼라 broadcast·소스null alias·단위 추론·작은 저항 대체는
허용하지 않습니다. PSD R/G의 null·조건부 SPD L/C·signals3/4·cells1–128과
균일2–10000행/첫 행0의 PWL 계약도 유지합니다. 중복/미지정 키·비유한 JSON·
잘못된 물리 입력은 전파 전에 거부합니다.

```python
loaded=MixedBoundaryMulticonductorRLGCLadderDocument.loads(text)
r=loaded.analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==doc.to_dict() and out['result']==r.to_dict()
assert r.node_voltage.shape==(41,9,3) and r.current.shape==(41,6)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
np.testing.assert_allclose(r.energy_rate,r.line_power-r.series_loss-r.shunt_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,r.line_power+r.source_resistor_loss+r.load_resistor_loss,
    rtol=1e-10,atol=1e-12)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert not r.current.flags.writeable
```

`max_evaluations`는 cell·신호 수와 별개인 실제 시간 행을 셉니다. 작은 예산은
단 한 번의 엔진 호출 전에 실패합니다. 정확한 결과형·원래 입력·시간·소스
전압·모든 상태/진단 배열 형상을 검사합니다. 소스Rs0·부하null/0/양수를 몰래
대체할 수 없습니다. 원래 유한 범위·전파·전력 실패는 그대로 전달합니다.

1512개 종단 조합의 무전파 정규화, 양쪽 신호 수·2drive의6개 균일 종단,
혼합/대각/무손실 전체 상태 재생, 소스/부하 identity 손상, 엄격한 키·단위·
예산, 특이/근영 PSD 손실을 검사합니다. 이전90스키마의 정규화 해시는
소스/설치본에서 exact입니다. 실제 새 fixture를 넣어 registry의 정확 집합
비교를 유지합니다(이 추가 시점91스키마·37템플릿).

수치 모델과 독립 KCL·해석·명시 공간 수렴 범위는 그대로입니다. 직접 단자
파동 변환은 지원하며 저장 파동 v1–15는 별도 종류를 계속 거부합니다. field/실측 정확도·
임의 과도 보장·새 의존성·앱/플랫폼 업데이트를 추가하지 않습니다.
[공통 실행](execution.md)을 참고하세요.


[명시 혼합 종단 단자 파동](multiconductor_boundary_startup_waves.md)은 이상/개방/단락의 단자 전류·전력을 보존합니다.
