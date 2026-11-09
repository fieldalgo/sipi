# 프로젝트 전달 계약

[English](PROJECTS.md)

desktop/Worker의 내부 adapter는 기존
[SavedProject](../docs/locales/ko/pages/packages/sipi/project.md) 형식을 이용한다.
계산이나 파일 쓰기는 실행하지 않는다. [입력 프로젝트 화면](README.ko.md)이 이
입력 동작을 이용하며 기록 동작과 결과 이력 화면은 별도다. 엔진 입력을 열 수 있다는 사실이
해당 편집 폼 지원을 뜻하지 않는다.

| action | `action` 외 필수 키 | 선택 키 |
|---|---|---|
| `project-create` | `text`, `project_id`, `design_id`, `title`, `label` | `controls` |
| `project-open` | `project_text` | 없음 |
| `project-duplicate` | `project_text`, `source_id`, `design_id`, `label` | 없음 |
| `project-update` | `project_text`, `design_id`, `text` | `controls`, `label` |
| `project-attach` | `project_text`, `design_id`, `record_text`, `select` | 없음 |
| `project-select` | `project_text`, `design_id`, `run_id` | 없음 |
| `project-remove-record` | `project_text`, `design_id`, `run_id` | 없음 |

`text`는 원본 엔진 입력 JSON, `project_text`와 `record_text`는 프로젝트와 실행 기록 원문 JSON이다.
누락·알 수 없는 옵션, 원본 JSON의 중복 키, 미지원 버전, 잘못된 값 및 프로젝트
digest 불일치를 거부한다. 응답은 기존 버전/빌드 정보인 `engine`과 정규
`project_text`를 담는다. 새 아티팩트 인증이나 생성한 결과 기록이 아니다.

UTF-8 요청은 256 KiB, 새 입력·들어오는 프로젝트/기록 원문·정규 프로젝트 출력은 각각
200 KiB까지다. adapter는 compact JSON과 원문 Unicode로 크기를 확인하고 native
HTTP 호스트는 공백·이스케이프를 포함한 실제 본문도 제한한다. 초과 시 잘라내거나
기록을 삭제하지 않는다. 오류가 나면 호스트는 이전 snapshot을 유지해야 한다.
핵심 API의 더 큰 설정 가능 한도와 별개다.

`controls`를 주면 `max_input_bytes`, `max_evaluations`, `diagnostics` 세 키가
모두 필요하며 기존 실행요청 검사를 적용한다. 생성 기본값은 204800 bytes, 128회,
빈 diagnostics이다. 수정에서 생략하면 기존 controls를 유지한다. 입력 준비
성공은 계산의 모델별 예산 허용이나 수렴 확인을 뜻하지 않는다.

복제는 현재 입력·controls를 새 ID에 복사하고 이력을 비우며 다른 설계를 유지한다.
입력·controls의 의미가 바뀌면 현재 결과 선택만 해제하고 이력은 보존한다. 서식만
바뀌면 선택과 새 원문을 유지한다. 열기는 검증된 기록과 명시적 선택을 보존한다.

`project-attach`는 기존 기록과 필수 boolean `select`를 받는다. 실행 ID는 프로젝트
전체에서 고유해야 한다. `select=true`이면 기록의 입력과 controls가 현재 설계와
같아야 한다. `false`이면 과거 요청을 이력으로 남길 수 있고 현재 선택은 유지한다.
`project-select`는 현재 입력에 맞는 기존 실행을 선택하며 `run_id=null`이면 선택을
해제한다. `project-remove-record`는 기존 기록을 제거하고 선택된 기록이면 선택도
해제한다. 없는 설계/실행·다른 입력의 현재 선택·변조·결합 크기 초과는 원래
snapshot을 바꾸지 않고 거부한다. 최신 결과를 자동 선택하거나 활성 실행의 응답임을
인증하지 않는다.

JavaScript를 거칠 때 기록의 직렬화 원문을 전달해야 한다. 숫자를 파싱 후 다시
직렬화하면 content digest가 달라질 수 있다. 출처 선언은 `host-declared` 그대로이며
기록을 붙인다고 배포물의 출처를 감사하거나 인증하지 않는다. 실행 ID·늦은 응답
처리·실행·실제 배포물 근거·파일 게시는 호스트의 작업이다. UI는 아직 새 결과를
생성해 붙이지 않는다.

빌드한 개발 wheel에서 전계 계산 없이 A/B 입력을 만들고 수정하는 예제:

```python
import json
from sipi.template_document import TemplateSectionDocument
from sipi._workbench.engine import execute

design = TemplateSectionDocument('stripline',
    dict(width=.0005, plane_spacing=.001, eps_r=4))
created = execute(dict(action='project-create', text=design.dumps(),
    project_id='example', design_id='a', title='Width study', label='A'))
copied = execute(dict(action='project-duplicate', project_text=created['project_text'],
    source_id='a', design_id='b', label='B'))
variant = TemplateSectionDocument('stripline',
    dict(width=.0006, plane_spacing=.001, eps_r=4), mesh=design.cross_section.mesh_options)
updated = execute(dict(action='project-update', project_text=copied['project_text'],
    design_id='b', text=variant.dumps()))
opened = execute(dict(action='project-open', project_text=updated['project_text']))
assert opened['project_text'] == updated['project_text']
assert len(json.loads(opened['project_text'])['designs']) == 2
cleared = execute(dict(action='project-select', project_text=opened['project_text'],
    design_id='a', run_id=None))
assert cleared['project_text'] == opened['project_text']
```

adapter/HTTP 검사와 실제 브라우저·플랫폼 검사는 별개다.
현재 사용 흐름과 범위는 [workbench 안내](README.ko.md)를 참고한다.
