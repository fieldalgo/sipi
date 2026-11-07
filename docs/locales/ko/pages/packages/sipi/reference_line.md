# 기준면별 표면 법칙을 저장한 선로

[English](../../../../../packages/sipi/reference_line.md) · [reference API](reference_surfaces.md) · [저장 신호 면](face_line.md)

`sipi.transmission-line/5`는 기존 `surface-faces` 도체에 엄격한 reference 표면
변형을 추가합니다. 이전 버전의 의미와 생성자의 기본 버전 1을 유지합니다.
버전 5에서도 기존 perfect·공통 surface·경계별 금속·면별 금속 입력을 그대로 받으며
그 결과를 바꾸지 않습니다.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma=58e6):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind='smooth'))

cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
conductor = dict(kind='surface-faces', ground_thickness=35e-6,
    conductors={'signal': {face: metal() for face in ('bottom', 'top', 'left', 'right')}},
    reference=dict(kind='surfaces', bottom=metal(), top=metal(35e6), sides=None, conductors={}))
line = TransmissionLineDocument(cross, [1e9, 4e9], materials={}, conductor=conductor,
    length=.03, z_ref=75., schema='sipi.transmission-line/5')
assert normalize_saved(line.dumps()) == line.dumps()
report = execute_saved(line.dumps())
assert report['status'] == 'complete'
assert report['result']['conductor_boundaries']['labels'][-2:] == ['reference:bottom', 'reference:top']
```

`reference`는 `kind='surfaces'`, `bottom`, `top`, `sides`, `conductors`만
포함합니다. 활성 plane/측벽에는 완전한 기존 금속 record를, 열린 경계에는 JSON
`null`을 넣습니다. `conductors`는 외부의 신호 면 mapping과 구분되는 ground trace
이름별 완전한 금속 record입니다. record마다 `conductivity`,
`relative_permeability`, 명시적인 지원 `roughness`를 유지합니다. ground trace의
둘레 전체에는 하나의 법칙을 적용하고 양 측벽도 하나를 공유합니다. 모든 접지는
같은 PEC 전위이며 별도 포트가 아닙니다.

이 변형은 버전 5의 `surface-faces`에만 허용합니다. 기존 tag 없는 공통 reference
metal은 버전 4와 5에서 유효합니다. 알 수 없는 필드·그룹 누락·열린 경계에 금속,
접지 경계에 null·잘못된 금속·중복 JSON 키·비유한 수를 거부합니다. 기하·배정·국소
표피 깊이 조건은 필드 계산 없이 정규화할 때 검사합니다.

분석은 기존 한 메시 구성을 재사용합니다. 신호·reference 전류 분할의 C0를 유전체
추출에 공유합니다. 공통 실행은 모든 표면 label·표피 깊이·거칠기 계수·복소 표면
임피던스·저항 기여·Q·적분 전류와 분할 전 도체 전류·flux 오류를 보존합니다.
기존 호출자 주파수 예산과 진단 선택도 유지합니다. 새로운 필드 솔버나 전류 재분포,
물리 정확도 범위를 추가하는 변경은 아닙니다.

기존 회로 source가 이 문서를 그대로 받습니다. 1회 추출 길이 탐색도 source 종류나
탐색 schema를 추가하지 않고 재사용합니다.

```python
from sipi.length_design import LineLengthDesignDocument

source = line.to_dict()
source['length_m'] = 0.
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=source),
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)],
    bounds=[0., .5], tolerance=1e-5, max_evaluations=32, schema='sipi.line-length-design/2')
result = plan.solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.to_dict()['source_evaluation']['field_extractions'] == 1
```

길이 탐색은 표본 구간·시도 예산·실패 보존 규칙을 유지하며 전역 최대나 연속 대역을
보장하지 않습니다. 원래 필드 입력의 기하별 메시·외곽 수렴은 여전히 별도로 필요합니다.

검증은 저장 RLGC/S와 개별 reference 손실·유전체 API를 1e−10 이내, 이전 공통
reference 형식을 1e−12 이내, 기존 회로 단자 전압을 1e−10 이내로 비교합니다.
한 메시/C0 객체 공유·입력에서 분리된 재생·엄격한 메시 전 거부·모든 진단 보존과
혼합모드 길이 탐색의 1회 추출을 확인합니다. 독립 필드·평행판·수렴 근거는
[reference API](reference_surfaces.md)의 검증을 따릅니다. 엔진 계약이며 앱 pin,
동박 실측·플랫폼 수락 범위는 별도입니다.

```sh
python -m pytest -q tests/sipi/test_reference_line.py tests/sipi/test_face_line.py tests/sipi/test_line_model.py tests/sipi/test_execution.py tests/sipi/test_extracted_length_design.py
```
