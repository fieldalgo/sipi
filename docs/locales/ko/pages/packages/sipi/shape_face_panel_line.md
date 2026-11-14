# 면별 금속 형상전류 선로 저장

`ShapeFacePanelTransmissionLineDocument`는 명시 스키마
`sipi.shape-face-panel-transmission-line/1`로 [직선면 손실 API](shape_face_conductor.md),
저장된 유전체 메시와 균일 선로 네트워크를 연결합니다. 최상위 키는 정확히
`schema`, `cross_section`, `frequency_hz`, `materials`, `conductors`, `reference`,
`ground_thickness_m`, `length_m`, `reference_ohms`, `panel`, `step_fraction`의 11개입니다.
기존 스키마·기본 방법은 유지합니다.

`conductors`의 각 신호는 정확히 `bottom`, `top`, `left`, `right` 네 면을 갖습니다.
각 재료는 기존 transmission-line/7의 벌크·명시 거칠기 또는 바깥부터 안쪽 순서의
도금 문법을 씁니다. `reference`는 `kind: surfaces`, 아래 접지 재료, 위/옆 `null`,
정확한 접지 패턴 이름을 갖습니다. 각 접지 패턴은 전체 둘레 재료 하나 또는
`kind: faces`와 네 면 재료를 받습니다. 직접 API의 유한 직사각형/사다리꼴 1~4개,
아래 접지·위/옆 개방, 개별 침투 깊이/코어, 제한된 형상 제어 조건을 유지합니다.

문서 생성·엄격한 정규화는 재료와 모든 유한 변위를 검사하지만 전계는 풀지 않습니다.
중복·누락·여분 키와 비유한 JSON 수를 거부하며 접근자는 분리된 자료를 반환합니다.
실행 전에 명시 주파수 예산을 검사합니다. 이 예산은 주파수 표본 수이며 면별 추출의
공유 풀이 횟수 제한을 대체하거나 개별 풀이 시간을 보장하지 않습니다.

해석은 직접 API와 같은 PEC 면 에너지/C0/외부 L 및 저장한 유전체 메시 하나를 써서
같은 신호 기저의 C/G를 계산합니다. R은 표면 저항 가중합, L은 금속 내부 인덕턴스를
포함합니다. 저장된 길이와 양의 실수 기준 임피던스로 네트워크를 만듭니다.
기저·C0 일치가 임의 기하나 외곽 영역 정확도를 인증하는 것은 아닙니다.

아래는 전계 없이 저장·정규화하는 예제입니다. 마지막 호출의 주석을 해제하면
계산합니다. 길이는 미터, 주파수는 헤르츠입니다.

```python
from sipi import CrossSection, Layer, Trace, CrossSectionDocument
from sipi import ShapeFacePanelTransmissionLineDocument
from sipi.execution import normalize_saved

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
metal = {'conductivity': 58e6, 'relative_permeability': 1.,
         'roughness': {'kind': 'smooth'}}
faces = {name: metal for name in ('bottom', 'top', 'left', 'right')}
reference = {'kind': 'surfaces', 'bottom': metal, 'top': None, 'sides': None,
             'conductors': {'guard': {'kind': 'faces', **faces}}}
document = ShapeFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh={'edge_size': 10e-6, 'far_size': .0005, 'grade': .1}),
    [1e9, 4e9], materials={}, conductors={'a': faces, 'b': faces}, reference=reference,
    ground_thickness=35e-6, length=.02, panels_per_edge=32, ground_modes=4096)
saved = document.dumps()
assert saved == normalize_saved(saved)
assert ShapeFacePanelTransmissionLineDocument.loads(saved).dumps() == saved
# result = document.analyze()  # Starts fields; result retains R/L/G/C and S.
```

공통 실행은 R/L/G/C, 네트워크, 요청 진단과 명시 `conductor_boundaries`를 반환합니다.
경계 이름·침투 깊이·거칠기·복소 Zs·각 저항 기여·대응 에너지 행렬을 보존합니다.
`current_solver`의 kind는 `grounded-rectangle-face-capacitance-shape`이며 원래 패턴 순서,
신호/접지 표시, 면별 에너지, 두 변위 단계, 모든 면별 요청·표본과 원래 전체 전류의
`whole_current` 기록을 포함합니다. 원면 순서는 기하 순서이고 재료 가중 순서는
신호 면들·접지면·접지 패턴 그룹입니다. 두 순서와 이름을 모두 남깁니다.
부호 있는 면별 전류를 추정하지 않으며 그룹 보존 진단은 `whole_current`에 있습니다.

`ShapeFacePanelLineError`는 단계·원인·정규 입력·완료된 전류와 부분 계산을 보존합니다.
전체전류 실패는 원래 부분 요청을, 면별전류 실패는 완료된 전체전류까지 보존합니다.
이후 메시/유전체/네트워크 실패는 모든 면별 기록을 남깁니다. 중단은 그대로 전파합니다.
`execute_saved`는 이런 실패에 완료 결과 없이 `status: failed`를 반환합니다.
요청 영수증과 명시 execution-record/2는 전계를 다시 풀지 않고 부분 근거를 보존합니다.
execution-record/1의 기존 규칙은 유지합니다.

실제 저장/직접 전계의 일치, 균일 매질 불변식, 독립 평면 금속·4포트 식,
패널·유전체 메시 검사, 부분 실패, 원정규 기록을 구분해 검증합니다.
유한 외곽 관측은 별도 수렴 계약을 통과하지 않으면 미수락으로 남깁니다.
국소 도금·거칠기의 한계는 유지하며 작은 상호항의 절대 정확도·브라우저/EXE·새 플랫폼
검증으로 확대하지 않습니다. 자동 외곽 세분이나 면별 금속 최적화는 추가하지 않습니다.
