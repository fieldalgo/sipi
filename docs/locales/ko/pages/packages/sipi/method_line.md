# 전류 방법을 명시한 저장 선로

`MethodTransmissionLineDocument`(`sipi.method-transmission-line/1`)는 정규
[전송선 문서](line_model.md)를 감싸고, 도체 표면 전류를 어느 기존 계산이 구할지
밝힙니다. 필드는 정확히 `schema`, `line`, `current_method`이고, panel 방법일 때만
`panel`(`panels_per_edge`, `ground_modes`, `interpolation_degree`; 아래·위·옆이 모두 열린
단면은 `ground_modes` 없음)이 더해집니다.
`current_method`에는 기본값이 없습니다. [transmission-line/8](default_line.md)은 같은 선택을
선로 안에 저장하고, `surface`·`surface-boundaries` 도체의 기본값을 `panel`로 하며, 이 문서를
거쳐 실행됩니다.

| `current_method` | 단면 | 실행하는 문서 | 도체 |
|---|---|---|---|
| `volume-p1` | 선로가 받는 모든 단면 | 감싼 선로 그대로(P1 부피 메시 표면 전류) | 선로와 같음 |
| `panel` | 아래 접지, 열린 위·옆 | [`sipi.panel-transmission-line`](panel_line.md) /1(선로 /1–/6) 또는 /2(/7) | perfect, surface, surface-boundaries |
| `panel` | 위아래 접지, 열린 옆 | [`sipi.two-ground-panel-transmission-line/1`](two_ground_panel_line.md) | surface, surface-boundaries |
| `panel` | 아래·위·옆 모두 열림(접지 트레이스만) | [`sipi.open-panel-transmission-line/1`](open_panel_line.md) | perfect, surface, surface-boundaries |

panel 방법에서 `surface` 도체는 모든 경계에 같은 금속을 준 것으로 넘깁니다. 각 신호와
기준에 그 금속을 준 `surface-boundaries`이며(전송선 /1·/2는 /3이 되고, /1의
`roughness_rms`는 `{"kind": "hammerstad", "rms_m": ...}`가 됩니다), 위아래 접지에서는
아래·위 평면과 접지 트레이스가 기준 금속을, 열린 옆면은 금속 없음을 받습니다. 접지 평면이
없으면 접지 트레이스들이 기준 금속을 함께 받습니다.
`equivalent_document()`가 실행되는 문서를 돌려줍니다.

```python
from sipi.method_line import MethodTransmissionLineDocument

line = TransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    schema='sipi.transmission-line/2',
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1., roughness=dict(kind='smooth')))
saved = MethodTransmissionLineDocument(line, current_method='panel',
    panel=dict(panels_per_edge=64, ground_modes=512, interpolation_degree=14))
result = saved.analyze()
```

## 검사하는 것

- 생성할 때 선로, 방법, 정확한 키를 검사하고, panel 방법이면 panel 문서가 필드 계산
  없이 하는 검사(단면 경계, 양의 도체 두께, 도체 종류, panel 설정, 도체·패널 수 한도)를
  모두 합니다. 공유 panel 커널의 나머지 조건(벽 거리, 가로세로비, 볼록성, 적분 수렴)은
  `analyze()`에서 검사합니다.
- 거절된 panel 계산을 부피 방법으로 바꾸지 않습니다.
- R, L, G, C, S는 동등 문서와 비트 단위로 같고, 결과는 이 입력을 `input_json`으로
  유지합니다. `sipi run`과 `execute_saved`는 동등 문서의 결과에
  `current_method = {method, equivalent_schema}`를 더해 돌려줍니다.

## 명시해서 고르는 이유

P1 부피 메시 표면 전류는 느리게 수렴합니다. 두 microstrip, grounded coplanar,
stripline에서 기본 메시 설정의 P1은 panel 값보다 12–19% 낮았고 C0는 4e-4 안에서
일치했습니다([도체 손실](conductor.md)). panel 방법은 모든 단면에 쓸 수 있지는 않지만,
전형 입력과 템플릿 기본 상자에서는 고정한 공유 리비전으로 템플릿 72개 모두가 panel
전류를 계산합니다(보간 상자·범위 변경 전에는 20개였고, 그 변경으로 결합·적층·broadside
stripline 10종, 벽에 자신의 크기보다 가까운 grounded coplanar·coplanar stripline 21종,
폭/높이 64까지의 적층 coplanar stripline 3종이 계산됩니다). 접지 평면이 없는 단면 18종은
[open-box panel 선로](open_panel_line.md)를 씁니다. 다른 경계 조합(예: 접지된 옆면)은
거절됩니다. 기존 전송선 문서와 결과는 바뀌지 않습니다.
