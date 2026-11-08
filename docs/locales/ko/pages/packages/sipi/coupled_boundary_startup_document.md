# 혼합 경계 두 신호 시작 응답 저장

`MixedBoundaryRLGCLadderDocument`는 [명시적 혼합 종단](coupled_boundary_startup.md)의
**sipi.coupled-rlgc-startup/2**를 저장합니다. v2는 도체별 이상/저항 소스와
단락/개방/저항 부하를 지원합니다. 기존 [v1 문서](coupled_startup_document.md)는
양의 저항 전용이며 정규화가 버전이나 물리 API를 자동 변경하지 않습니다.

```python
import numpy as np
from sipi import MixedBoundaryRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = MixedBoundaryRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[0., None])
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/2'
assert out['input']['load_resistance_ohm'] == [0., None]
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.all(response.voltage[:, 2] == 0) and np.all(response.current[:, 3] == 0)
```

## 필수 11개 필드와 명시적 v2

필드는 `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`입니다. 모두 필수이며 이 클래스의 버전은 정확히
`sipi.coupled-rlgc-startup/2`여야 합니다.

API와 같은 core 제약을 사용합니다. R/G는 정확히 대칭인 실수 2x2 PSD, L/C는
고유값 비가 1e-12보다 큰 SPD, 길이는 양수, 명시적 1..128셀, 0에서 시작하는
균일 2..10000 시간 표본과 첫 행 0인 `(표본 수,2)` PWL 소스입니다. 초기 에너지나
impulse를 추정하지 않습니다. 양쪽 경계 벡터는 각각 명시적 2개 항목입니다.
소스는 유한 비음수 저항이며 0은 이상 소스입니다. 각 부하는 유한 비음수 저항,
0은 단락, JSON null은 개방입니다. 무한대·스칼라 확장·숫자 bool·알 수 없는/중복
키·미지원 버전·잘못된 형상/행렬은 거부합니다. SI 단위 및 오른쪽 기울기/마지막
값 유지의 전류 규약은 혼합 API를 따릅니다.

양의 저항만 가진 입력도 v2로 명시해 저장할 수 있으며 혼합 API scope를 유지합니다.
기존 v1을 변환하는 것은 아닙니다. v2 클래스는 v1 payload의 버전을 거부하지만
공통 정규화는 기존 validator로 유효 v1을 계속 지원합니다. v1에 0/null 종단을
넣으면 거부합니다. 부하 null과 0을 서로 바꾸지 않고 보존합니다.

## 파싱·예산·실행

로딩은 공통 혼합 경계 제어 검증을 호출하며 상태 전파·메시·파형 작업을 하지
않습니다. 문자열과 중첩 배열/행렬은 복사합니다. 실행 시 질량 행렬의 표현 가능성을
사전 인증하지 않으므로 극단적 underflow는 분석 중 일반 수치 오류로 남습니다.

`samples`는 실제 시간 행 수입니다. `analyze(max_evaluations=128)`와 공통 실행은
전파 전에 호출자 정수 예산 2..10000을 초과하는 행 수를 거부합니다. 두 입력이라고
두 배로 세거나 셀/상태 수로 바꾸지 않습니다. 3행·128셀은 예산 3, 3행·1셀도
예산 2면 거부합니다. 셀 수·파형·시간 범위를 자동 축소하지 않습니다. 이 제어는
정확도·실행 시간·메모리 인증이 아닙니다.

응답 타입·원입력·시간/소스 배열·노드/구간/4포트 형상을 확인합니다. Python은 전체
읽기 전용 응답을 받고 공통 `sipi.execution/1`은 입력·포트·에너지/전력을 담습니다.
내부 상태는 기본 공통 출력에 없고 Python 응답에서 명시적으로 직렬화합니다.
기존 byte/진단 제약과 원래 수치 예외를 유지하며 전파 실패를 부분 성공으로
포장하지 않습니다.

엄격 중첩 파싱·무계산 로딩·예산·동일성 검사·유한 척도 실패·v1 보존, 6개
행렬/ramp/pulse의 전체 상태 재현 및 6개 도체별 종단 조합을 검사합니다.
직접 API·복원 분석·기본 공통 출력이 정확히 일치합니다. 기반 결합 RL/Schur
용량 해석·모드 세분·독립 KCL/DOP853 기준은 바뀌지 않습니다. 리액티브 부하,
임의 분산·추가 도체·일반 TDR/eye/BER·실측 정확도·자동 브라우저/Windows 연결을
추가하는 저장 버전은 아닙니다.

[혼합 경계 API](coupled_boundary_startup.md) · [양의 저항 v1](coupled_startup_document.md) ·
[공통 실행](execution.md) · [English](../../../../../packages/sipi/coupled_boundary_startup_document.md)

[용량성 저장 v3](coupled_capacitive_startup_document.md)
