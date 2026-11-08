# 다신호 Debye 직렬 RL 단자 파동 저장

[English](../../../../../packages/sipi/startup_waves_document_v13.md) | **한국어**

명시한 `StartupPortWavesDocument(..., version=13)`은 기존 v12 종류에
[17키 다신호 Debye reactive 입력](multiconductor_debye_reactive_startup_document.md)을 추가합니다.
기본값은 버전1이며 기존 v1–12는 원래 허용 범위를 유지하고 새 종류를 자동
승격하지 않고 거부합니다. 스키마는 `sipi.startup-port-waves/13`입니다.

```python
import numpy as np
from sipi import MulticonductorDebyeReactiveLadderDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

t=np.linspace(0.,4e-9,41)
nested=MulticonductorDebyeReactiveLadderDocument(
    t,np.minimum(t/1e-9,1.)[:,None]*[1.,-.4,.2],signals=3,
    R=np.diag([20.,0.,26.]),L=np.diag([450.,480.,510.])*1e-9,
    G=np.diag([.002,.0022,0.]),C_inf=np.diag([210.,220.,230.])*1e-12,
    delta_C=np.array([np.diag([150.,0.,0.]),np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7,7e8],length=.1,cells=4,
    source_resistance=[25.]*3,load_resistance=[100.]*3,
    load_capacitance=np.diag([30.,0.,20.])*1e-12,
    load_branch_resistance=np.diag([30.,0.,40.]),
    load_branch_inductance=np.diag([180.,200.,220.])*1e-9)
text=nested.dumps()
assert normalize_saved(text)==text
assert len(nested.to_dict())==17
assert nested.to_dict()['schema']=='sipi.multiconductor-debye-reactive-startup/1'
assert nested.to_dict()['schema'] in saved_schemas()
assert MulticonductorDebyeReactiveLadderDocument.loads(text).dumps()==text
from sipi import StartupPortWavesDocument
saved=StartupPortWavesDocument(nested,z_ref=[35.,45.,55.,65.,75.,85.],version=13)
text=saved.dumps()
assert normalize_saved(text)==text
assert saved.to_dict()['schema']=='sipi.startup-port-waves/13'
assert set(saved.to_dict())=={'schema','startup','z_ref_ohm'}
assert saved.to_dict()['startup']==nested.to_dict()
```

최상위 키는 정확히 `schema`, `startup`, `z_ref_ohm`입니다. 내부에는 지원하는
물리 문서만 허용하고 다른 파동 문서는 넣을 수 없습니다. 검증된 signals3/4에
따라 양의 실수 기준 저항 6·8개를 요구하고 기존 2·4단자 종류는 원래 형상을
유지합니다. 기준 저항은 일정한 명시 대각 값이며 특성/모드 임피던스를
추론하지 않습니다. 재귀나 숨은 버전 승격은 없습니다.

내부 Cload[F]/Rbranch[ohm]는 0·rank-one·작은 양의 값을 포함하는 정확 대칭·
실수 PSD 행렬입니다. Lbranch[H]는 고유값 비가 1e-12보다 큰 SPD입니다.
선로 PSD 손실/강도·SPD L/C_inf·pole 순서·cells1–64·PWL 샘플 계약을
유지합니다. 읽기/정규화는 전파하지 않고 행렬·pole 순서·drive·샘플·기준
저항을 바꾸지 않습니다. 잘못된 내부 행렬·미지정/중복 키·비유한 수·잘못된
기준 저항은 실행 전에 실패합니다.

```python
from sipi import startup_port_waves
physical=nested.analyze(max_evaluations=41)
w=StartupPortWavesDocument.loads(text).analyze(max_evaluations=41)
out=execute_saved(text,max_evaluations=41)
assert out['status']=='complete' and out['error'] is None
assert out['input']==saved.to_dict() and out['result']==w.to_dict()
assert w.to_dict()==startup_port_waves(physical,z_ref=saved.to_dict()['z_ref_ohm']).to_dict()
np.testing.assert_allclose(w.port_power[:,3:].sum(axis=1),
    -physical.load_resistor_loss-physical.load_capacitor_power
    -physical.load_branch_energy_rate-physical.load_branch_resistor_loss,
    rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(w.port_power.sum(axis=1),
    physical.line_energy_rate+physical.series_loss+physical.shunt_loss+physical.relaxation_loss,
    rtol=1e-10,atol=1e-12)
assert not w.incident.flags.writeable
```

이 회로의 `max_evaluations`는 cell/신호/pole 수와 별개인 실제 시간 행
2–10000을 셉니다. 예산이 작으면 단 한 번의 엔진 호출과 파동 변환 전에
실패합니다. 기존 무손실 지연 예산의 의미는 유지합니다. 파동 identity 검사는
시간·단자 V/I·기준 값·포트 이름·소스 종류·모든 파동 형상을 보존합니다.

단자 전류는 양끝 모두 선로 안으로 향합니다. near 전력은 소스 저항 손실을
제외합니다. far 전력은 병렬 저항 손실·커패시터 전력·branch 인덕터 에너지
변화율·branch 저항 손실 합의 음수입니다. 전체 단자 수지에는 외부 C/L을
포함한 total이 아니라 내부 line 에너지를 씁니다. 원래 유한 범위·전파·전력
실패를 그대로 전달합니다.

23소스 종류 × 2drive 재생, v1–12의 이전 정규 입력/전체 파동 해시296개를
검증합니다. 최초 허용 버전/기본1·20개 파동 identity 손상·읽기 중 미전파·
엔진/변환 각1회·정확 예산·C/Rbranch의0/rank-one/근영 값·LbSPD·PSD null·
선언 pole·원래 실패를 검사합니다. 기존12 registry와 영향 없는5 method의
구문 트리는 정확히 유지합니다. 공통 registry의 실제 v13 fixture를 추가하며
정확 집합 비교를 유지합니다(이 추가 시점86스키마·37template).

수치 솔버나 변환식을 바꾸지 않습니다. 물리 엔진의 원래8주기 정착 실패와
별도 긴 관측시간 수락 범위도 유지합니다. 저장 기능이 정확도 인증·임의 관측
시간 보장·FFT/TDR·런타임 의존성·앱·플랫폼 연결을 추가하지 않습니다.
[단자 파동](multiconductor_debye_reactive_startup_waves.md)과
[공통 실행](execution.md)을 참고하세요.
