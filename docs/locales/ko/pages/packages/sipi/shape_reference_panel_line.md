# 접지 금속을 분리한 선로 저장

`ShapeReferencePanelTransmissionLineDocument`는 [접지 경계별 전체 둘레
금속 모델](shape_reference_conductor.md)에 맞는 유전체장·RLGC·선로 회로를
함께 저장합니다. 명시 스키마는 `sipi.shape-reference-panel-transmission-line/1`
이며 기존 저장 스키마와 전류 방식의 동작은 유지합니다.

최상위 키는 `schema`, `cross_section`, `frequency_hz`, `materials`,
`conductors`, `reference`, `ground_thickness_m`, `length_m`, `reference_ohms`,
`panel`, `step_fraction`으로 고정합니다. 길이 m, 주파수 Hz, 전도도 S/m,
임피던스 Ω입니다. `cross_section`은 저장 단면/1·/2·/3이며 `materials`는
기존 유전체 기록을 씁니다. `conductors`는 모든 신호 이름과 bulk/거칠기 또는
적층 금속 기록을 정확히 대응시킵니다. `reference`는 `kind: surfaces`,
바닥 금속, null인 top/sides, 모든 접지 패턴의 `conductors`를 명시합니다.
접지 패턴마다 전체 둘레 금속 하나를 지정하며 면별 법칙은 거부합니다.
별도의 공통 접지 기본값이 겹치지 않습니다. 유한 두께·볼록 도체·바닥 접지·
위/옆 열린 경계 조건은 그대로입니다.

적층 금속은 conductivity·relative_permeability와 바깥→안쪽 순서의
`coatings` 배열(최대 32개)을 가집니다. 각 층은 thickness_m·conductivity·
relative_permeability를 명시합니다. Bulk/거칠기 기록에는 conductivity·
relative_permeability·roughness를 넣습니다. 기존 모델 정의와 양도체·각 경계의
표피 깊이·남은 코어 검사를 전계 계산 전에 적용합니다. 정규화에서는 저장된
패널 제어와 두 형상 이동폭을 장 계산 없이 사전 검사합니다. 실제 계산에서는
공유 솔버의 적분·기하·조건수 검사도 수행합니다.

전류 계산의 C0·외부 L에 맞추어 저장 체적 메시 하나에서 C/G를 구하고,
국소 금속 법칙으로 R·내부 L을 계산합니다. 결과에 정확한 입력·메시/전류 제어·
모든 전류 표본을 남깁니다. 공통 실행은 특성/모드 진단과 `current_solver`,
`conductor_boundaries`를 저장합니다. 경계 기록에는 순서 있는 이름·표피 깊이·
거칠기·복소 표면 임피던스·개별 저항 기여·합산 전 형상 에너지 행렬이 있습니다.
순서는 신호, 바닥, 기하 순서의 접지 패턴입니다. 합산 전류 적분은 원
`current_solver`에 남으며 에너지 행렬에서 면별 또는 바닥/패턴별 전류 적분을
추정하지 않습니다.

실행 중 단계 오류는 원인·정확한 입력·완료된 전류 또는 부분 전류 요청을
보존하는 `ShapePanelLineError`입니다. 공통 실행은 null 결과와 해당 오류를
가진 failed를 반환합니다. KeyboardInterrupt는 전파합니다. 기존 요청·실행
기록/1·/2·프로젝트·CLI로 입출력할 수 있습니다. 주파수 예산은 장 계산 전에
검사하지만 솔버 메모리나 실행 시간을 제한하지는 않습니다.

다음 예제는 장 계산 없이 코팅 접지 패턴 입력을 생성하고 정규화합니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi import ShapeReferencePanelTransmissionLineDocument
from sipi.execution import normalize_saved

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True),
    Trace('b', .0005, .0004, .001, 60e-6),
], .02)
coated_guard = dict(kind='layered', conductivity=58e6,
    relative_permeability=1., coatings=[
        dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.),
        dict(thickness_m=1e-6, conductivity=40e6, relative_permeability=1.)])
doc = ShapeReferencePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.0005, grade=.1)),
    [1e9, 4e9, 16e9], materials={},
    conductors={'a': metal(58e6), 'b': metal(35e6)},
    reference=dict(kind='surfaces', bottom=metal(45e6), top=None, sides=None,
                   conductors={'guard': coated_guard}),
    ground_thickness=35e-6, length=.02, panels_per_edge=32,
    ground_modes=1024, interpolation_degree=16, step_fraction=.001)
text = doc.dumps()
assert text == normalize_saved(text)
# result = doc.analyze()  # Runs actual current and dielectric field solves.
# from sipi import SavedExecutionRequest
# receipt = SavedExecutionRequest(text, diagnostics=['characteristic', 'modes']).run()
```

독립 균질 유전체/LC 불변식·bulk/코팅 전달식·수동 상반 4포트 식·선택 패널/체적
세분과 직접 API 전류의 정확한 보존을 검사합니다. 유한 외곽 변화는 관측이며
외곽 수렴 수락 기준이 아닙니다. 임의 기하·작은 상호항 정확도·실측 동박 특성·
브라우저 실행·플랫폼 배포 지원을 입증하지 않습니다. 국소 평면 코팅식은
코팅 모서리나 금속 내부 확산을 해석하지 않습니다.
