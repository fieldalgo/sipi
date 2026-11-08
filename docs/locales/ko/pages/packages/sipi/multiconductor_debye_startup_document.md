# 다신호 Debye 시작 응답 저장

[English](../../../../../packages/sipi/multiconductor_debye_startup_document.md) | **한국어**

`MulticonductorDebyeRLGCLadderDocument`는 명시한
[3·4신호 Debye 회로](multiconductor_debye_startup.md)를
`sipi.multiconductor-debye-rlgc-startup/1`로 저장합니다. 생성·읽기·정규화는
입력만 검사하고 상태 전파를 실행하지 않습니다. 신호 수·재료·pole·소스·기준·
셀 수를 추론하지 않습니다.

```python
import numpy as np
from sipi import MulticonductorDebyeRLGCLadderDocument
from sipi.execution import normalize_saved

t = np.linspace(0., 4e-9, 41)
arguments = dict(time=t,
    source_voltages=np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2],
    signals=3, R=np.diag([20., 23., 26.]),
    L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024]),
    C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 143., 156.]), np.zeros((3, 3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
document = MulticonductorDebyeRLGCLadderDocument(**arguments)
text = document.dumps()
assert document.to_dict()['schema'] == 'sipi.multiconductor-debye-rlgc-startup/1'
assert normalize_saved(text) == text
assert MulticonductorDebyeRLGCLadderDocument.loads(text).dumps() == text
```

정확히14키가 필요합니다: `schema`, `signals`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `delta_C_f_per_m`,
`relaxation_hz`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`. 누락/미지 키·다른 단위·중복 JSON 키·비유한 수·미지원
버전은 거부합니다. 스칼라/목록 차원·정확한 대칭·SPD또는0 제약·첫 소스 행0·
양의 유한한 pole/저항 등 직접 API의 조건을 유지합니다.

`signals`는3 또는4를 명시하고 cells1..64,선언pole1·2개,0에서 시작하는 균일
시간2..10000행을 요구합니다. `analyze(max_evaluations=...)`는 실제 시간 행
수를 세며 셀·신호·활성 상태 수와 구분합니다. 예산은 정수2..10000(기본128)이며
초과하면 전파 전에 실패합니다. 저장한 셀 수와 시간값은 바꾸지 않습니다.
공통 실행기는 기존 입력 바이트 한도와 무관한 진단 선택도 계산 전에 검사합니다.
이 한도는 수렴·실행 시간·메모리를 보장하지 않습니다.

```python
from sipi import multiconductor_debye_rlgc_ladder_response
from sipi.execution import execute_saved

direct = multiconductor_debye_rlgc_ladder_response(**arguments)
replayed = document.analyze(max_evaluations=41)
assert replayed.to_dict(include_states=True) == direct.to_dict(include_states=True)
execution = execute_saved(text, max_evaluations=41)
assert execution['status'] == 'complete'
assert execution['result'] == direct.to_dict()
assert execution['input']['cells'] == 4
assert not replayed.polarization_charge[:, :, 1].any()
```

실행은 기존 엔진을 한 번 호출합니다. 반환 전 정확한 결과형·정규화한 모든 입력·
시간·소스 샘플을 검사합니다. 소스/노드/구간/단자 배열은 선언한 차원이어야
하고 분극 배열3개는(time,node,pole,signal)로0강도에도 선언pole 수를 유지합니다.
나머지 진단 배열은 시간당 값 하나입니다. 직접 결과는 복사된 읽기 전용이고
정규화/내보낸 사전은 독립적입니다. 원래 수치/전파 오류는 그대로 전달합니다.
솔버 결과를 보정하거나 정확도를 추론하거나 실패를 부분 성공으로 바꾸지 않습니다.

[공통 저장 실행](execution.md)은 기존 `sipi.execution/1` envelope와 엔진의
상태 없는 결과 내보내기를 반환합니다. 직접 `analyze` 결과의 `to_dict`에서는
전체 상태를 요청할 수 있습니다. 결과 내보내기와 실행 가능한 저장 요청은
구분합니다. 기존 시작 파동v1–9와 이전 회로 저장 종류에 새 문서를 자동 수락하지
않습니다.

검증은3/4신호·결합/대각/RG0·ramp/pulse의 직접/저장/공통 전체 상태 일치,
one/zero/순서변경pole,필수 키 전체·엄격한 행렬/pole/개수/단위·중복/비유한
입력,엔진1회 호출·전파 전 행/바이트/진단 예산,모든 상태/진단shape 손상과 원래
런타임 오류를 포함합니다. 수치 근거는 기존
[독립 KCL·모드·수렴 검증](multiconductor_debye_startup.md)을 유지합니다.
수치 커널·허용 오차·런타임 의존성·물리 모델·앱·플랫폼 지원은 바꾸지 않습니다.
