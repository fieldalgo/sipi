# 물리적 면별 금속의 유한 해상도 평가

[English](../../../../../packages/sipi/two_ground_face_resolution.md)

`assess_two_ground_face_line_resolution`은 명시적
[면별 금속 선로](two_ground_face_panel_line.md)를 받는다. 물리적 면별 법칙을
보존하며 체적·패널·외곽 폭 변경을 별도로 평가한다. 직접 API이며 기존 전체 경계
입력과 저장 스키마는 유지한다. 계산을 완료해도 기준에 미달할 수 있다.
유한 일치는 절대 오차 추정이나 점근적 수렴의 인증이 아니다.

다음 예제는 장 계산 없이 입력을 준비한다. 마지막 줄의 주석을 해제하면
전체 평가를 실행한다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_resolution import ResolutionTolerance
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument
from sipi.two_ground_face_resolution import assess_two_ground_face_line_resolution
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
# Run the six line evaluations explicitly when ready:
# assessment = assess_two_ground_face_line_resolution(line, **controls)
```

장 계산 전에 전체 계획을 검사한다. base·체적 단독·패널 단독·공동 입력을 계산한 뒤
명시한 더 넓은 상자를 평가한다. `max_solves`는 5..16이며 실패를 포함한 전체 선로
시도를 센다. 내부 선형계 수가 아니다. 외곽 문서가 하나 이상 필요하다. 체적 세분은
edge_size·far_size·grade에 명시한 1 미만 인자를 곱한다. 세 패널 제어값은 모두
명시하고 하나 이상 증가해야 하며 감소할 수 없다. 외곽 입력은 공동 패널 해상도를
유지하되 더 넓은 영역을 위해 ground_modes만 늘릴 수 있다.

외곽 문서는 양쪽 물리 접지면을 이동하지 않고 열린 측면을 엄격히 확장한다.
도체·내부 경계·유전체 모델·주파수/신호 순서·포트·길이·모든 면의 금속/코팅/거칠기와
참조 법칙을 유지한다. 유한 열린 측면은 법선 플럭스 0이며 방사 경계가 아니다.
전체 경계 입력을 자동 변환하지 않는다. 대체 경로·재시도·자르기·자동 외곽 추정은 없다.

R·L_internal·L_external·C·G·C0 중 하나 이상을 선택하고 SI 단위의
`ResolutionTolerance(relative, absolute)`를 명시한다. 주파수별 모든 원소를
absolute + relative*max(abs(a),abs(b))로 검사하며 작은 원소의 하한은 없다.
체적과 패널은 각각 base와, 공동은 각 단독 축과, 외곽은 공동 결과와 비교한다.
미선택 물리량은 평가하지 않는다. 기록은 정확한 입력·실제 전류/메시 관측·차이·
허용량을 보존한다. 예외는 후속 평가를 멈추고 완료한 작업·단계·실패 입력과 확보한
전류/메시 typed 원인을 유지한다. 중단은 전파한다.

등록된 단선 시험은 예제의 두 유전체 층과 2/5 GHz를 사용한다. 두 번째는 균일한
2 mm 유전체에서 폭 0.43 mm·간격 0.28 mm·두께 50 µm·높이 0.975 mm인 같은
크기의 두 도체를 2/3.5/5 GHz로 검사한다. 두 도체의 면별 전도율 배치는 서로 반대이고
양쪽 접지는 58 MS/m이다. 두 사례 모두 degree16·패널64/128·접지모드128/256·
체적 설정 절반·외곽 폭16/32mm와512/1024모드를 사용한다. 선택한 여섯 행렬량 모두
모든 축에서 상대0.01/절대0을 통과해야 한다. 독립 스칼라/행렬 제곱근으로 특성
임피던스를 확인하며 균일 쌍은 C/G 및 외부L/C0 불변식도 확인한다. 판정 전에 실제
관측을 기록한다. 합성 시험은 각 실패 단계·원소별 한도·물리 변경 거부·완료 여부와
중단을 확인한다.

이 유한 사례는 임의 큰 상자에서 기본 모드 수의 적합성·연속대역/실측 정확도·모든
제조 기하·브라우저/플랫폼 수락을 증명하지 않는다. 이전 실패 관측과 기준은 유지한다.

[면별 금속 평가·부분실패 기록 저장](two_ground_face_resolution_document.md)
