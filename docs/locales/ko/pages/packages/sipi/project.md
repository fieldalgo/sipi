# A/B 프로젝트 저장

[English](../../../../../packages/sipi/project.md) · [실행 결과 기록](execution_record.md) · [실행 요청](execution_request.md) · [로컬 파일](project_io.md)

`SavedProject`는 여러 설계의 현재 입력과 실행 이력을 하나의 불변 JSON
스냅샷에 보관합니다. 로컬 A/B 비교와 다시 열기에 사용할 데이터 계약입니다.
열기·수정·요청 준비는 계산을 실행하지 않습니다. 이 API 자체는 파일을 읽거나
쓰지 않으며 사용자 화면을 시작하지 않습니다.

```python
import hashlib
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

def make_request(resistance):
    return SavedExecutionRequest(
        LumpedNetworkDocument([0, 1e9], resistance=resistance).dumps())

# Synthetic example metadata; the application must check actual build artifacts.
artifacts = [dict(component='sipi', version='example-only', kind='wheel',
                  sha256=hashlib.sha256(b'demonstration artifact').hexdigest())]
a = make_request(10)
result_a = SavedExecutionRecord(a, a.run(), run_id='demo:a', artifacts=artifacts)
project = SavedProject(a, project_id='demo:project', design_id='a',
                       title='Series resistor comparison', label='Baseline')
project = project.attach_record('a', result_a, select=True)
project = project.duplicate_design('a', 'b', 'Alternative')
assert project.design('b')['records'] == []
b = make_request(20)
project = project.update_design('b', b)
result_b = SavedExecutionRecord(b, b.run(), run_id='demo:b', artifacts=artifacts)
project = project.attach_record('b', result_b, select=True)
saved_text = project.dumps()  # application chooses how/where to persist this
restored = SavedProject.loads(saved_text)
assert restored.current_record('a').receipt == result_a.receipt
assert restored.current_record('b').receipt == result_b.receipt
assert restored.prepare('b').to_dict() == b.to_dict()
```

화면은 `current_record(design_id)`를 명시적으로 선택된 결과로 표시합니다.
`None`은 현재 요청에 선택된 결과가 없다는 뜻입니다. 이력의 마지막 항목을
새 계산 결과로 표시하면 안 됩니다. 선택된 기록의 전체 정규 요청과 실행
제어값은 현재 설계와 같아야 합니다. 실행 완료·피팅 수락·공차 완전성은 원래
receipt의 별도 값으로 유지되며, 선택만으로 수치 정확도나 수락을 보증하지 않습니다.

```python
edited = restored.update_design('b', make_request(25))
assert edited.current_record('b') is None
assert edited.design('b')['records'] == [result_b.to_dict()]
assert restored.current_record('b').run_id == 'demo:b'  # old snapshot unchanged
reopened = SavedProject.loads(edited.dumps())
assert reopened.current_record('b') is None
assert reopened.prepare('b').to_dict() == make_request(25).to_dict()
```

## 결과 선택과 이력

- `add_design(id, label, request)`는 결과 없는 현재 요청을 추가합니다.
- `duplicate_design(source_id, id, label)`은 현재 요청·제어값만 복사합니다.
  새 설계의 이력과 선택은 비어 있고 기존 스냅샷은 바뀌지 않습니다.
- `update_design(id, request, label=...)`은 현재 원본 입력·제어값을 교체합니다.
  의미가 바뀌면 선택만 해제하고 모든 과거 기록을 남깁니다. 정규 요청이 같고
  원본 JSON 표기만 달라졌다면 선택을 유지합니다.
- `attach_record(id, record)`는 선택 없이 이력에 추가합니다. 이전 요청의
  늦은 응답도 이 방식으로 보관할 수 있습니다.
- `attach_record(..., select=True)`와 `select_record(id, run_id)`는 해당 설계 안에서
  현재 요청과 같은 기록만 선택합니다. 불일치는 거부합니다.
  `select_record(id, None)`은 이력을 삭제하지 않고 선택을 해제합니다.
