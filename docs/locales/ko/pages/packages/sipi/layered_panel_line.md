# 고정 금속 코팅을 사용하는 패널 선로

`sipi.panel-transmission-line/2`는 내부 `sipi.transmission-line/7`과 기존
패널 전류 계산을 명시적으로 결합합니다. 버전 1은 계속 내부 선로 1–6만
받습니다. `schema`, `line`, `panel` 키는 같고 생성자에서 새 버전을 명시합니다.

각 신호와 공통 귀환 경계는 서로 다른 벌크 금속과 순서가 있는 평면 코팅을
보존할 수 있습니다. 공유 진공 패널 계산의 전류 Gram 행렬에 기존 적층 표면
임피던스를 적용하여 R과 내부 L을 구합니다. 유전체 C/G는 하나의 체적 메시를,
외부 L은 같은 패널 C0를 사용합니다. 저장된 기하에 코팅 두께를 더하지 않습니다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved

section = CrossSection([Layer("uniform", .002, 4.2, tan_delta=.02)],
    [Trace("signal", 0., .0005, .0002, thickness=35e-6)], .004)
metal = dict(kind="layered", conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6,
                   relative_permeability=3.)])
line = TransmissionLineDocument(CrossSectionDocument(section,
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1)), [1e9, 2e9],
    materials={}, conductor=dict(kind="surface-boundaries",
        conductors={"signal": metal}, reference=metal, ground_thickness=35e-6),
    length=.02, schema="sipi.transmission-line/7")
document = PanelTransmissionLineDocument(line, panels_per_edge=32,
    schema="sipi.panel-transmission-line/2")
result = execute_saved(document.dumps(), max_evaluations=2)
assert result["status"] == "complete"
assert result["result"]["current_solver"]["kind"] == "grounded-rectangle-panels"
```

코팅에는 기존 잔여 코어·스킨 깊이·1차 표면 섭동 제한이 적용됩니다. 기하는
공유 패널 커널의 볼록성·경계 간격·자원 제한을 만족해야 합니다. 아래 접지,
열린 위·옆 경계와 양의 도체 두께가 필요합니다. 미지원 공통 표면 모델이나
면별 모델을 암묵적으로 바꾸지 않습니다. 완전 도체는 기존 패널 계산과 R=0을
유지하며 일반 FEM 전류 방식으로 전환하지 않습니다.

검증은 패널 세분·유전체 체적 세분·외곽 크기를 구분합니다. 고정된 두 선로
시험에서 전체 행렬을 보존하고 평면 전달 임피던스, 독립 4×4 선로 전달행렬,
상호성·수동성을 확인합니다. 최대 행렬 규준의 변화는 작은 상호항의 상대오차
상한이 아닙니다. 전류 방식을 바꿨다고 다른 방식의 실패가 해결되는 것은
아닙니다. 유한 외곽 검사는 무한 영역 또는 실측 정확도의 인증이 아니므로
실제 입력과 주파수에서 세 종류의 세분 검증을 각각 해야 합니다.

예를 들어 고정 대칭 쌍의 1 GHz 상호 R 항은 외곽 두 치수를 두 배로 늘릴 때
0.0859271에서 0.0460899 Ω/m로 약 46.4% 변합니다. 이때 최대 행렬 규준의 R
변화는 약 0.281%입니다. 패널 세분만으로도 작은 상호항은 약 1.07% 변합니다.
이 관측은 항별 수렴 근거가 아닙니다. 상호항을 포함하여 용도에 중요한 각
물리량의 절대·상대 한계를 명시적으로 정해야 합니다.

이번 버전은 저장된 순방향 계산을 추가합니다. 기존 직접 factory API로
[코팅 쌍 선로 역산](layered_panel_goal.md)도 수행할 수 있습니다. 저장형 코팅
목표 wrapper와 제조 공차 연결은 별도의 계약입니다. 기존 [패널 선로 제한](panel_line.md)과
[적층 금속 가정](layered_metal.md)도 적용됩니다.

[English](../../../../../packages/sipi/layered_panel_line.md)
