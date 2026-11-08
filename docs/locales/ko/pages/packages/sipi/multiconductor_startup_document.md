# 3·4신호 RLGC 시작 응답 입력 저장

`MulticonductorRLGCLadderDocument`는
[3·4신호 상수 RLGC 입력](multiconductor_startup.md)을
`sipi.multiconductor-rlgc-startup/1`로 저장합니다. 선언한 신호 수, 행렬,
종단 저항, 셀 수, 시간 표본과 소스 순서를 보존하며 기존 scalar/2신호
스키마를 승격하거나 신호 수를 추정하지 않습니다.

필수 루트 키는 정확히 12개입니다.
`schema`, `signals`, `time_s`, `source_voltages_v`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`. 선로의 SI 길이당 값과 종단 저항 ohm을 구분합니다.
추가·누락·중복 키, 미지원 버전, 비유한 JSON, 불리언 수치, 잘못된 행렬/소스
모양을 거부합니다. `signals`는 정수3/4여야 하며 실수나 차원 추론은 안 됩니다.

정확한 실수 대칭, SPD L/C, SPD 또는 정확히 영행렬인 R/G 및 비영행렬의
고유값 비1e-12 초과 조건을 유지합니다. 영행렬이 아닌 특이 PSD 손실,
분산과 다른 종단 모델은 이 계약 밖입니다. 정규화·검증은 입력을 복사하며
상태 전파 계산을 실행하지 않습니다.

```python
import numpy as np
from sipi import MulticonductorRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

document = MulticonductorRLGCLadderDocument(
    [0., 1e-9, 2e-9], [[0., 0., 0.], [1., -.4, .2], [1., -.4, .2]],
    signals=3, R=np.diag([20., 23., 26.]), L=np.diag([450., 470., 490.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C=np.diag([210., 220., 230.])*1e-12,
    length=.1, cells=16, source_resistance=[25., 25., 25.],
    load_resistance=[100., 100., 100.])
text = document.dumps()
assert normalize_saved(text) == text
assert document.to_dict()['schema'] == 'sipi.multiconductor-rlgc-startup/1'
assert len(document.to_dict()) == 12
```

```python
loaded = MulticonductorRLGCLadderDocument.loads(text)
r = loaded.analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert r.voltage.shape == (3, 6)
assert out['input']['signals'] == 3 and out['input']['cells'] == 16
assert not out['result']['states_included']
assert r.to_dict(include_states=True)['states_included']
```

`max_evaluations`는 실제 시간 행 수(정수2..10000)를 제한하며 신호 수와
물리 셀 수1..128 조건은 별개입니다. 기본값128은 최대128개 시간 행을
허용합니다. 예산이 부족하면 전파 전에 실패하고 셀 감소·소스 재표본화·
잘라내기를 하지 않습니다. 공통 실행은 계산 전에 입력 바이트 예산과
관련 없는 진단 요청도 검사합니다.

재실행은 정확한 응답 자료형과 저장 입력·시간·소스 일치를 요구합니다.
모든 배열 모양을 검사합니다: 소스(시간,N), 노드(시간,셀+1,N), 구간(시간,셀,N),
단자(시간,2*N), 에너지·손실·시간 진단량(시간,). 직접 결과는 복사된 읽기 전용
내부 상태까지 내보낼 수 있고 공통 실행은 기본 간결 결과를 반환합니다.
전파·유한 규모·입력 동일성 실패는 부분 성공으로 바꾸지 않습니다.

N3/4 × 결합/대각/무손실 × 램프/펄스 총12개 전체 상태의 정확 재현,
엄격 키·단위·행렬·소스·개수, 셀/시간 독립 예산, 복사, 상태/진단량 훼손,
원래 실패 전달을 검사합니다. 물리 API의 독립 모드/KCL 및 수렴 기준을
유지합니다. 기존 파동 저장v1..8은 이 새로운 종류를 거부하며 후속 파동
스키마에는 명시적6/8단자 계약이 필요합니다. 저장 지원만으로 앱·플랫폼
통합이나 실측 정확도를 주장하지 않습니다.

[공통 실행](execution.md) · [물리 API](multiconductor_startup.md)
