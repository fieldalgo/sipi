# 두 신호 RLGC 시작 응답 입력 저장

`CoupledRLGCLadderDocument`는 [상수 두 신호 유한 회로](coupled_startup.md)의
`sipi.coupled-rlgc-startup/1` 입력을 저장합니다. 명시적 수동 행렬과 양의 저항
종단으로 같은 초기 에너지 0의 PWL 전파를 재현합니다. 저장하면서 분산 모델을
추정하거나 물리 솔버를 바꾸지 않습니다.

```python
import numpy as np
from sipi import CoupledRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = CoupledRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[23., 37.], load_resistance=[91., 113.])
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete' and out['input']['cells'] == 32
assert out['result']['port_names'] == ['near_0', 'near_1', 'far_0', 'far_1']
assert not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert response.node_voltage.shape == (121, 33, 2)
```

## 엄격한 행렬 계약

필수 필드는 11개입니다: `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`. 버전은 정확히
`sipi.coupled-rlgc-startup/1`이며 단일선로 스키마와 바꿔 쓰지 않습니다.

RLGC는 SI 단위의 정확히 대칭인 유한 실수 2x2 행렬입니다. R/G는 음의 고유값
보정 없이 양의 준정부호, L/C는 정규화 고유값 비가 1e-12보다 큰 양의 정부호여야
합니다. 소스 전압은 `(표본 수,2)`이고 첫 행은 0이며 소스와 부하 저항은 각각
양의 유한 값 2개입니다. 0/null/무한대나 스칼라 자동 확장은 종단 표현으로
허용하지 않습니다. 시간은 0에서 시작해 엄격히 증가하며 상대 1e-10 이내 균일
간격입니다. 2..10000표본과 1..128셀을 명시합니다. PWL 보간·마지막 값 유지·
초기 에너지 0은 API 계약을 따릅니다.

로딩은 공통 제어 검증만 수행하며 상태 전파·파형·메시·field 계산을 하지 않습니다.
알 수 없는/중복 키, 미지원 버전, 비유한 값, 숫자 필드 bool과 잘못된 행렬/종단
형상을 거부합니다. JSON/사전은 중첩 행렬과 소스 배열까지 복사합니다. 제어 검증이
이후 셀 척도의 표현 가능성을 인증하지 않으므로 극단적인 underflow 입력은 정규화
뒤 전파 단계에서 올바르게 거부될 수 있습니다.

## 예산과 결과 동일성

`samples`는 시간 행 수입니다. `analyze(max_evaluations=128)`와 `execute_saved`는
솔버 전에 실제 행 수를 호출자 정수 예산 2..10000과 비교합니다. 입력이 두 개라고
두 배로 세거나 셀/동적 상태 수를 세지 않습니다. 3표본·128셀은 예산 3이 필요하고
3표본·1셀도 예산 2면 거부합니다. 셀 수를 줄이거나 다시 표본화하지 않습니다.
이 상한은 수렴·실행 시간·메모리 요구량을 보장하지 않습니다.

분석은 응답 타입, 단위 포함 원입력, 시간/소스 배열, 노드/구간 형상과 4열 포트
형상을 확인합니다. Python은 전체 읽기 전용 API 응답을 받고 공통 실행은
`sipi.execution/1`에 포트·에너지·전력의 기본 결과를 담아 내부 상태를 제외합니다.
내부 상태는 Python 결과 직렬화에서 명시적으로 요청합니다. 4개 전류 모두 선로
안 방향입니다. 기존 byte 제한 및 characteristic/mode 진단의 최상위 line 문서
제약을 유지합니다.

잘못된 입력, 예산 초과, 일반 수치 실패는 부분 성공 없이 원예외를 전달합니다.
교환 대칭/비대칭/비결합 행렬의 실제 ramp/pulse 6개 사례에서 두 소스를 구동하고
지정된 서로 다른 저항 종단을 유지한 내부 상태와 공통 출력의 동일성을 검증합니다.
엄격 입력·중첩 복사·무전파 파싱·실제 행 예산·결과 변조 거부·유한 척도 실패도
검사하며 실제 validator를 공통 저장 스키마 registry에 포함합니다.

기반 독립 모드 연속해·분포 ABCD·비대칭 DOP853·단일 회로 한계·에너지 기준은
바뀌지 않습니다. 임의 분산, 추가 도체, 이상/개방/단락/리액티브 종단, 일반
TDR/eye/BER나 실측 기판 정확도는 지원 주장이 아닙니다. 앱 폼 및 브라우저/Windows
검증은 엔진 JSON 지원과 별도입니다.

[결합 회로 API](coupled_startup.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/coupled_startup_document.md)
