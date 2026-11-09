# 저장 입력과 옵션을 고정하는 실행 요청

[English](../../../../../packages/sipi/execution_request.md) · [저장 실행](execution.md)

`sipi.execution_request.SavedExecutionRequest`는 저장 JSON 원문과 공통 옵션
`max_input_bytes`, `max_evaluations`, `diagnostics`를 고정합니다. 기존 엄격한
문서 검증을 사용하며 장을 계산하지 않습니다. 일부 기존 검증은 작은 대수
계산을 수행합니다. diagnostics는 기존 최상위 선로에서만 허용하며 정렬한
튜플로 보관합니다. 모델별 평가 예산 확인은 실행할 때 유지되므로 요청 준비가
시간·메모리·플랫폼 적합성이나 모든 모델 예산 수락을 보장하지 않습니다.

`source_text`는 실행 시 입력 byte 판정에 쓸 원문이고 `input_json`은 기존 문서의
정규화 JSON입니다. 짧은 원문이 byte 한도 안에 있어도 보기 좋게 펼친 정규화
문자열은 더 클 수 있습니다. 실행은 고정한 원문·옵션을 `execute_saved`에
전달해 이 차이로 원래 입력을 거부하지 않습니다. 모델 예산을 조용히 줄이거나
계산 위치를 바꾸지 않습니다. controls와 `to_dict()`는 분리한 사본을 반환하므로
반환값을 수정해도 원요청은 바뀌지 않습니다.

`input_sha256`는 정규화 문서의 정확한 UTF-8 문자열 해시입니다. `request_id`는
schema=`sipi.execution-request/1`, 정규화 input 객체, 모든 controls를 포함한
envelope를 해시합니다. 키 정렬·공백 없는 구분자·그대로의 Unicode·비유한수 금지로
직렬화합니다. 문서 정규화 후 같은 공백·키순서 변형은 동일 identity이고,
입력이나 옵션 변경은 다른 요청으로 식별합니다. 같은 계산을 선택하는 diagnostic
순서는 정렬합니다. 수학적으로 같은 모든 모델의 JSON이 같다는 뜻은 아닙니다.

`run()`의 `sipi.execution-receipt/1` 결과는 request와 execution을 담습니다.
request는 schema/request_id/input_sha256/정규화 input/controls입니다. execution은
기존 `sipi.execution/1` 출력 그대로이며 complete/incomplete/failed, 이력·원인을
유지합니다. 실행 입력은 고정 입력과 같아야 합니다. 기존 예외는 그대로 전파하고
예외가 발생한 실행의 receipt를 만들어 내지 않습니다. 요청·receipt는 출력 계약이며
새 엔진 입력 형식을 registry에 추가하지 않습니다.

## 예제

```python
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest

document = LumpedNetworkDocument([0.0, 1e9], resistance=10.0, inductance=2e-9)
request = SavedExecutionRequest(document.dumps(), max_evaluations=128)
expected_request_id = request.request_id
receipt = request.run()
assert receipt["schema"] == "sipi.execution-receipt/1"
assert receipt["request"]["request_id"] == expected_request_id
assert receipt["request"]["input"] == document.to_dict()
assert receipt["execution"]["schema"] == "sipi.execution/1"
assert receipt["execution"]["status"] == "complete"
assert receipt["execution"]["input"] == receipt["request"]["input"]
```

## 화면·호스트가 맡을 일

해시는 의미상 입력·옵션을 식별하며 실행 회차를 구분하지 않습니다. 같은 요청을
두 번 실행하면 request_id도 같습니다. 취소·재시작·반복 실행 뒤 늦게 도착한
응답을 거절하려면 호스트가 별도 run token을 확인해야 합니다. 이 API는 프로세스,
취소, 파일, 서버, 업로드나 화면 변경을 수행하지 않습니다. 화면이 수정한 입력과
고정 요청을 비교할 기반일 뿐, 실제 오래된 응답 처리는 호스트 시험이 필요합니다.

identity는 엔진·의존성 artifact를 포함하거나 인증하지 않습니다. 재현·버전 간
캐싱 전에는 정확한 artifact 해시, 방법·설정과 검증 근거를 함께 보관해야 합니다.
개발 버전 문자열 하나로 빌드가 특정되지 않을 수 있습니다. SHA-256은 서명,
물리 정확도 인증, 브라우저나 Windows 지원 증명이 아닙니다.

## 검증

현재 registry의 모든 저장 형식이 장 계산 없이 준비됩니다. 해시 envelope를
독립 재구성하고 공백·옵션별 identity, 불변·분리 사본, Unicode byte 한도,
정규화 문자열 확장, 엄격한 입력 오류와 원모델 예산 거부를 검사합니다. 성공,
공차의 불완전 행, 역산 네 실패 단계와 원예외의 출력·원인·이력을 보존합니다.
실제 두 신호 균일 유손실 재료 패널 선로는 직접 실행 출력과 정확히 같고,
재료 해석 특성행렬 1e-10·C 1e-12·S 상호성/수동성 1e-10 이내에서 일치합니다.
재료식은 C0를 공유하므로 독립 기하 해·새 수렴 인증이 아닙니다. 기존 입력 형식과
수치 실행 코드는 바꾸지 않습니다.
