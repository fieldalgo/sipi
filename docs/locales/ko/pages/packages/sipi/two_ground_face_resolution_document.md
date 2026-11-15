# 면별 금속 선로의 유한 해상도 평가 저장

[English](../../../../../packages/sipi/two_ground_face_resolution_document.md)

`TwoGroundFaceResolutionDocument`는
[직접 유한 평가](two_ground_face_resolution.md)의 엄격한
`sipi.two-ground-face-resolution/1` 입력을 저장한다. 같은 명시적 계획을 공통
실행·요청·결과 기록·프로젝트·CLI 파일에 연결한다. 기존 전체 경계 스키마와
수치 한도는 유지한다.

다음 예제는 장 계산 없이 계획을 준비하고 정규화한다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_resolution_document import TwoGroundFaceResolutionDocument
from sipi.execution import normalize_saved
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
section = CrossSection([
    Layer('lower', .001, 3., tan_delta=.002),
    Layer('upper', .001, 5., tan_delta=.004)],
    [Trace('signal', 0., .0007, .0006, .00005)], .008, top='ground')
line = TwoGroundFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={}, conductors=dict(signal=dict(zip(('bottom','top','left','right'),
        [dict(metal,conductivity=s) for s in (58e6,35e6,21e6,45e6)]))),
    reference=dict(kind='surfaces', bottom=metal, top=dict(metal, conductivity=21e6),
                   sides=None, conductors={}),
    ground_thickness=35e-6, length=.02, panels_per_edge=64, ground_modes=128,
    interpolation_degree=16)
finer = dict(panels_per_edge=128, ground_modes=256, interpolation_degree=16)
outer = []
for width, modes in ((.016, 512), (.032, 1024)):
    raw = line.to_dict()
    raw['cross_section']['box']['width'] = width
    for key in ('edge_size', 'far_size', 'grade'):
        raw['cross_section']['mesh'][key] *= .5
    raw['panel'] = dict(finer, ground_modes=modes)
    outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
controls = dict(refined_panel_options=finer, outer_documents=outer,
    refinement_factor=.5, max_solves=6,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
request = TwoGroundFaceResolutionDocument(line, **controls)
text = request.dumps()
assert normalize_saved(text) == text
# Run the admitted plan explicitly when ready:
# assessment = request.analyze(max_evaluations=6)
```

루트 키는 schema·line·refined_panel·outer_lines·refinement_factor·max_solves·
tolerances 일곱 개다. 기준과 모든 외곽 선로는 면별 선로 스키마여야 한다.
중첩 허용량은 명시 SI 이름 R_ohm_per_m·L_internal_h_per_m·L_external_h_per_m·
C_f_per_m·G_s_per_m·C0_f_per_m 중 하나 이상을 선택하고 relative와 absolute를
모두 제공한다. 하한·추정 허용량·자동 외곽을 추가하지 않는다.

중복·누락·추가·비유한·잘못된 필드는 거부한다. 고정 기하·물리 접지면·금속·코팅·
거칠기·재료·포트를 포함한 전체 체적/패널/공동/외곽 계획을 장 계산 전에 검사한다.
입력은 분리된 스냅샷이다. 직접 API의 전체 선로 시도 한도 5..16을 유지하며
호출자 예산도 모든 예정 평가를 포함해야 한다. 미지원 진단과 입력 바이트 한도도
장 계산 전에 검사한다.

`request.analyze(max_evaluations=6)` 또는
`execute_saved(text, max_evaluations=6)`가 같은 직접 평가를 실행한다.
계산을 마친 수치 불일치는 `completed=true`, `accepted=false`와 complete 실행
상태를 유지한다. 장/비교 예외는 계획을 멈추고 실패 단계·정확한 입력·완료한 prefix와
확보한 전류/메시 typed 원인 상세를 보존한다. 중단은 전파한다. CLI는 원본 파일을
유지하고 부분 실패를 포함한 실행 receipt를 쓴다.

부분 실패 평가를 저장하려면 `SavedExecutionRecord`에서 명시적으로
`sipi.execution-record/2`를 선택한다. version1은 이 변형을 계속 거부한다.
version2는 장 계산 없이 정확한 예정 prefix·단계·개수·입력·전류/메시 증거와
실패 원인의 연결을 검사한다. 바뀐 면별 입력이나 원인 상세가 조용히 다른 계획으로
바뀔 수 없다. 구조 검사와 선언된 artifact hash는 물리적 진실성을 증명하지 않는다.
요청·기록·선택한 프로젝트 결과를 복원해도 장 계산하지 않는다.

물리 저장 시험은 직접 API에 등록된 적층 단선 사례를 반복한다. 2/5 GHz·선로 평가
6회·행렬량 여섯 개·상대0.01/절대0을 유지하고 평가 결과 전체를 이전 직접 관측 및
설치본 결과와 정확히 비교한다. 직접 연구의 독립 특성 임피던스·원소별·차동쌍 검증은
별도 근거다. 합성 시험은 여섯 실패 위치·계산 완료 불일치·잘못되거나 변조된 기록·
중단·CLI 거부·프로젝트 복원을 확인한다. 이 전달 검사는 연속대역·실측 정확도·임의
외곽·새 플랫폼을 검증하지 않는다.
