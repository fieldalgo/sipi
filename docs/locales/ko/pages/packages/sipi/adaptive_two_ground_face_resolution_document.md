# 두 접지 면별 금속의 제한적 세분 계획 저장

[English](../../../../../packages/sipi/adaptive_two_ground_face_resolution_document.md)

`AdaptiveTwoGroundFaceResolutionDocument`는
`sipi.adaptive-two-ground-face-resolution/1`을 저장한다. 최상위 여섯 키는 `schema`,
`line`, `refinements`, `tolerances`, `refinement_factor`, `max_solves`다.
[직접 제한 계획](adaptive_two_ground_face_resolution.md)의 두~네 명시 단계·
외곽 전 두 연속4방향 통과·다음 단계/외곽 전체 예산 예약·원 typed 실패 계약을 유지한다.
각 단계는 `refined_panel`과 순서 있는 `outer_lines`를 저장한다. 허용오차 물리량은
명시 SI 이름을 사용하고 relative/absolute를 모두 지정한다. 중첩 선로 버전과
물리적인 면별/접지 법칙은 명시적으로 유지한다.

아래 코드는 장을 풀지 않고 입력을 준비하고 검사한다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
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
from sipi.adaptive_two_ground_face_resolution import (
    TwoGroundFaceResolutionRefinement, refine_two_ground_face_line_resolution)
steps = []
mesh = line.to_dict()['cross_section']['mesh']
for level in (1, 2):
    for key in ('edge_size', 'far_size', 'grade'):
        mesh[key] *= .75
    panel = dict(panels_per_edge=64*2**level, ground_modes=128*2**level,
                 interpolation_degree=16)
    outer = []
    for width, modes in ((.016, 256*2**level), (.032, 512*2**level)):
        raw = line.to_dict()
        raw['cross_section']['box']['width'] = width
        raw['cross_section']['mesh'] = dict(mesh)
        raw['panel'] = dict(panel, ground_modes=modes)
        outer.append(TwoGroundFacePanelTransmissionLineDocument.from_dict(raw))
    steps.append(TwoGroundFaceResolutionRefinement(panel, outer))
controls = dict(refinements=steps, refinement_factor=.75, max_solves=9,
    tolerances={key: ResolutionTolerance(.01, 0.) for key in
                ('R', 'L_internal', 'L_external', 'C', 'G', 'C0')})
assert len(steps) == 2

from sipi.adaptive_two_ground_face_resolution_document import AdaptiveTwoGroundFaceResolutionDocument
from sipi.execution_request import SavedExecutionRequest
saved = AdaptiveTwoGroundFaceResolutionDocument(line, **controls)
request = SavedExecutionRequest(saved.dumps(), max_evaluations=9)
assert AdaptiveTwoGroundFaceResolutionDocument.loads(saved.dumps()).dumps() == saved.dumps()
assert request.to_dict()['input'] == saved.to_dict()
# receipt = request.run()
```

실효 전체 선로 예산은 저장된 `max_solves`와 호출자 `max_evaluations` 중 작은 값이다.
두 단계와 외곽 전체를 예약할 수 없는 호출자 예산은 장 계산 전에 거부한다.
입력 바이트와 diagnostic 제어도 계산에 앞선다. 완료된 불일치는 complete지만
미수락이고 장 실패/예산 소진은 부분 결과를 유지하며 실행 상태 failed가 된다.
실패 계획에는 적격 선택 결과가 없다.

부분 실패를 저장하려면 `sipi.execution-record/2`를 명시한다. 버전1의 기존 거부는
유지한다. 버전2 재열기는 원래 입력과 호출자 예산에서 장 계산 없이 계획을 재구성한다.
단계/외곽 수·정확한 시도 입력과 평가 순서·비교 순서/참조·두 연속 통과 흐름·전류/메시
근거·typed 원인의 결합을 검사한다. 후속 실패 단계는 시작할 때 세 배치와 외곽 전체를
수용할 수 있어야 한다. 기록된 실패 시도 하나만 예산에 들어가는 것으로는 부족하다.
예산 중단은 그 예약이 실제로 불가능해야 한다. 비교 실패는 완료된 선로 계산을 유지하되
성공 비교를 만들지 않는다. 프로젝트/CLI 재열기는 장을 다시 풀지 않는다.

물리 저장 단일선 사례는 직접 계획의 아홉 선로 배치와 열 비교를 반복한다.
전체 입력·관측·차이·허용량·선택 평가를 앞선 직접 근거와 정확히 비교한다.
독립 스칼라 제곱근과 행렬제곱근 결과도 검사한다. 합성 검사는 모든 실패 연산·
후속 단계 입장·호출자 예산 소진·불완전 비교·완료 불일치·변조된 이력·CLI/프로젝트
복원을 포함한다. 후속 실패에 해당 단계를 예약할 수 없는 더 작은 호출자 예산을
붙인 기록을 별도 회귀 시험에서 거부한다.

기록 검증은 구조와 제어 흐름 일관성 검사이며 서명·산출물 인증·기록된 수치의 인증이
아니다. 유한 일치는 이산화 오차 경계·실측 정확도·연속 대역 수락·플랫폼 지원을
확립하지 않는다. 기존 해석 방법과 수치 기준은 바꾸지 않는다.
