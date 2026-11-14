# 해상도 부분 실패를 보존하는 버전 있는 결과 기록

`SavedExecutionRecord(..., schema='sipi.execution-record/2')`는
`sipi.line-resolution/1`, `sipi.line-resolution/2`, `sipi.panel-resolution/1`,
`sipi.adaptive-panel-resolution/1`의 기존 부분 실패 출력을 보존합니다.
이 실행 결과는 null이 아닌 부분 평가와 `stage`, `input`, `kind`, `message`를
가진 오류를 남깁니다. 기존 버전 1 결과 기록은 이 조합을 거부했습니다.

기본 생성자는 여전히 `sipi.execution-record/1`을 만들고 원래 입력 검사 규칙을
유지합니다. 실행 출력도 그대로입니다. 부분 결과를 기록할 때 버전 2를 명시적으로
선택하며, 불러오기가 기존 기록을 자동 승격하지 않습니다. 버전 2에서도 버전 1의
일반 완료·미완료·형식 있는 오류 상태를 보존합니다.

부분 실패는 위 네 해상도 입력 스키마에서만 허용합니다. 결과에는 고정/자동 세분에
맞는 키, false인 `completed`·`accepted`, 원래 허용값, 객체 행의 평가·비교 이력이
필요합니다. 필드 실패 기록은 원래 오류와 일치해야 합니다. 자동 세분 필드 실패는
`stop_reason: field-failed`와 선택 평가 없음 상태를 보존합니다. 예산 소진은 대신
null 필드 실패, `stop_reason: budget-exhausted`, `ResolutionBudgetExceeded`,
예산 단계와 원래 요청 입력을 유지합니다. 이를 수렴이나 필드 오류로 바꾸지 않습니다.

기존 원문/요청 연결, 내용 해시, 바이트 한도, 실행 식별자와 호스트 아티팩트 선언
검사를 유지합니다. 실패 행렬·이력은 보존하는 근거이며 독립적으로 인증한 수치
결과가 아닙니다. 구조 검사가 수동 조립 영수증이나 선언한 아티팩트의 실행 사실,
물리 정확도를 인증하지 않습니다. 체크섬은 서명이 아닙니다.

불러오기와 `prepare()`는 필드·최적화를 실행하지 않습니다. `SavedProject`는 기존
기록 로더로 버전 2 기록을 보존하고 명시적으로 선택할 수 있습니다. 선택은 실패한
계산을 수락된 결과로 바꾸지 않습니다. 버전 2 기록도 엔진 요청이 아닌 출력 문서입니다.

아래 작은 완료 네트워크 예제로 같은 명시 기록 API를 확인합니다. 실제 실행에서는
호스트가 검증한 아티팩트 선언을 사용해야 하며 아래 값은 예제라고 명시한 자리표시자입니다.

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

request = SavedExecutionRequest(LumpedNetworkDocument(
    [0., 1e9], resistance=10., port_names=('input', 'output')).dumps())
receipt = request.run()
# Example-only declarations, not the hashes of any executed artifacts.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256='0' * 64)]
saved = SavedExecutionRecord(request, receipt, run_id='example:1',
    artifacts=artifacts, schema='sipi.execution-record/2')
restored = SavedExecutionRecord.loads(saved.dumps())
assert restored.receipt == receipt
assert restored.prepare().to_dict() == request.to_dict()
assert restored.to_dict()['schema'] == 'sipi.execution-record/2'
```

[English](../../../../../packages/sipi/partial_execution_record.md)