- `remove_record(id, run_id)`는 명시적으로 기록 하나를 제거하며 필요하면 선택도
  해제합니다. `remove_design(id)`는 설계 하나를 제거하고 최소 하나는 남겨야
  합니다. 모두 새 스냅샷을 반환하며 기존 파일을 지우지 않습니다.
- `design(id)`와 `to_dict()`는 분리된 복사본을 반환합니다. `design_ids`는 설계
  순서를 보존하고 `prepare(id)`는 실행하지 않고 원래 요청을 준비합니다.

**현재 실행 응답의 채택은 호스트 책임**입니다. 같은 의미의 요청을 두 번
실행하면 두 응답 모두 설계와 일치할 수 있습니다. 도착한 응답을 선택하기 전에
현재 실행 토큰도 비교해야 합니다. 프로젝트 열기·선택은 취소·프로세스 수명·
동시 편집·작업 큐를 구현하지 않습니다. 시각이나 이력 순서로 자동 선택하지 않습니다.

## 엄격한 파일 내용 계약

`sipi.project/1`은 정확히 `schema`, `project_id`, `title`, `designs`,
`content_sha256`을 가집니다. 순서 있는 각 설계는 정확히 `design_id`, `label`,
`source_text`, `controls`, `records`, `selected_run_id`를 가집니다. 제어값은
기존 정규 `max_input_bytes`, `max_evaluations`, `diagnostics`를 유지하고 기록은
기존 [실행 결과 계약](execution_record.md)을 재사용합니다. 이 envelope는
등록된 엔진 계산 입력이 아닙니다.

설계는 1–64개, 전체 기록은 최대 128개입니다. 설계 ID와 실행 ID는 각각
프로젝트 전체에서 중복될 수 없습니다. 프로젝트·설계 ID는 ASCII 영문·숫자·
점·밑줄·콜론·하이픈 1–128자입니다. 제목과 설계 이름은 공백만인 문자열을
허용하지 않고 각각 512/256 UTF-8 바이트 이내이며 C0·DEL 제어문자를 제외합니다.
정규 입력이 더 커지더라도 원본 입력과 원래 byte cap을 그대로 보존합니다.

`max_project_bytes` 기본값은 16 MiB이고 1바이트부터 64 MiB까지 지정할 수
있습니다. 불러올 원본 UTF-8 텍스트와 저장할 정규 JSON에 모두 적용되며, 내장
결과도 같은 cap 안에서 재검증합니다. 새 스냅샷을 반환하는 수정 메서드는
지정된 cap을 유지합니다. 알 수 없거나 중복된 키·미지원 버전·비유한 값·잘못된
선택·손상된 내부 기록은 거부합니다.

체크섬은 `content_sha256`을 제외한 모든 필드를 키 정렬·간격 없는 구분자·
Unicode를 이스케이프하지 않은 UTF-8로 해시합니다. 변경을 검출하고 열 때
조용히 복구하지 않습니다. 다시 계산한 체크섬은 파일 인증이 아닙니다.
기록의 artifact 정보도 **호스트 선언**으로 남으며 저장만으로 설치 바이너리·
의존성 완전성·실제 실행을 증명하지 않습니다.

파일의 원자적 쓰기·백업·복구·미지원 원본 보존은 앱 책임입니다. 이 envelope는
알 수 없는 필드를 버리거나 자동 마이그레이션하거나 실행 중 작업을 복원하지
않고, 브라우저·Windows 지원을 약속하지 않습니다. UI 상태·프로젝트 병합도
이번 계약에 포함하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_project.py tests/sipi/test_execution_record.py tests/sipi/test_execution_request.py
```

실제 A/B 회로 계산, 입력 수정·이력 불변성, 늦은 응답, 동일 요청의 명시적 실행
선택, 복제·삭제·다시 열기, UTF-8·개수 경계, 구조·무결성, 전체 입력 형식의
암묵적 필드 계산 없는 준비를 검사합니다. 새 물리 정확도 주장은 하지 않습니다.
