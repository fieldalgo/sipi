# 접지 평면 없는 저장 panel 선로

[English](../../../../../packages/sipi/open_panel_line.md)

`OpenPanelTransmissionLineDocument`(`sipi.open-panel-transmission-line/1`)는
아래·위·옆이 모두 열린 단면(unbacked coplanar 템플릿 등)의 [panel 선로](panel_line.md)입니다.
접지 평면이 없으므로 접지 트레이스가 기준이며 귀환 전류 전체를 나릅니다. 필드는 정확히
`schema`, `line`, `panel`이고 `panel`은 `panels_per_edge`(1–256)와
`interpolation_degree`(10, 12, 14, 16)만 가집니다(접지 모드 없음). 감싼 선로는
전송선 /1–/7, 도체는 `perfect` 또는 `surface-boundaries`, 도체 두께는 양수여야 합니다.
사용 예제는 영문 문서와 같습니다.

진공 전류는 공유 open-box panel 해법(`galerkin.laplace_open_box`)이 구합니다. 상자 네
벽 모두 법선 플럭스 0(부피 메시의 열린 경계와 같음)이고 모든 접지 트레이스가 0
전압입니다. 이 전류가 진공 정전용량과 외부 L을 주고, 기존 유전체 해법이 저장된 부피
메시에서 C·G를, 기존 경계별 표면 법칙이 R과 내부 L을 줍니다(모든 접지 트레이스가 기준
금속 하나를 공유). `ground_thickness`는 부피 경로와 같은 기준 표피 깊이 검사에 들어갑니다.
생성·정규화는 필드를 풀지 않습니다. 공유 핵의 허용 검사(볼록 다각형, 폭/높이
[0.25, 16], 벽 거리 보간 상자)와 1e-10 세분 검사는 `analyze()`에서 합니다. 거절된
계산을 부피 방법으로 대체하지 않습니다.

`execute_saved`와 `sipi run`은 선로 결과에 `current_solver.kind =
"open-rectangle-panels"`, 설정, 접지 트레이스 이름, 진공 정전용량, 표면 전류 인자,
해법 진단(`smooth_interpolation_boxes`, `charge_sum_error` 포함)을 더해 돌려줍니다.

unbacked coplanar 템플릿 3종(단일·결합·비대칭)에서 panel 진공 정전용량이 기본 메시의
독립 scikit-fem P2 해와 5e-4 이내로 일치합니다(측정 1.1e-4,
`tests/sipi/test_open_panel_line.py`). 같은 단면의 P1 부피 표면 전류는 panel 전류보다
낮으며 접지된 panel 경로와 같은 양상입니다. 공유 해법의 해석·급수 기준은 그 문서에
있습니다. 이는 유한 비교이며 일반 정확도 자격이 아닙니다. [전류 방법 명시](method_line.md)는
열린 단면에서 이 문서를 고릅니다.
