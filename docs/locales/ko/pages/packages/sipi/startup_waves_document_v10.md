# 다신호 Debye 단자 파동 저장

[English](../../../../../packages/sipi/startup_waves_document_v10.md) | **한국어**

명시한 `StartupPortWavesDocument(..., version=10)`이 중첩 입력에
`sipi.multiconductor-debye-rlgc-startup/1`을 추가합니다. 최상위 키는
`schema`, `startup`, `z_ref_ohm` 세 개입니다. 기본 버전1과 기존 버전1–9의
허용 종류·정규 입력·결과를 유지하며 새 종류를 자동 승격하지 않고 거부합니다.

```python
import numpy as np
from sipi import MulticonductorDebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved, normalize_saved

t = np.linspace(0., 4e-9, 41)
startup = MulticonductorDebyeRLGCLadderDocument(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 23., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 143., 156.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
request = StartupPortWavesDocument(
    startup, z_ref=[35., 45., 55., 65., 75., 85.], version=10)
text = request.dumps()
assert normalize_saved(text) == text
assert request.to_dict()['schema'] == 'sipi.startup-port-waves/10'
assert request.to_dict()['startup'] == startup.to_dict()
```

중첩 입력의 명시한 `signals`는3 또는4이며 양의 유한 실수 기준 저항6개 또는
8개가 필요합니다. 단자 순서는 near N개 뒤 far N개이고 양단 전류는 선로
안으로 들어갑니다. 스칼라/복소 기준, 포트 수 추측, 재귀 파동 문서,
중복/미지정 키와 비유한 값은 거부합니다.
[물리 회로 저장](multiconductor_debye_startup_document.md)의14키·선언한1–2pole·
SPD 또는0 강도·양의 저항 종단·cells1–64 계약을 유지합니다. 읽기/정규화는
전파하지 않고 시간 샘플·pole 순서·강도·기준 저항을 바꾸지 않습니다.

```python
from sipi import startup_port_waves
out = execute_saved(text, max_evaluations=41)
expected = startup_port_waves(startup.analyze(max_evaluations=41),
                             z_ref=[35., 45., 55., 65., 75., 85.]).to_dict()
assert out['status'] == 'complete' and out['error'] is None
assert out['input'] == request.to_dict() and out['result'] == expected
assert out['result']['source_kind'] == 'MulticonductorDebyeRLGCLadderResponse'
assert len(out['result']['incident_sqrt_w'][0]) == 6
```

해석은 물리 엔진과 [파동 변환](multiconductor_debye_startup_waves.md)을 각각
한 번 호출합니다. 예산은 cell/신호 수와 별개인 실제 시간 행 수2–10000이며
무손실 중첩 입력은 원래 지연 항 예산을 유지합니다. 부족한 예산은 전파 전에
거부합니다. 기존 결과형·시간·V/I·기준 저항·단자 이름·source_kind·파동 배열
형상 검사를 유지합니다. 원래 물리/파동 복원 실패를 클리핑하거나 재시도하지
않습니다. 전체 단자 전력은 순간/분극 에너지 변화율과 직렬·병렬·완화 손실을
포함합니다.

17소스 종류×ramp/pulse를 직접/저장/공통 실행으로 재생하며 허용되는 모든
기존 버전의 결과를 보존합니다. 수정 전 정규 입력/전체 파동182건의 해시를
소스·설치본에서 정확히 비교합니다. one/zero/순서변경pole·엔진/변환1회·
엄격한 중첩 입력·예산·출력 identity 손상을 검사합니다. 공통 registry는
80스키마·37단면 template이며 전체 스키마 fixture에 실제 버전10 문서를
추가하고 정확한 집합 일치를 유지합니다. 수치 엔진/파동 식과 기존 수치 시험은
변경하지 않습니다. 새 물리 모델·정확도 인증·TDR/FFT·앱·플랫폼 연결을
추가하지 않습니다. [전체 저장 파동 버전](startup_waves_document.md)을 참고하세요.
