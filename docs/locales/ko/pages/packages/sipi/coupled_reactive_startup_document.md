# 명시적 C·RL 부하를 포함한 결합 시작 응답 저장

`ReactiveRLGCLadderDocument`는 [외부 직렬 RL 분기 API](coupled_reactive_startup.md)를
**sipi.coupled-rlgc-startup/4**로 저장합니다. 물리 검증을 재사용하며 행렬·시간 격자·
경계 입력을 정확히 보존합니다.

```python
import numpy as np
from sipi import ReactiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = ReactiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/4'
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.array_equal(response.total_energy,
    response.energy + response.load_capacitor_energy + response.load_branch_energy)
assert response.total_power_balance_relative_error <= 1e-10
```

## 필수 14개 키

필수 키는 `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`, `load_capacitance_f`, `load_branch_resistance_ohm`,
`load_branch_inductance_h`입니다. 알 수 없는/중복 키·비유한 JSON 수·미지원 버전을
거부하며 행렬을 추정하지 않습니다.

선로·파형·혼합 소스/부하·외부 C 제약은 [용량성 저장 v3](coupled_capacitive_startup_document.md)와
같습니다. 추가 분기 R[ohm]는 유한 실수 정확 대칭 PSD2x2이며 영/rank-one을 허용하되
음의 고유값을 보정하지 않습니다. 분기 L[H]은 고유값 비>1e-12인 유한 실수 정확 대칭
SPD2x2입니다. 특이/영 L·스칼라 확장·bool/복소수·비대칭을 거부합니다. 초기 전류 0인
직렬 R/L 분기가 외부 C·도체별 종단과 병렬인 회로이며 임의 RLC netlist가 아닙니다.
집중 C[F]/L[H]는 선로 C[F/m]/L[H/m]와 구별합니다.

v1–3은 기존 검증과 출력 scope를 유지하고 추가 분기 키 각각을 거부합니다. 자동
승격하지 않습니다. v4 클래스는 이전 payload를 거부하며 명시적 C/Rbranch가 0인
경우도 양의 Lbranch를 요구하는 v4로 유지합니다.

## 검증·예산·응답

파싱/정규화는 중첩 입력을 복사하고 상태 전파 없이 검증합니다. `samples`는 실제 시간
행 수입니다. 정수 `max_evaluations`(2..10000, 기본128)는 저장 1..128셀·두 도체·추가 전류
상태 수와 별개입니다. 3행·128셀은 예산3에 들어가며 3행·1셀도 예산2면 전파 전에
거부합니다. 시간 범위나 셀 수를 바꾸지 않으며 실행 중 유한 척도 오류는 원래 예외로
남습니다.

전체 입력/시간/소스 동일성·노드/구간/4포트 형상·커패시터/분기 전류와 에너지/전력/손실
형상을 확인합니다. Python은 복사된 읽기 전용 전체 상태를 보존합니다. 공통 실행은
기본적으로 내부 선로 상태를 생략하지만 선로·외부 커패시터·분기 에너지/손실과 합계
보존 검사를 구분해 유지합니다. byte/진단 제약은 그대로이며 수치 실패를 부분 성공으로
포장하지 않습니다.

6개 행렬/ramp/pulse와 6개 혼합 경계의 전체 상태 재현, 영/rank-one 부하, 중첩 복사·
무계산 로딩·예산·잘못된 출력·이전 버전 보존을 검사합니다. 물리 L-C-L·모드 세분·독립
KCL·전력 기준은 변경하지 않습니다. 이 저장 형식이 검증된 API를 넘어 물리 topology·
분산·실측 정확도·브라우저/Windows 연결을 추가하지는 않습니다.

[리액티브 API](coupled_reactive_startup.md) · [용량성 v3](coupled_capacitive_startup_document.md) ·
[공통 실행](execution.md) · [English](../../../../../packages/sipi/coupled_reactive_startup_document.md)
