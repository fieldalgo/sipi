# 프로젝트 전달 계약

[English](PROJECTS.md)

desktop/Worker의 내부 adapter는 기존
[SavedProject](../docs/locales/ko/pages/packages/sipi/project.md) 형식을 이용한다.
계산이나 파일 쓰기는 실행하지 않는다. A/B 조작 및 결과 이력 화면은 아직 연결되지
않았다. 엔진 입력을 열 수 있다는 사실이 해당 편집 폼 지원을 뜻하지 않는다.

| action | `action` 외 필수 키 | 선택 키 |
|---|---|---|
| `project-create` | `text`, `project_id`, `design_id`, `title`, `label` | `controls` |
| `project-open` | `project_text` | 없음 |
| `project-duplicate` | `project_text`, `source_id`, `design_id`, `label` | 없음 |
| `project-update` | `project_text`, `design_id`, `text` | `controls`, `label` |

`text`는 원본 엔진 입력 JSON, `project_text`는 원본 프로젝트 JSON이다.
누락·알 수 없는 옵션, 원본 JSON의 중복 키, 미지원 버전, 잘못된 값 및 프로젝트
digest 불일치를 거부한다. 응답은 기존 버전/빌드 정보인 `engine`과 정규
`project_text`를 담는다. 새 아티팩트 인증이나 생성한 결과 기록이 아니다.

UTF-8 요청은 256 KiB, 새 입력·들어오는 프로젝트 원문·정규 프로젝트 출력은 각각
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
새 결과 추가·최신 결과 자동 선택은 하지 않는다. 실행별 ID·늦은 응답 처리·실행·
아티팩트 선언·파일 게시는 호스트의 후속 작업이다.

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
```

native 소스/설치 adapter 및 실제 HTTP 프로세스 검사는 새 Worker·Windows 수락
결과가 아니다. 이번 단위에서 화면 자산은 바뀌지 않는다.
