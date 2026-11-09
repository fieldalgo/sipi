# 편집 가능한 템플릿 단면 입력

[English](../../../../../packages/sipi/template_document.md) · [단면 JSON](design.md) · [프로젝트](project.md) · [공통 실행](execution.md)

`TemplateSectionDocument`는 지원 템플릿의 이름·수치 입력값과 정확한 단면
형상·확정 메시 제어값을 함께 저장합니다. 앱은 다각형에서 원래 치수를
추측하지 않고 입력 폼을 복원할 수 있습니다. 이는 엔진 입력 계약이며,
이 클래스 자체가 폼이나 프로젝트 화면을 구현하지는 않습니다.

```python
from sipi.template_document import TemplateSectionDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.execution_record import SavedExecutionRecord
from sipi.project import SavedProject

section = TemplateSectionDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=4),
    mesh=dict(edge_size=40e-6, far_size=.25e-3, grade=.3))
request = SavedExecutionRequest(section.dumps())
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['result']['z0_ohm'] > 0
# Synthetic demonstration metadata, not actual runtime provenance.
record = SavedExecutionRecord(request, receipt, run_id='demo:template-1',
    artifacts=[dict(component='sipi', version='example-only', kind='wheel', sha256='1'*64)])
project = SavedProject(request, project_id='demo:project', design_id='a',
                       title='Stripline comparison', label='Baseline')
project = project.attach_record('a', record, select=True)
restored = SavedProject.loads(project.dumps())
reopened = TemplateSectionDocument.loads(restored.prepare('a').source_text)
assert reopened.parameters == section.parameters
assert reopened.cross_section.dumps() == section.cross_section.dumps()
```

임피던스 study에 등록된 기존 제조 템플릿 42종을 사용합니다. 기존 기하·재료
유효성 규칙이 그대로 적용됩니다. 길이는 미터, 상대 유전율과 손실 탄젠트는
무차원입니다. 새 factory·솔버·재료 모델·물리 정확도는 추가하지 않습니다.
`analyze()`는 일반 `CrossSectionDocument`로 위임하며 공통 실행도 기존 단면
결과 필드를 사용합니다.

## 수정 후 계산 선택

```python
from sipi.design_document import ImpedanceDesignDocument
from sipi.study import ImpedanceStudyDocument

edited = TemplateSectionDocument(reopened.template,
    dict(reopened.parameters, width=.6e-3), mesh=reopened.mesh_options)
updated = restored.update_design('a', SavedExecutionRequest(edited.dumps()))
assert updated.current_record('a') is None
assert updated.design('a')['records'] == [record.to_dict()]

# Prepare existing goal/study inputs from the saved template without solving.
goal = ImpedanceDesignDocument(edited.template, edited.parameters,
    variable='width', bounds=[.4e-3, .8e-3], target=50,
    max_evaluations=32, mesh=edited.mesh_options)
study = ImpedanceStudyDocument(edited.template, edited.parameters,
    quantity='z0', mesh=edited.mesh_options,
    sampling=dict(kind='corners', variables=[dict(name='width', lower=.55e-3, upper=.65e-3)]))
assert goal.to_dict()['parameters'] == edited.parameters
assert study.to_dict()['parameters'] == edited.parameters
```

수정은 새 문서를 만듭니다. 예제는 메시 제어값을 명시적으로 유지합니다.
`mesh`를 생략하면 변경한 단면의 기본 메시를 새로 정하는 선택입니다.
어느 쪽도 수렴 보증은 아닙니다. 목표·study의 물리량·범위·표본·고정 pitch·
재료 override에는 해당 기능의 기존 계약이 적용됩니다. 입력 준비만으로
목표의 가능성이나 세분 메시 허용 오차 충족을 증명하지 않습니다.

## 정확한 형상 연결

`sipi.template-section/1`은 정확히 `schema`, `template`, `parameters`,
`cross_section`을 가집니다. 인자 연결은 알 수 없거나 빠진 이름, bool,
비유한 수치를 거부합니다. 기본 인자 값도 명시적으로 포함합니다.
`None`은 기존 기본값이 `None`인 선택 인자에만 허용합니다. 해당 인자는
목록에 `None`으로 남을 수 있지만 실제 확정 형상은 `cross_section`에 저장됩니다.

내장 단면은 기존 버전 있는 기하 스키마를 사용합니다. 메시에는 확정된
`edge_size`, `far_size`, `grade`, `min_angle` 네 값이 모두 들어갑니다.
열 때 현재 factory가 저장된 인자와 메시 제어값으로 형상을 다시 만들고,
정규 기하가 정확히 같은지 검사합니다. 폭·재료·경계·기하 버전의 불일치나
미확정 메시 값은 거부합니다. 후속 엔진이 factory 의미를 바꾸면 별도
마이그레이션이 필요하며 이 클래스가 저장 형상을 조용히 대체하지 않습니다.

`template`, `parameters`, `cross_section`, `section`, `mesh_options`는
분리되거나 재구성된 값을 제공합니다. 스냅샷은 불변입니다. `loads`/`from_dict`는
알 수 없는 필드·중복 키·비유한 JSON을 거부하며, 준비는 필드 해석 없이 기하만
검증합니다. 기존 기하 JSON은 계속 지원하고 임의 형상에서 템플릿을 추정하지
않습니다. 공통 입력 byte cap과 요청·프로젝트 식별 계약도 그대로 적용됩니다.

```sh
python -m pytest -q tests/sipi/test_template_document.py tests/sipi/test_execution_request.py tests/sipi/test_execution_record.py tests/sipi/test_project.py
```

동결한 42개 fixture는 기존 factory의 기본 인자·정확한 기하·메시를 기록하며
사다리꼴·층상·코팅·유한 ground 사례를 포함합니다. 이는 **기존 기하 회귀 기준**이며
독립 물리 정답은 아닙니다. 별도로 직접·저장 실행의 실제 행렬, 독립 Cohn
stripline과 메시·외곽 세분, 프로젝트 재열기·수정 후 선택 해제를 검사합니다.
기존 수치 방법·허용 오차는 바꾸지 않습니다. 추가 UI 폼·브라우저 런타임 대조·
Windows 수락은 별도 작업입니다.
