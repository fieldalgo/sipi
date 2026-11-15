# 두 접지면 면별 선로 저장

[English](../../../../../packages/sipi/two_ground_face_panel_line.md)

`TwoGroundFacePanelTransmissionLineDocument`는 직접
[면별 도체 모델](two_ground_face_conductor.md)을 동일 기하의 유전체 추출 및
기존 RLGC 네트워크와 함께 저장한다. 명시적 스키마는
`sipi.two-ground-face-panel-transmission-line/1`이다. 기존
[전체 표면 문서](two_ground_panel_line.md)의 스키마와 의미는 유지한다.

```python
from sipi import CrossSection, CrossSectionDocument, Layer, Trace
from sipi.two_ground_face_panel_line import TwoGroundFacePanelTransmissionLineDocument

metal = {"conductivity": 58e6, "relative_permeability": 1.0,
         "roughness": {"kind": "smooth"}}
section = CrossSection(
    [Layer("substrate", 0.002, 4.0, tan_delta=0.003)],
    [Trace("signal", x=0.0, width=0.0006, y=0.0007, thickness=0.00005)],
    width=0.008, top="ground",
)
doc = TwoGroundFacePanelTransmissionLineDocument(
    CrossSectionDocument(section, mesh={"edge_size": 5e-6,
                         "far_size": 0.0001, "grade": 0.05}),
    [1e9, 3e9, 10e9], materials={},
    conductors={"signal": {face: metal for face in ("bottom", "top", "left", "right")}},
    reference={"kind": "surfaces", "bottom": metal, "top": metal,
               "sides": None, "conductors": {}},
    ground_thickness=35e-6, length=0.02,
    panels_per_edge=64, interpolation_degree=16,
)
text = doc.dumps()
restored = TwoGroundFacePanelTransmissionLineDocument.loads(text)
result = restored.analyze()
```

최상위 필드는 정확히 `schema`, `cross_section`, `frequency_hz`, `materials`,
`conductors`, `reference`, `ground_thickness_m`, `length_m`, `reference_ohms`,
`panel`이다. 패널 제어는 명시적 `panels_per_edge`, `ground_modes`,
`interpolation_degree`이다. SI 단위·기존 메시 자원 한도·직접 면별 모델의
허용 조건을 적용한다. 신호는 네 이름의 면별 금속 기록을 정확히 포함한다.
접지 도체는 전체 표면 법칙 또는 `kind: "faces"`와 네 법칙을 선택한다.
기존 bulk·거칠기·평면 코팅 기록을 재사용한다.

정규화는 장을 풀지 않고 선택적 공유 모서리 기능의 설치도 요구하지 않는다.
중복 키·알 수 없거나 누락된 중첩 키·비유한 JSON·미지원 도체 형상·잘못된
신호/기준면 매핑·재료·표피 깊이/잔여 코어 위반을 거부한다. 접근자와 저장
입력은 분리된 스냅샷이다. 공유 기능과 수치 수렴은 실제 해석할 때 검사한다.

한 번의 공유 전류 풀이에서 면별 계수와 원래 전체 경계 근거를 얻는다.
같은 단면으로 저장된 유전체 메시를 만들고 신호 순서를 검사한 뒤 C/G를
전류 모델의 진공 C0·외부 인덕턴스·면별 가중 도체 손실과 결합한다. 이후
기존 전송선 네트워크를 구성한다. 모든 제어와 실제 메시 식별 정보를
보존하며 전류 계산 방법을 다른 장 방식으로 자동 전환하지 않는다.

`result.current_record()`는 `kind: "two-ground-rectangle-face-panels"`이고
면 라벨·부호 전류·전류 Gram 및 원래 `whole_current` 기록을 포함한다.
`result.mesh_record()`는 실제 유전체 메시 관측을 반환한다. 둘 다 분리된
SI 딕셔너리이다.

공통 저장 실행·요청·기록·프로젝트·CLI 경로가 이 스키마를 받는다. 주파수
개수 예산은 장을 풀기 전에 검사한다. 완료 기록은 정확한 입력·RLGC·네트워크·
선택적 특성 임피던스/모드 진단·면별 표면 법칙·전류/메시 정보를 보존한다.
단계별 `TwoGroundFacePanelLineError`는 재료 검사·도체 검사·전류 풀이·메시·
유전체 추출·네트워크 구성에서의 실패에 대해 원입력·원인과 완료된 전류나
메시를 보존한다. 기록과 프로젝트를 다시 열 때 장을 재계산하지 않는다.

직접 모델의 표피 깊이·국소 평면 코팅·유한 외곽 한계는 그대로이다. 저장
실행 성공은 수렴·정확도 인증, 아이 다이어그램 계산, 새 브라우저 폼 완성을
뜻하지 않는다. 설계 판단 전에 기하·면별 양·유전체 메시·주파수 범위를
독립적으로 검증해야 한다. native/Worker 일치와 패키지 플랫폼 수락도
별도 검사이다.
