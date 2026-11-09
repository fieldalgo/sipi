# 패널 전류를 명시하는 저장 선로

[명시적 두 매개변수 역산](panel_pair_goal.md)은 체적·패널·동시 세분을 각각 검증합니다.

`PanelTransmissionLineDocument`는 공유 경계 패널 진공 전류와 기존 유전체
장 추출을 명시적으로 조합합니다. `sipi.panel-transmission-line/1` 입력은
정확히 `schema`, `line`, `panel`을 갖습니다. `line`은 정규화된 기존
`TransmissionLineDocument`이며 `panel`은 `panels_per_edge`, `ground_modes`,
`interpolation_degree`를 저장합니다. 생성자 기본값을 사용해도 세 제어값을
모두 기록합니다.

중첩 선로의 도체 모델은 `perfect` 또는 `surface-boundaries`여야 합니다.
다른 표면 모델을 암묵적으로 변환하지 않습니다. 기존 선로 문서 1–6과
기본 계산 방법의 계약은 유지됩니다. 패널 선로를 일반 선로 문서로 읽어
선택한 전류 계산 방법을 조용히 잃는 동작도 허용하지 않습니다.

생성과 정규화는 메시나 장을 계산하지 않습니다. 기존 선로 입력,
엄격한 키 집합, 주파수·재료·금속 규칙, 아래 접지와 위·옆 open 조건,
양의 도체 두께와 정수 패널 제어값을 검사합니다. 중복 키와 유한하지
않은 JSON 수는 거부합니다. 입력은 복사해 보관하므로 호출자 사전,
반환된 사전이나 중첩 선로 접근자를 변경해도 보관된 입력은 바뀌지 않습니다.

공유 커널의 볼록성·이격·종횡비·조건수·수치 세분 검사는 실제 계산 때
수행합니다. JSON 정규화 성공이 그 검사나 물리적 유효범위의 통과를
보장하지는 않습니다. [패널 도체 손실](panel_conductor.md)에 설명한
정확한 공유 의존성 아티팩트가 필요합니다.

## 일치하는 입력으로 한 번의 계산

1. 진공 패널 전류 계수를 계산합니다. 명시적 접지 도체는 전위 0을
   유지합니다. `surface-boundaries`에서는 기존 금속별 표면 법칙과 표피
   깊이 제한을 적용합니다. 패널 계산이 실패하면 유전체 메시를 만들기
   전에 그 오류를 전달합니다.
2. 저장된 기하 메시 설정으로 유전체 메시 하나를 만듭니다.
3. 기존 재료 표본과 유전체 추출을 재사용하되 진공 기준으로 패널 C0를
   전달합니다. 공간적으로 균일한 스칼라 유전체는 같은 C0에 복소 유전율을
   곱해 C와 G를 얻습니다. 비균일 또는 텐서 유전체는 기존 체적 장 풀이를
   사용합니다.
4. 표면 법칙의 R·내부 L과 mu_0 epsilon_0 inverse(C0)의 외부 L을
   조합합니다. 이 RLGC로 기존 균일 선로 회로와 선택적 특성·모드 진단을
   계산합니다.

결과에는 패널 선로 전체 JSON, 해석된 체적 메시 설정, 패널 설정과 전류
진단이 남습니다. R/L/G/C는 주파수별 SI 행렬입니다. 완전도체는 R=0과
내부 L=0을 명시적으로 사용하면서 패널 외부 인덕턴스를 유지합니다.
`characteristic()` 등 기존 선로 결과의 연산도 같은 행렬을 사용합니다.

다른 솔버로 전환하거나 기하를 자동 변경하거나 요청하지 않은 패널
세분을 수행하지 않습니다. 패널 분해, 체적 메시 분해, 유한 외곽 크기는
서로 다른 수렴 검사입니다. 패널 외곽은 아래에서 접지이고 나머지 벽에서
법선 미분이 0이며, 무한 개방 영역과 동일하지 않습니다.

## 검증과 한계

엄격한 저장·복원, 이전 저장 입력 보존, 입력 격리, 장 계산 없는 정규화,
일치하는 C0와 인덕턴스, 균일 유전체 배율, 금속 조립, 유전체 메시 1회와
독립 2N 특성 임피던스 풀이 및 수동·상호 회로를 검사합니다. 비균일 두
선로 연구는 원래 세 체적 분해와 세 외곽 크기에서 유전체 장을 다시 풀고
해당 명시적 패널 분해를 사용합니다. 이후 행렬 재조합으로 체적과 패널
축을 분리할 수 있지만, 그 조합을 추가 장 풀이 횟수로 표현하지 않습니다.

이 검사는 고정 입력의 구현과 수렴을 검증합니다. 역산 성공, 임의 배치의
정확도, 재료 피팅의 유효성이나 실측 하드웨어와의 일치를 보장하지 않습니다.
기존 준 TEM·일차 표면 임피던스 제한은 그대로 적용됩니다. 도체 내부
전류 확산, 동박 면별 독립 법칙, 임의 비볼록 패널 기하와 분포 3D 전이는
이 경로의 지원 범위 밖입니다.

## 사용 예

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.line_model import TransmissionLineDocument
from sipi.panel_line import PanelTransmissionLineDocument
from sipi.execution import execute_saved

section = CrossSection(
    [Layer("uniform", .002, 4.2, tan_delta=.02)],
    [Trace("left", -.0003, .0005, .0002, thickness=35e-6),
     Trace("right", .0003, .0005, .0002, thickness=35e-6)],
    .004,
)
metal = dict(conductivity=58e6, relative_permeability=1.,
             roughness={"kind": "smooth"})
line = TransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(
        edge_size=10e-6, far_size=.2e-3, grade=.1)),
    [1e9, 2e9], materials={},
    conductor=dict(kind="surface-boundaries",
        conductors={"left": metal, "right": metal}, reference=metal,
        ground_thickness=35e-6),
    length=.02, schema="sipi.transmission-line/3",
)
document = PanelTransmissionLineDocument(line, panels_per_edge=16)
text = document.dumps()
assert PanelTransmissionLineDocument.loads(text).dumps() == text
output = execute_saved(text, max_evaluations=2,
                       diagnostics=["characteristic"])
assert output["status"] == "complete"
assert output["result"]["current_solver"]["settings"]["panels_per_edge"] == 16
```
