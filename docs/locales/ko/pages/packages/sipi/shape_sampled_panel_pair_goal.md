# 유한 주파수 격자의 명시 형상전류 목표 역산

[English](../../../../../packages/sipi/shape_sampled_panel_pair_goal.md) ·
[단일 주파수 형상전류 역산](shape_panel_pair_goal.md) · [기존 격자 검색](sampled_panel_pair_goal.md)

`seek_shape_sampled_panel_forward_pair_impedances`는 요청한 모든 주파수의 차동·공통
순방향 임피던스 실수부를 맞춥니다. 전체 복소 특성 행렬에서 구한 서로 다른 전력
쌍대 여기 값이며 모드 크기나 종단 입력 임피던스가 아닙니다. factory는
`ShapePanelTransmissionLineDocument`를 명시적으로 반환해야 하고 기존 역산의
계산 방식은 유지합니다.

양의 유계 변수 두 개와 엄격하게 증가하는 양의 주파수 2..64개가 필요합니다.
목표와 절대 허용차는 차동·공통 순서의 양의 실수 (N,2) 행렬이며 단위는 Ω입니다.
스칼라 조건의 암묵 확장은 거부합니다. 검색 중 신호 순서·주파수 벡터·길이 0·패널
제어·형상 이동폭은 고정합니다. 벌크·고정 코팅 금속의 유효 조건도 유지합니다.
유한 격자의 문제는 과결정이거나 허용 가능한 해가 없을 수 있습니다.

정수 4..10000인 예산은 실패·최적화 탐색을 포함한 캐시되지 않은 선로 전체 평가를
셉니다. 마지막 세 번은 선택한 입력의 체적 전용·패널 전용·동시 세분에 예약합니다.
향후 세분 입력은 검색 전계 전에 검사합니다. 선택 및 세분 결과의 모든 주파수가
원래 절대 허용차를 만족해야 합니다. 각 세분 값은 명목값 대비 0.5% 이내이며 동시
세분은 두 개별 세분과의 차이도 각각 0.5% 이내여야 합니다. 초기값이 목표에 맞아도
실제 네 번의 평가가 필요하고 실패 후보를 수락된 설계로 반환하지 않습니다.

아래 예제는 검색을 준비하고 실행하지 않습니다. 목표는 폭 .55 mm·간격 .35 mm인
저장된 유한 영역 계산에서 가져왔으며 **독립 전계 기준이나 실측값이 아닙니다**.
시작 변수는 목표 입력과 다릅니다. 길이는 m, 주파수는 Hz입니다.

```python
from sipi import asymmetric_coupled_microstrip, CrossSectionDocument
from sipi.dielectric import DebyeDielectric
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.shape_panel_line import ShapePanelTransmissionLineDocument
from sipi.shape_sampled_panel_pair_goal import seek_shape_sampled_panel_forward_pair_impedances

frequencies = [1e9, 2e9, 4e9]
def line(width, gap):
    section = asymmetric_coupled_microstrip(
        left_width=width, right_width=.5e-3, gap=gap,
        substrate_height=.2e-3, eps_r=1., tan_delta=0.,
        left_thickness=35e-6, right_thickness=50e-6,
        box_width=8e-3, air_height=3.75e-3)
    metal = dict(conductivity=58e6, relative_permeability=1., roughness={'kind':'smooth'})
    conductor = dict(kind='surface-boundaries',
        conductors={'positive':metal, 'negative':metal}, reference=metal,
        ground_thickness=35e-6)
    material = DebyeDielectric(3., (.7,), (1e9,))
    source = TransmissionLineDocument(
        CrossSectionDocument(section, mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)),
        frequencies, materials={'substrate':material, 'air':material},
        conductor=conductor, length=0., schema='sipi.transmission-line/6')
    return ShapePanelTransmissionLineDocument(PanelTransmissionLineDocument(source,
        panels_per_edge=16, ground_modes=512, interpolation_degree=16))

options = dict(factory=line, bounds=[[.4e-3,.7e-3],[.2e-3,.5e-3]],
    frequencies=frequencies,
    targets=[[68.8828994054204,21.90566648151497],
             [71.10351393482341,22.613365409231967],
             [72.29432825718574,22.993194259891602]],
    tolerances=[[.05,.025]]*3, initial=[.48e-3,.28e-3], max_evaluations=64)
assert line(.55e-3,.35e-3).to_dict()['line']['line']['frequency_hz'] == frequencies
# goal = seek_shape_sampled_panel_forward_pair_impedances(**options)
```

`ShapeSampledPanelForwardPairDesign`은 선택 선로·세 세분 선로·변수·주파수·목표·
허용차·전체 이력을 보존합니다. `to_dict()`는 선택·세분 결과의 전체 전류 기록을
추가하고 검색 이력에는 원입력과 임피던스를 남깁니다. 문서 접근자는 명시 계산
방식을 유지한 새 객체를 반환합니다. 이 보고서는 저장 요청·factory 스키마가 아닙니다.

`SampledPanelForwardPairGoalError`에 완료한 이력, 주파수 벡터, 실패 포함 시도 수,
단계, 변수·입력과 원인 예외가 남습니다. 원인이 `ShapePanelLineError`이면 상세
부분 전류 기록을 확인할 수 있습니다. 중단은 전파하고 다른 방식으로 조용히
대체하지 않습니다.

독립 모달 격자·단위 변환, 전체 주파수 목표·고정 제어 실패, 예약 예산과 기존
소비자를 검사합니다. 벌크·코팅 실제 검색은 목표 밖에서 시작하고 선택·개별 세분의
전계를 독립 균일 Debye·금속 전달식·4포트 불변식과 비교합니다. 유한 영역 목표는
역산의 자기 일관성 근거이며 독립 절대 정확도 근거가 아닙니다. 기존 작은 영역
외곽 미수락도 유지합니다. 전역 최적해·유일성·연속 대역·충분한 외곽·절대 정확도를
인증하지 않습니다.
