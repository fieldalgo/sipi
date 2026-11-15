# 두 접지 면별 금속 선로의 제한적 연속 세분

[English](../../../../../packages/sipi/adaptive_two_ground_face_resolution.md)

`refine_two_ground_face_line_resolution`는 명시적인
[유한 해상도 비교](two_ground_face_resolution.md)를 미리 정한 두~네 세분 단계로 확장한다.
같은 물리 접지면·면별 금속 법칙·유전체 모델·포트 순서·원래 전류 검증 기준을 유지한다.
새 기본 솔버를 선택하거나 지정하지 않은 후속 패널 설정을 추정하지 않는다.

예제는 장 계산 없이 계획을 구성한다.

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
# Run the bounded plan explicitly when ready:
# assessment = refine_two_ground_face_line_resolution(line, **controls)
```

각 단계는 선택한 모든 원소·주파수에 대해 volume/base·panel/base·joint/volume·
joint/panel을 비교한다. 두 단계가 연속 통과해야 외곽 검사를 시작하며 실패한 단계는
연속 횟수를 초기화한다. 직전 joint 계산은 다음 base로 재사용한다. 예제가 수락되면
완전한 선로 배치 아홉 개와 비교 열 개를 실행한다. 단계마다 외곽 크기·순서를 고정하고
그 단계 joint 패널 제어에 비해 접지 모드만 더 늘릴 수 있다.

장 계산 전에 모든 예정 단계·외곽 입력을 검사한다. 메시 제어는 정확한 순차 세분 값을
써야 한다. 거듭제곱을 한 번에 곱하면 반올림이 달라져 엄격한 입력 계약상 같지 않을 수
있으므로 예제는 각 단계에서 메시 사전을 갱신한다. 물리 치수·재료·허용오차를 자동
보정하지 않는다. `max_solves`는 전체 선로 시도8..32개이며 내부 풀이·메모리·시간의
상한이 아니다. 다음 단계의 세 배치와 외곽 전체가 잔여 예산에 들어야 그 단계를 시작한다.

결과는 `accepted`, `resolution-unaccepted`, `outer-unaccepted`, `budget-exhausted`,
`field-failed`를 구분한다. 단계/외곽 불일치는 완료됐지만 미수락한 계획이며 예산 소진·
장 실패는 미완료다. 두 연속 통과와 외곽 전체 통과 후에만 선택 joint 결과가 있다.
외곽 불일치는 추가 세분 없이 중단한다. typed 실패는 정확한 시도 입력·이전 결과·
전류/유전체 메시 관측을 보존하고 중단 예외는 전파한다. `to_dict()`에 모든 비교와
원래 관측을 담는다.

등록 층상 단일선 및 균일 Debye 쌍선 예제는64→128→256패널·128→256→512접지모드·
차수16·순차 메시 인자0.75를 사용한다. 선택 단계의16/32mm 외곽은1024/2048모드다.
여섯 행렬량에 상대1%·절대0의 원소별 비교를 적용하며 작은 원소 바닥값은 없다.
독립 행렬제곱근 전진 임피던스는1e-10에서 검사하며 쌍선은 균일 Debye C/G와 진공LC
불변식도 확인한다. 합성 검사는 모든 단계·마지막 주파수 상호성분·연속 횟수 초기화·
후속 계획 거부·예산 예약·외곽 중단·계획 복사/불변성·typed 실패를 확인한다.

명시 사례의 유한 일치 검사이며 이산화 오차 경계·점근 수렴 증명·실측 정확도 인증·
연속 대역 보장·플랫폼 수락이 아니다. 일치해도 공통 계통오차는 남을 수 있다.
기존 수치 허용오차와 해석 방법은 바꾸지 않는다.
