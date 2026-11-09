# 설치 native workbench의 계산 기록 생성

`saved-record`는 저장 입력 원문 `text`와 선택 사항인 완전한 `controls`를 받는다.
[saved-receipt](RECEIPTS.ko.md)와 같이 입력 200 KiB, compact 인코딩 요청
256 KiB, 평가 최대 128회를 적용한다. 호출자가 준 실행 ID·배포물 선언·기타 옵션은
거부한다. 기존 분석과 receipt 작업의 응답·수치 동작은 유지한다.

파일 검사가 가능한 설치 SIPI wheel에 현재 recording helper가 있어야 한다.
[실제 설치 파일 목록](ARTIFACTS.ko.md)을 수집한 뒤 불변 요청을 한 번 실행하고
목록을 다시 수집한다. 두 snapshot이 다르면 기록 생성을 거부한다. 누락 metadata,
설치본을 가린 source import, 일치하지 않는 helper는 계산 전에 거부한다.
일반 솔버 예외는 오류로 남기며, 실패한 역산·일부 실패한 연구의 receipt는 원래
이력을 보존한다.

응답은 `engine`, 원문 `record_text`, 원문 `runtime_manifest_text`다.
기록에는 새 UUID 기반 실행 ID를 부여하며 입력·receipt·출처 선언을 포함해
200 KiB까지 허용한다. 초과한 출력은 잘라내지 않고 거부한다. 별도 manifest는
요청/프로젝트 한도보다 클 수 있으며 프로젝트 입력이 아닌 출처 근거다.
내보낼 때 두 원문 문자열을 보존한다. 기록의 숫자를 파싱 후 재직렬화하지 말고
원문을 `project-attach`에 전달한다. 프로젝트 합계 크기·명시적 선택 조건은 유지한다.

파일 비교는 원자적 filesystem snapshot, 실행 메모리 인증, 원본 wheel 식별,
물리 정확도 주장이 아니다. 선언은 `host-declared`로 유지한다. 고유 실행 ID가
취소·늦은 응답 검사를 대신하지 않는다. 파일을 쓰거나 프로젝트 결과를 선택하지 않는다.

브라우저는 별도 [배포 원본 출처 경로](BROWSER_RECORDING.ko.md)를 사용하며 EXE 출처는
후속 작업이다. 기존 계산은 유지하고 이 전달 작업이 자동 결과 이력 UI를 추가하지는 않는다.

빌드한 wheel에서 다음 예제를 소스 저장소 밖에서 실행한다.

```python
from sipi import LumpedNetworkDocument
from sipi.project import SavedProject
from sipi._workbench.engine import execute

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
project = execute(dict(action='project-create', text=text, project_id='example',
    design_id='a', title='Recorded calculation', label='A'))
result = execute(dict(action='saved-record', text=text))
updated = execute(dict(action='project-attach', project_text=project['project_text'],
    design_id='a', record_text=result['record_text'], select=True))
current = SavedProject.loads(updated['project_text']).current_record('a')
assert current.dumps() == result['record_text']
assert current.receipt['execution']['status'] == 'complete'
```

[English](RECORDING.md)
