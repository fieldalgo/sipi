# Debye 시작 응답 입력 저장

`DebyeRLGCLadderDocument`는 명시적 단일 신호
[Debye 시작 회로](debye_startup.md)를 `sipi.debye-rlgc-startup/1`로 저장합니다.
정규화는 입력을 검증하고 복사하며 상태를 전파하지 않습니다.

```python
from sipi import DebyeRLGCLadderDocument
from sipi.execution import execute_saved, normalize_saved

d = DebyeRLGCLadderDocument([0., 1e-9, 2e-9], [0., 1., 1.],
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=8, source_resistance=25., load_resistance=100.)
text = normalize_saved(d.dumps())
r = DebyeRLGCLadderDocument.loads(text).analyze(max_evaluations=3)
out = execute_saved(text, max_evaluations=3)
assert out['result'] == r.to_dict()
assert out['input'] == d.to_dict()
assert out['status'] == 'complete'
```

루트 키는 정확히 13개입니다: `schema`, `time_s`, `source_voltages_v`,
`R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`, `C_inf_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`, `delta_C_f_per_m`,
`relaxation_hz`. 모두 필수이며 추가 키·미지원 버전·중복 JSON 키·비유한
숫자는 거부합니다. 강도는 상대 유전율이 아니라 F/m입니다.
기존 `C_f_per_m`, 단위 없는 재료 변환, 암묵적 극점 맞춤이나 버전 승격은
허용하지 않습니다.

물리 API의 선언 극점 1–4개, 0 강도, 같은 주파수, 입력 순서, 셀 1–128개,
균일 시간 행 2–10000개를 그대로 보존합니다. 소스 0은 이상 전압원,
부하 0은 단락, JSON `null`은 개방입니다. 배열과 사전은 복사합니다.
입력 검증은 실제 전파 조건이나 공간·시간 수렴의 검증을 대신하지 않습니다.
실행 시 유한 수치 범위나 물리 검증 실패는 원래 예외로 전달합니다.

`max_evaluations`는 전파 전에 실제 시간 행 수를 제한하며 셀·극점 수와
별개입니다. 기본값은 128이고 정수 2–10000을 허용합니다.
입력을 재표본화하거나 셀을 줄이거나 선언 극점을 없애거나 관측 길이를
늘리지 않습니다. 공통 실행기는 입력 바이트 제한과 적용 불가능한 진단
선택도 계산 전에 검사합니다.

재실행은 정확한 응답 타입, 정규화한 물리 입력, 시간·소스 배열,
노드·구간·두 포트 크기, 분극 상태 3종의 크기, 모든 에너지·변화율·손실
벡터를 확인합니다. 입력이나 배열 크기가 달라진 결과를 성공으로 반환하지
않습니다. 일반 실행에서는 내부 배열을 생략하고 직접
`analyze().to_dict(include_states=True)`로 포함할 수 있습니다.
6종 경계의 ramp/pulse 재실행이 물리 API의 전체 상태·진단과 일치하며,
1/2/4극점·같은 극점·0 강도 요청도 시험합니다.

기존 상수 RLGC 저장 및 파동 스키마 v1/v2/v3는 이 모델을 암묵적으로
허용하지 않습니다. 이 엔진 저장 계약은 웹·Windows 연결,
일반 유전체 추출이나 실측 정확도의 검증을 뜻하지 않습니다.

[공통 실행](execution.md) · [물리 API](debye_startup.md) ·
[English](../../../../../packages/sipi/debye_startup_document.md)
