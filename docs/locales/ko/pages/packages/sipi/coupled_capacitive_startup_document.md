# 부하 커패시턴스를 포함한 결합 시작 응답 저장

`CapacitiveRLGCLadderDocument`는 [수동 용량성 부하 API](coupled_capacitive_startup.md)를
명시적 **sipi.coupled-rlgc-startup/3**으로 저장합니다. 상수 RLGC 행렬, 도체별 혼합
저항 경계, 영 초기 상태 PWL 소스와 외부 커패시턴스를 보존하며 물리 API를 바꾸지 않습니다.

```python
import numpy as np
from sipi import CapacitiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
document = CapacitiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.coupled-rlgc-startup/3'
assert out['input']['load_resistance_ohm'] == [91., None]
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.all(response.load_capacitor_energy >= 0)
assert np.array_equal(response.total_energy, response.energy + response.load_capacitor_energy)
assert response.total_power_balance_relative_error <= 1e-10
```

## 필수 12개 필드와 명시적 v3

필드는 `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_resistance_ohm`,
`load_resistance_ohm`, `load_capacitance_f`입니다. 모두 필수이며 추가 키는 거부합니다.
마지막 필드는 **F** 단위의 정확히 대칭인 유한 실수 PSD 2x2 행렬로, 선로의 **F/m**
행렬과 별개입니다. 영행렬과 rank-one 행렬은 허용하지만 음의 고유값은 보정 없이
거부합니다. 스칼라 확장·bool·복소수·비대칭 행렬도 거부합니다.

나머지 제약은 [혼합 저장 v2](coupled_boundary_startup_document.md)를 따릅니다.
명시적 1..128셀, 0에서 시작하는 균일 2..10000 시간 행, 첫 행 0인 두 PWL 소스,
조건을 만족하는 SPD L/C와 PSD R/G, 유한 비음수 소스 저항, 비음수/null 부하입니다.
0은 이상 소스 또는 단락입니다. null은 저항 부하가 없다는 뜻이며 명시적 커패시터는
남아 있습니다.

버전은 정확히 v3여야 합니다. 커패시턴스가 0인 v3도 v3로 유지합니다. 양의 저항
전용 v1과 혼합 v2는 기존 검증과 출력 scope를 유지하며 추가 커패시턴스 키를
거부합니다. 자동 승격은 없습니다. 중복 키·미지원 버전·비유한 JSON 수·잘못된
중첩 입력을 거부합니다.

## 예산·출력·검증

로딩은 입력을 복사하고 상태 전파 없이 제어값을 검증합니다. 호출자 정수
`max_evaluations`(2..10000, 기본 128)는 저장 셀 수와 별도로 실제 시간 행을 셉니다.
3행·128셀은 예산 3에 들어가고 3행·1셀은 예산 2면 전파 전에 실패합니다. 저장 셀 수나
시간 범위를 변경하지 않습니다. 실행 중 유한 척도 오류는 원래 예외로 남으며 사전
검증이 실행 가능성을 인증하지 않습니다.

응답 타입·입력/시간/소스 동일성·노드/구간/4포트 형상·외부 커패시터 전류/에너지/전력
형상을 확인합니다. Python은 복사된 읽기 전용 전체 상태를 유지합니다. 기본 공통
실행은 내부 상태를 생략하지만 선로 내부·외부 커패시터·합계의 에너지/전력을 구분해
포함합니다. 기존 byte 제한과 진단 제약도 유지하며 계산 실패를 부분 성공으로 반환하지
않습니다.

6개 행렬/ramp/pulse와 6개 혼합 종단 사례를 직접 API·복원 분석·공통 실행으로 정확히
재현하고 영/rank-one 커패시턴스도 검사합니다. 입력 복사·무전파 파싱·예산·동일성 검사·
원래 예외·v1/v2 보존을 확인합니다. API의 독립 LC·모드 세분·비대칭 KCL·DC 정착 기준은
바뀌지 않습니다. 이 저장 계약이 임의 RLC 회로·주파수 분산·Maxwell 시간 영역 솔버·실측
정확도·브라우저/Windows 연결을 추가하지는 않습니다.

[용량성 API](coupled_capacitive_startup.md) · [혼합 v2](coupled_boundary_startup_document.md) ·
[공통 실행](execution.md) · [English](../../../../../packages/sipi/coupled_capacitive_startup_document.md)

[리액티브 저장 v4](coupled_reactive_startup_document.md)
