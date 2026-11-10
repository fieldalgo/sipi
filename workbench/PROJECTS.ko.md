# 프로젝트 전달 계약

[English](PROJECTS.md)

desktop/Worker의 내부 adapter는 기존
[SavedProject](../docs/locales/ko/pages/packages/sipi/project.md) 형식을 이용한다.
계산이나 파일 쓰기는 실행하지 않는다. [입력 프로젝트 화면](README.ko.md)이 이
입력 동작을 이용한다. **Saved analysis**는 아래 설명처럼 같은 계약으로 프로젝트
입력·실행 기록·명시적 이력 선택을 연결한다. 엔진 입력을 열 수 있다는 사실이
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
| `project-record` | `project_text`, `design_id`, `run_id` | 없음 |

`text`는 원본 엔진 입력 JSON, `project_text`와 `record_text`는 프로젝트와 실행 기록 원문 JSON이다.
누락·알 수 없는 옵션, 원본 JSON의 중복 키, 미지원 버전, 잘못된 값 및 프로젝트
digest 불일치를 거부한다. 응답은 기존 버전/빌드 정보인 `engine`과 정규
`project_text`를 담는다. 새 아티팩트 인증이나 생성한 결과 기록이 아니다.
읽기 전용 `project-record` 응답은 대신 `engine`, 원문 `record_text`, boolean인
`selected`, `matches_current`를 반환하며 프로젝트 대체본을 반환하지 않는다.

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

`project-record`는 계산·선택·변경 없이 지정한 기존 실행을 읽는다. 입력 프로젝트
전체를 먼저 검증하고 Python으로 직렬화한 원래 기록의 숫자 표기와 digest를 보존한다.
과거 입력·controls의 기록도 읽을 수 있으나 `matches_current=false`이면 현재 설계의
결과가 아닌 과거 이력이다. 서식만 바뀐 입력은 의미상 일치를 유지한다. `selected`는
기존 명시적 선택 여부이며 일치한다고 자동 선택하지 않는다. 기록의 host-declared
배포물 metadata에서 runtime manifest를 새로 만들거나 복원했다고 주장하지 않는다.

JavaScript를 거칠 때 기록의 직렬화 원문을 전달해야 한다. 숫자를 파싱 후 다시
직렬화하면 content digest가 달라질 수 있다. 출처 선언은 `host-declared` 그대로이며
기록을 붙인다고 배포물의 출처를 감사하거나 인증하지 않는다. 실행 ID·늦은 응답
처리·실행·실제 배포물 근거·파일 게시는 호스트의 작업이다. 폼 23종의 입력 프로젝트
화면은 새 기록을 붙이지 않으며 이 작업은 **Saved analysis**에서 한다.

## 분석 변형과 실행 이력 보관

**Saved analysis**에서 입력을 열고 **Start project from input**을 누른다.
설계 이름·원문 JSON·선택 진단을 수정하고 **Duplicate current input**으로 변형을
만든다. 복제본은 현재 입력·controls를 보존하되 이력은 비운다. 설계를 전환하면
현재 편집을 먼저 검증·저장하고 다른 입력과 진단을 복원한다. 입력이 잘못되면
현재 프로젝트·설계를 유지한다. **Save project**는 원문 전체를
`sipi-analysis-project.json`으로 내려받고 **Open project**는 검증 후에만 현재
상태를 바꾼다. 업로드·자동 파일 저장은 하지 않는다.

활성 프로젝트의 **Run and keep record**는 현재 입력·controls를 한 번 실행한 뒤
해당 설계에 기록을 붙이고 명시적으로 현재 결과로 선택한다. 실패한 역산·불완전한
연구도 원래 상태대로 기록한다. 결합된 프로젝트가 한도를 넘으면 기존 프로젝트를
유지하며 새 개별 기록은 내려받을 수 있도록 오류를 알린다. 일반 **Run analysis**는
이력을 만들지 않으며 프로젝트에서는 기록 실행과 동일한 저장 byte/평가 한도 및
선택 진단을 사용한다. 가져온 controls를 보존하므로 128회를 넘는 예산도 열고 저장할
수는 있지만 실행은 거부한다. 몰래 예산을 줄이지 않는다.

**Project history**에서 실행을 골라 **View saved run**을 누르면 재계산·선택·입력
교체 없이 기록 원문을 읽는다. 현재 선택·입력 일치하나 미선택·과거 요청을 구분하고
미저장 편집도 표시한다. **Select as current**는 검증된 현재 입력·controls와
일치하는 기록만 허용한다. **Clear selection**은 이력을 유지하고 선택만 해제한다.
**Remove from project**는 고른 실행을 제거하며 선택된 기록이면 선택도 해제한다.
변경을 보관하려면 프로젝트 파일을 저장한다.

입력·controls 편집은 과거 이력을 남기고 다음 검증된 프로젝트 갱신에서 맞지 않는
선택을 해제한다. 서식 변경만으로 의미상 일치가 바뀌지는 않는다. 프로젝트·기록
원문은 digest에 사용된 숫자를 JavaScript로 재직렬화하지 않고 전달·내려받는다.
이력 기록은 내보낼 수 있지만 별도 runtime manifest는 프로젝트 안에 없다.
따라서 이력만 볼 때 **Save environment**는 비활성화된다. 이후에 필요하면 새 기록
실행 직후 환경 파일을 따로 저장한다. 이력 열람 중 일반 결과 내보내기는 비활성화되며
원문 기록을 저장한다.

취소된 작업·늦은 파일 읽기·늦은 attach 응답은 현재 프로젝트를 교체하거나 오래된
실행을 추가하지 못한다. 필요한 모든 변환이 성공한 뒤에만 UI 프로젝트를 갱신한다.
프로젝트 200 KiB·encoded 요청 256 KiB 한도를 유지하고 잘라내거나 과거 실행을
자동 삭제하지 않는다. 개별 기록 파일 가져오기·자동 수치 비교·환경 목록 보관소는
이번 화면의 범위가 아니다.

실제 브라우저 검사는 `SIPI_PYTHON`을 빌드 wheel 환경으로 지정한 뒤
`node workbench/tests/project-history-browser.mjs OUTPUT`으로 실행한다.
두 번째 인자로 staged 브라우저 디렉터리를 주면 Worker 경로를 검사한다.

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

숫자를 파싱한 객체를 다시 보내지 않고 실제 설치 기록 원문을 읽는 예제:

```python
from sipi import LumpedNetworkDocument
from sipi._workbench.engine import execute

text = LumpedNetworkDocument([0, 1e9], resistance=10).dumps()
created = execute(dict(action='project-create', text=text, project_id='records',
    design_id='a', title='Recorded analysis', label='A'))
recorded = execute(dict(action='saved-record', text=text))
import json
run_id = json.loads(recorded['record_text'])['run_id']
attached = execute(dict(action='project-attach', project_text=created['project_text'],
    design_id='a', record_text=recorded['record_text'], select=True))
read = execute(dict(action='project-record', project_text=attached['project_text'],
    design_id='a', run_id=run_id))
assert read['record_text'] == recorded['record_text']
assert read['selected'] and read['matches_current']
```
