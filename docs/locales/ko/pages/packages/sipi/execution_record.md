# 실행 결과 저장

[English](../../../../../packages/sipi/execution_record.md) · [불변 요청](execution_request.md) · [공통 실행](execution.md) · [A/B 프로젝트](project.md)

`SavedExecutionRecord`는 실행 영수증 하나를 정확한 원입력 문자열, 호스트 실행
식별자, 선언된 빌드 산출물 정보와 함께 보관합니다. 읽거나 준비할 때 계산을 실행하지
않습니다. 엔진 계산 입력·여러 설계 프로젝트·파일시스템 저장 API와는 별도 출력
형식입니다.

```python
import hashlib
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord

request = SavedExecutionRequest(
    LumpedNetworkDocument([0, 1e9], resistance=10,
                          port_names=('input', 'output')).dumps())
receipt = request.run()
# Demonstration metadata only. A real host supplies its build artifact digests.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256=hashlib.sha256(b'demonstration artifact').hexdigest())]
record = SavedExecutionRecord(request, receipt,
    run_id='demo:run-1', artifacts=artifacts)
saved = record.dumps()
restored = SavedExecutionRecord.loads(saved)
assert restored.receipt == receipt
assert restored.prepare().to_dict() == request.to_dict()
assert restored.artifacts['verification'] == 'host-declared'
```

`sipi.execution-record/1`은 `schema`, `run_id`, `source_text`, `receipt`,
`artifacts`, `content_sha256`의 정확히 여섯 키를 가집니다. 영수증은 기존
`sipi.execution-receipt/1`의 요청·실행 객체를 유지합니다. 정규화 입력·의미적 요청
식별자·실행 조건은 `source_text`로 다시 준비한 요청과 같아야 합니다. 정규화할 때
문서가 커져 원래 입력 바이트 제한을 넘을 수 있으므로 정확한 원문을 보존합니다.
다시 열면서 원래 한계를 늘리거나 실행 조건을 바꾸지 않습니다.

실행 출력은 기존 `sipi.execution/1` 구조와 같은 정규화 입력을 사용해야 합니다.
완료·미완료 실행은 결과 객체와 null 오류를, 실패 실행은 null 결과와 type/message
오류 및 추가 실패 이력을 보관합니다. 오차 한계를 넘은 피팅의 `accepted=False`는
실행 완료와 별개로 유지합니다. 공차 실패 행과 미완료 요약을 버리지 않습니다.
이 구조 검사는 임의 결과의 수치적 의미나 물리적 타당성을 인증하지 않습니다.

## 산출물 선언과 변경 검출

산출물은 정확히 `schema`, `verification: "host-declared"`, `items`를 가진
`sipi.artifact-declaration/1`입니다. 각 항목은 `component`, `version`, `kind`,
`sha256` 네 필드이며 1–64개를 받습니다. component는 소문자 ASCII 영문/숫자로
시작하고 영문/숫자/점/밑줄/하이픈으로 된 최대 64자입니다. version은 ASCII
영문/숫자/더하기/점/밑줄/하이픈 1–128자입니다. kind는 `wheel`, `source-archive`,
`wasm`, `executable`, `runtime` 중 하나이고 digest는 소문자 16진수 64자입니다.
component/kind 쌍은 중복될 수 없고 `sipi` 항목이 있어야 합니다. 두 필드 순으로
정렬하여 저장하며 읽을 때도 이 순서를 요구합니다. 경로나 URL 필드는 없습니다.

이는 명시적인 **호스트 선언**이며 실제 설치 산출물 검증이나 전체 의존성 목록
인증이 아닙니다. 엔진이 PC를 검색하거나 패키지를 내려받거나 해당 바이트를 실행했다고
증명하지 않습니다. 실제 빌드/런타임 식별자는 호스트가 확보하고 검사해야 합니다.
위 예제 digest는 의도적인 합성 예시이며 배포 출처로 사용하면 안 됩니다.

`content_sha256`은 자기 자신을 제외한 모든 필드의 정규화 UTF-8 JSON을 해시합니다.
키를 정렬하고 공백 없는 구분자를 사용하며 Unicode를 ASCII escape로 바꾸지 않습니다.
일치하지 않으면 거부하고 읽으면서 자동 수정하지 않습니다. 내용과 체크섬을 함께
다시 만들 수 있으므로 서명·진위 인증·실행 증명은 아닙니다. 선언된 산출물 digest도
같은 신뢰 경계를 가집니다.

## 다시 연 뒤 명시적으로 실행

```python
prepared = restored.prepare()  # validates and reconstructs; no calculation
new_receipt = prepared.run()   # explicit new execution
new_record = SavedExecutionRecord(prepared, new_receipt,
    run_id='demo:run-2', artifacts=artifacts)
assert new_record.receipt == restored.receipt
assert new_record.run_id != restored.run_id
assert new_record.to_dict()['content_sha256'] != restored.to_dict()['content_sha256']
```

호스트가 제공하는 `run_id`는 ASCII 영문/숫자/점/밑줄/콜론/하이픈 1–128자입니다.
호스트가 유일성을 보장하고 응답을 표시하기 전에 현재 실행 토큰과 비교해야 합니다.
같은 의미의 요청도 서로 다른 실행일 수 있습니다. 이 기록 자체는 취소·작업 예약·
오래된 응답 표시 방지를 구현하지 않습니다. 새 실행에는 현재 호스트의 산출물 선언을
사용해야 하며 과거 선언을 복사하는 것으로 런타임 검증을 대체할 수 없습니다.

스냅샷은 불변이며 `to_dict`, `receipt`, `artifacts`는 분리된 객체를 반환합니다.
`dumps()`는 정규화된 짧은 문자열을 반환하고 파일을 쓰지 않습니다.
`loads`/`from_dict`는 추가/중복 필드·비유한 JSON 값·맞지 않는 요청/영수증/메타데이터/
체크섬을 거부합니다. 기록 크기 기본값은 8 MiB이며 `max_record_bytes`로 1바이트부터
64 MiB까지 설정합니다. 읽은 UTF-8 원문과 정규화 저장 문자열에 모두 적용합니다.
계산 입력의 원래 제한은 요청 내부에 별도로 유지합니다. 미지원 버전은 예외를 내며
호스트는 호환 판독기를 위해 원본 파일을 보존해야 합니다.

```sh
python -m pytest -q tests/sipi/test_execution_record.py tests/sipi/test_execution_request.py tests/sipi/test_tensor_dielectric_fit_document.py
```

실제 수락/미수락 피팅, 미완료 공차, 실패 역산 영수증을 검사합니다. 원입력/조건,
UTF-8 바이트 입장 조건, 산출물 선언 제한, 변경 검출, 데이터 분리, 계산 없는 준비를
검증하며 모든 등록 엔진 입력을 전계 계산 없이 구조적으로 다시 열 수 있는지 확인합니다.
새 물리 정확도·자동 저장/복구·UI 연결·산출물 진위·플랫폼 지원을 추가하는 검증은
아닙니다.
