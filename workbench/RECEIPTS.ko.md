# 실행 결과의 입력 연결

공유 Python adapter의 `saved-receipt`는 저장 입력 원문 `text`와 선택 사항인
`controls`를 받아 `engine`과 기존 `sipi.execution-receipt/1` 봉투를 반환합니다.
호스트 연결용 계약이며, 입력 프로젝트 UI에는 아직 새 계산 결과를 붙이지 않습니다.

controls를 지정하면 `max_input_bytes`, `max_evaluations`, `diagnostics` 세 키가
모두 있어야 합니다. 기본값은 204800, 128, `[]`입니다. 입력 원문은 200 KiB,
공백 없는 UTF-8 JSON 요청 전체는 256 KiB까지 받습니다. 더 큰 입력 한도를
선언해도 요청 식별에는 그 값을 보존하며, 별도 전달 한도를 적용합니다.
평가 한도 128 초과는 줄이지 않고 거부합니다. 엔진의 모델별 실행 허용 검사와
선로 전용 diagnostics 제한은 유지됩니다. 준비 성공이 계산 성공을 뜻하지 않습니다.

receipt는 정규화한 입력과 모든 설정을 결과에 연결합니다. 표시 형식만 바꾸면
요청 식별자는 같지만 설정이 바뀌면 달라집니다. 실패한 역산과 일부 실패한 연구는
상태/이력을 유지합니다. 다른 예외는 기존 호스트 오류 경로로 전달합니다.
`saved-analyze`는 바뀌지 않습니다.

같은 요청을 반복 실행하면 의미상 식별자도 같습니다. 호스트는 별도 실행 ID,
늦은 응답 거부, 실제 배포물 출처를 갖춘 뒤 프로젝트 기록을 만들어야 합니다.
receipt나 `engine` 버전만으로 wheel 식별 또는 물리 정확도를 입증하지 않습니다.
이 작업은 파일을 쓰거나 기록을 붙이지 않습니다. JavaScript를 거칠 때 프로젝트와
기록 원문을 보존하세요. 숫자 재직렬화는 `0.0`을 `0`으로 바꾸는 경우처럼
digest를 바꿀 수 있습니다.

다음 엔진 예제는 같은 기본 receipt 계약을 보여 줍니다. adapter에는 위의
추가 전달 한도도 적용합니다.

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
request = SavedExecutionRequest(text, max_input_bytes=204800,
                               max_evaluations=128, diagnostics=[])
receipt = request.run()
assert receipt['request']['request_id'] == request.request_id
assert receipt['execution']['status'] == 'complete'
```

[프로젝트 전달](PROJECTS.ko.md) · [English](RECEIPTS.md)
