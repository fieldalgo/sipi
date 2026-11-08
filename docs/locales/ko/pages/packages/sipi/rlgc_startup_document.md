# 유한 RLGC 시작 응답 입력 저장

`RLGCLadderDocument`는 `sipi.rlgc-startup/1`을 저장하고
[유한 수동 회로 API](rlgc_startup.md)를 공통 실행에 연결합니다. 명시적 셀 수,
균일 시간 표본, 구간별 선형 소스와 초기 에너지 0을 보존합니다. 상수 단일
RLGC 물리 모델과 수락 기준은 바뀌지 않습니다.

```python
import numpy as np
from sipi import RLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
document = RLGCLadderDocument(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C=200e-12, length=.1, cells=128,
    source_resistance=25., load_resistance=100.)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete' and out['input']['cells'] == 128
assert out['result']['power_balance_relative_error'] <= 1e-10
assert not out['result']['states_included']
assert 'node_voltage_v' not in out['result']
response = document.analyze(max_evaluations=121)
assert response.node_voltage.shape == (121, 129)
```

## 엄격한 저장 계약

필수 필드는 11개입니다: `schema`, `time_s`, `source_voltages_v`, `R_ohm_per_m`,
`L_h_per_m`, `G_s_per_m`, `C_f_per_m`, `length_m`, `cells`,
`source_resistance_ohm`, `load_resistance_ohm`. schema는 정확히
`sipi.rlgc-startup/1`입니다. 알 수 없는 키/버전, 중복 키, 비유한 숫자와 숫자
필드의 bool은 거부합니다. 부하 null은 명시적 개방, 0은 단락이며 소스 저항 0은
이상 전압원입니다.

불러올 때 API 제어 검증을 공유하며 상태 전파·파형·메시·field 계산은 하지
않습니다. 시간은 0에서 시작하는 2..10000표본으로 엄격히 증가하고 상대 1e-10
이내 균일 간격입니다. 소스는 같은 형상과 첫 값 0이며 선형 보간 후 마지막 값을
유지합니다. R/G는 비음수, L/C/길이는 양수, 저항은 비음수인 유한 SI 실수입니다.
정규화 문자열과 사전은 호출자 배열에서 독립적입니다. 이 사전 검증이 극단적인
셀 척도·행렬 계수·상태의 표현 가능성을 보장하지 않으므로 실행 시 유한성/에너지
검사는 계속 적용됩니다.

## 표본 예산과 셀 수 보존

`samples`는 실제 출력 시간 표본 수입니다. `analyze(max_evaluations=128)`와
`execute_saved`는 이 수가 호출자 정수 예산 2..10000 이내인지 **상태 전파 전**
확인합니다. `cells`는 별도 명시적 1..256 정수입니다. 예제는 예산 121로 128셀을
그대로 계산합니다. 3표본·256셀은 예산 3이 필요하고, 3표본·1셀도 예산 2면
거부합니다. 시간이나 셀을 자동 축소하거나 다시 표본화하지 않습니다. 이 예산은
상태 수, 독립 적분기의 내부 step 수, 실행 시간이나 메모리가 아니며 수렴을
보장하지 않습니다.

`analyze()`는 전체 읽기 전용 API 응답을 반환하고 저장 입력, 시간/소스 배열,
노드/구간 셀 형상을 확인합니다. 공통 실행은 `sipi.execution/1`에 기본 API
사전(입력·포트·에너지·전력)을 담고 내부 상태 배열은 제외합니다. Python에서는
`response.to_dict(include_states=True)`로 명시적으로 내부 상태를 저장할 수
있습니다. 양쪽 포트 전류는 선로 안 방향, 구간 전류는 소스에서 부하 방향입니다.

기존 byte 제한과 진단 제약을 유지합니다. characteristic/mode 진단은 최상위
transmission/volume line에만 적용됩니다. 잘못된 입력, 예산 초과, 일반 수치
실패는 부분 성공 없이 원래 예외를 전달합니다. 극단적으로 작은 셀 척도의 입력은
정규화에 성공해도 분석 중 올바르게 거부될 수 있습니다.

엄격 파싱·복사·무전파 로딩·실제 표본 예산과 셀 보존·실행 실패·결과 동일성을
검증합니다. 이상/저항 소스와 단락/개방/저항 부하의 12개 유손실 ramp/pulse에서
직접 API 상태 및 공통 출력이 정확히 같습니다. 기존 독립 RL/LC, DOP853, 분포
선로 및 공간 세분 기준은 그대로이며 기록된 이상 소스/개방 128셀 실패와 256셀
수락도 유지합니다. 실제 validator를 공통 스키마 registry에 포함합니다.

분산/결합 선로, 리액티브 외부 부하, 일반 TDR/eye/BER나 실측 기판 정확도로
모델을 확장하지 않습니다. 저장 스키마만으로 앱 폼이나 브라우저/Windows 연결이
검증되는 것은 아닙니다.

[유한 회로 API](rlgc_startup.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/rlgc_startup_document.md)
