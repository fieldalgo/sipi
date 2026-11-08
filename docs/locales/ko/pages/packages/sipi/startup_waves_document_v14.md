# 다신호 Debye 전류원 단자 파동 저장

[English](../../../../../packages/sipi/startup_waves_document_v14.md) | **한국어**

명시한 `StartupPortWavesDocument(..., version=14)`는 기존 v13 종류에
[17키 다신호 Debye 전류원 입력](multiconductor_debye_norton_startup_document.md)을 추가합니다.
기본값은 버전1이며 기존 v1–13은 원래 허용 범위를 유지하고 새 종류를 자동
승격하지 않고 거부합니다. 스키마는 `sipi.startup-port-waves/14`입니다.

```python
import numpy as np
from sipi import NortonMulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved,execute_saved
t=np.linspace(0.,4e-9,41)
nested=NortonMulticonductorDebyeReactiveLadderDocument(
    t,.02*np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_shunt_conductance=[0.,.02,0.],load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=nested.dumps()
assert normalize_saved(text)==text
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-norton-startup/1'
assert len(nested.to_dict())==17 and nested.samples==41
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=14)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/14'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

최상위 키는 정확히 `schema`, `startup`, `z_ref_ohm`입니다. 내부에는 지원하는
물리 문서만 허용하며 다른 파동 문서는 넣을 수 없습니다. 명시한 signals3/4에
따라 양의 실수 기준 저항 6·8개를 요구하고 기존 2·4단자 종류는 원래 형상을
유지합니다. 기준 저항은 일정한 명시 대각 값이며 특성/모드 임피던스를
추론하지 않습니다. 재귀나 숨은 버전 승격은 없습니다.

내부에는 주입 전류 `source_currents_a`와 유한·비음수 소스 병렬 컨덕턴스
`source_shunt_conductance_s`를 저장합니다. 컨덕턴스0은 이상적 전류원입니다.
값·선언 pole·null 방향·샘플을 보존하며 전압/저항 alias나 Thevenin 변환은
없습니다. 원래 선로 PSD 손실/강도·SPD L/C_inf·외부 C/Rbranch PSD·branch L
SPD 규칙을 유지합니다. 읽기/정규화는 전파하지 않습니다. 미지정/중복 키·
비유한 수·잘못된 기준 저항은 실행 전에 실패합니다.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
np.testing.assert_allclose(w.current[:,:3],physical.source_currents
    -physical.voltage[:,:3]*np.asarray(nested.to_dict()['source_shunt_conductance_s']),
    rtol=1e-13,atol=1e-15)
np.testing.assert_allclose(w.port_power[:,:3].sum(axis=1),
    physical.source_power-physical.source_shunt_resistor_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

near 단자 전류는 주입 전류에서 Gs*Vnear를 뺀 값입니다. near 단자 전력은
소스 병렬 저항 손실을 제외합니다. far 전력은 병렬 저항 손실·커패시터 전력·
branch 인덕터 에너지 변화율·branch 저항 손실 합의 음수입니다. 전체 단자
수지에는 외부 C/L 저장과 구별되는 내부 line 에너지를 씁니다. 원래 유한 범위·
전파·전력 실패를 그대로 전달합니다.

이 회로의 `max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행
2–10000을 셉니다. 예산이 작으면 단 한 번의 엔진 호출과 파동 변환 전에
실패합니다. 기존 무손실 지연 예산의 의미는 유지합니다. 정확한 출력 identity
검사는 시간·단자 V/I·기준 값·포트 이름·소스 종류·모든 파동 형상을 보존합니다.

25소스 종류 × 2drive 재생과 v1–13의 이전 정규 입력/전체 파동 해시342개를
검증합니다. 최초 허용 버전·기본1·20개 파동 identity 손상·읽기 중 미전파·
정확 예산·Gs의 이상적/혼합/양수/근영 값·외부 C/Rbranch의0/rank-one/근영 값·
branch L SPD·PSD null·pole·원래 실패를 검사합니다. 기존13 registry와 영향
없는5 method의 구문 트리를 정확히 유지합니다. 공통 registry에 실제 v14
fixture를 추가하며 정확 집합 비교를 유지합니다(이 추가 시점88스키마·37template).

솔버나 파동 변환식을 바꾸지 않습니다. 물리 엔진의 실패한 저손실 PWL/짧은
관측시간 조건과 별도 감쇠 연속선로 수락 범위를 유지합니다. 저장 기능이 임의
과도응답 정확도·FFT/TDR·런타임 의존성·앱/플랫폼 연결을 추가하지 않습니다.
[단자 파동](multiconductor_debye_norton_startup_waves.md)과 [공통 실행](execution.md)을 참고하세요.
