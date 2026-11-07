# 접지 도체의 면별 법칙을 저장하는 선로

[English](../../../../../packages/sipi/ground_face_line.md) · [접지 면 API](ground_faces.md) · [기준 그룹](reference_line.md)

`sipi.transmission-line/6`은 유한 두께 직사각형·사다리꼴 접지 도체의 4면에
각각 표면 법칙을 저장합니다. 기존 `surface-faces` 도체와
`reference.kind='surfaces'`를 확장합니다. 이전 도체 형식도 그대로 받습니다.
생성자 기본값은 버전 1이며 이전 스키마를 읽으면서 자동 승격하지 않습니다.

```python
from sipi import CrossSectionDocument, coplanar_stripline
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

def metal(sigma=58e6):
    return dict(conductivity=sigma, relative_permeability=1., roughness=dict(kind='smooth'))

faces = ('bottom', 'top', 'left', 'right')
section = coplanar_stripline(width=.5e-3, gap=.2e-3, ground_width=.5e-3,
    plane_spacing=1e-3, trace_height=.4e-3, thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3)
cross = CrossSectionDocument(section, mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
left = dict(kind='faces', **{face: metal() for face in faces})
left['top'] = metal(58e6/4)
reference = dict(kind='surfaces', bottom=metal(), top=metal(), sides=None,
    conductors={'ground_left': left, 'ground_right': metal()})
line = TransmissionLineDocument(cross, [1e9, 4e9], materials={}, length=.03, z_ref=75.,
    conductor=dict(kind='surface-faces', ground_thickness=35e-6,
        conductors={'signal': {face: metal() for face in faces}}, reference=reference),
    schema='sipi.transmission-line/6')
assert normalize_saved(line.dumps()) == line.dumps()
assert line.to_dict()['schema'] in saved_schemas()
report = execute_saved(line.dumps())
assert report['status'] == 'complete'
labels = report['result']['conductor_boundaries']['labels']
assert 'reference:ground:ground_left:top' in labels
assert labels[-1] == 'reference:ground:ground_right'
```

각 접지 이름의 값은 전체 둘레를 나타내는 기존 완전한 금속 record 또는 정확히
`{kind: "faces", bottom, top, left, right}`입니다. 각 면은 기존 계약의
`conductivity`, `relative_permeability`, 명시적인 `roughness`를 모두 가져야 합니다.
신호 면은 기존 tag 없는 4필드 record를 유지합니다. 기준면·측벽은 각각 금속
하나를 사용하고 열린 경계는 null입니다. 전체 둘레 금속을 쓰는 접지도 이름을
빠짐없이 지정해야 합니다.

버전 5는 계속 4면 접지 record를 거부합니다. 알 수 없거나 빠진 필드, 중복 JSON
키, 비유한 수, 두께 없는 접지·임의 다각형의 면 지정, 확장 label 충돌, 각 면의
skin-depth 위반은 메시 전에 거부합니다. 정규화는 field 계산 없이 입력과 분리된
정규 snapshot을 만듭니다. [API의 기하·skin-depth·전류보존 조건](ground_faces.md)은
그대로 적용되며 모든 기준 도체는 하나의 PEC 전위를 공유합니다.

해석은 기하 메시 하나와 공유 진공 전류 추출 하나를 사용하고 같은 C0를 유전체
추출에 넘깁니다. 공통 실행 결과는 확장 label, skin depth, 거칠기 계수, 표면
임피던스, 저항 기여, Q, 면별·전체 도체 전류를 보존합니다. 공유 추출 한 번은
신호마다 단위 전압 field를 푼다는 뜻이며 모든 단면에서 스칼라 해가 하나라는
뜻은 아닙니다.

기존 회로 source가 이 버전을 받습니다. 길이 역산은 RLGC를 한 번 추출해 고정한
다음 기존 샘플 주파수 bracket과 평가 예산을 재사용합니다.

```python
from sipi.length_design import LineLengthDesignDocument

source = line.to_dict()
source['length_m'] = 0.
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=source),
    bounds=[0., .5], tolerance=1e-5, max_evaluations=32,
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 4e9], minimum=.7, maximum=None)],
    schema='sipi.line-length-design/2')
result = plan.solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.to_dict()['source_evaluation']['field_extractions'] == 1
```

별도 Python API의 RLGC/S 및 회로 재생은 1e−10, 같은 금속의 4면과 기존 전체
둘레 모델은 1e−12 이내인지 검사합니다. 고정 RLGC 길이 탐색 이력은 정확히
일치해야 합니다. 독립 scikit-rf DistributedCircuit 비교는 같은 추출 RLGC로
S 절대 오차 1e−10을 요구합니다. 이는 네트워크 전파 비교이며 field 추출의
독립 검증은 아닙니다. 기존 독립 유한요소·넓은 접지박 한계·메시/외곽 수렴 근거는
접지 면 API 문서에 있습니다. 저장 연결은 새로운 물리 정확도, 연속 주파수 보장,
앱 통합 또는 Windows 수락을 의미하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_ground_face_line.py tests/sipi/test_reference_line.py tests/sipi/test_face_line.py tests/sipi/test_execution.py tests/sipi/test_extracted_length_design.py
```
