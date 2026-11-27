# 기본 panel 전류의 저장 선로

`sipi.transmission-line/8`(`sipi.default_line`의 `DefaultPanelTransmissionLineDocument`)은
[transmission-line/7](line_model.md)의 필드에 도체 전류 방법을 더한 문서입니다.
`surface`와 `surface-boundaries` 도체는 기본으로 panel 방법을 씁니다. 정규화할 때
`current_method`와, panel 방법이면 `panel`까지 항상 저장 문서에 적습니다. 그래서 기본값이
바뀌어도 저장한 선로의 방법과 제어값은 그대로입니다. transmission-line/1–/7 문서와 결과는
바뀌지 않습니다.

| 필드 | 규약 |
|---|---|
| `schema`, `cross_section`, `frequency_hz`, `materials`, `conductor`, `length_m`, `reference_ohms` | transmission-line/7과 같음 |
| `current_method` | `"panel"` 또는 `"volume-p1"`. 입력에서 생략할 수 있고 저장본에는 항상 있음 |
| `panel` | panel 방법에서만. 입력에서 생략할 수 있고 저장본에는 항상 있음: `panels_per_edge`, `ground_modes`, `interpolation_degree`(아래·위·옆이 모두 열린 단면은 `ground_modes` 없음) |

`current_method`를 생략하면 `surface`·`surface-boundaries` 도체는 `panel`을 씁니다.
`perfect` 도체에는 기본값이 없으므로 방법을 적어야 합니다. P1 부피 메시 표면 전류를
쓰려면 `current_method: "volume-p1"`을 적습니다. 이때는 `panel`을 둘 수 없습니다.

`panel`을 생략하면 단면에 따라 다음 기본값을 씁니다.

| 단면 | 기본 `panel` |
|---|---|
| 아래 접지, 열린 위·옆 | `panels_per_edge` 64, `ground_modes` 512, `interpolation_degree` 14 |
| 위아래 접지, 열린 옆 | `panels_per_edge` 64, `ground_modes` 512, `interpolation_degree` 14 |
| 아래·위·옆 모두 열림 | `panels_per_edge` 64, `interpolation_degree` 12 |

기본값은 상수 `sipi.default_line.DEFAULT_PANEL_CONTROLS` 한 곳에 있고, 저장 문서에는 쓴
값이 기록됩니다. 전형 입력과 템플릿 기본 상자로 템플릿 72개 모두를 측정해 정했습니다.
변 하나당 패널을 64에서 128로 늘리면 C0는 최대 1.5e-6, 전류 Gram 행렬은 각 최대 원소의
최대 5.2e-3만큼 바뀌었고, panel 시간 중앙값은 P1 기본 메시 시간의 1.05배였습니다. 사다리꼴
(식각) 도체가 가장 느리게 수렴하며, 64 패널에서 남은 Gram 오차는 약 1–2%로 추정됩니다.
정밀 계산에는 `panels_per_edge: 128`을 명시하세요. 시간은 약 2배, Gram 변화는 약 2.5배
줄어듭니다. 위아래 접지 사이의 적층 coplanar stripline은 보간 상자 37개가 필요해 패널 수와
상관없이 약 150–200 s 걸렸습니다.

계산은 같은 내용의 [방법 명시 선로](method_line.md)가 하는 계산입니다.
`method_document()`는 그 `sipi.method-transmission-line/1` 문서를, `equivalent_document()`는
실제로 실행되는 panel·두 접지 panel·open panel·transmission-line/7 문서를 돌려줍니다.
새 수치 경로는 없습니다. R, L, G, C, S는 그 문서와 비트 단위로 같고, 결과는 이 입력을
`input_json`으로 유지합니다. `sipi run`과 `execute_saved`는 동등 결과에
`current_method = {method, equivalent_schema}`를 더합니다.

```python
from sipi.default_line import DefaultPanelTransmissionLineDocument

saved = DefaultPanelTransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    conductor=dict(kind='surface', conductivity=58e6, ground_thickness=35e-6,
                   relative_permeability=1., roughness=dict(kind='smooth')))
saved.to_dict()['current_method']   # 'panel'. 기본 panel 제어값도 저장됨
result = saved.analyze()
```

## 거절하는 것

거절해도 P1 방법으로 바꾸지 않습니다. panel 거절 메시지는 `current_method: "volume-p1"`로
P1을 명시해 고를 수 있다고 알려 줍니다.

- `surface-faces` 도체(면별 금속)에는 panel 기본값이 없고 panel 방법에서는 거절됩니다.
  `volume-p1`을 적거나 면별 panel 선로 문서를 쓰세요.
- 위 세 가지 밖의 경계 조합(예: 접지된 옆면).
- 정규화에서는 panel 문서가 필드 계산 없이 하는 검사도 거칩니다. 단면에 맞는 도체 종류(두
  접지는 `surface`나 `surface-boundaries` 필요), 양의 도체 두께, panel 제어값, 도체·패널 수
  한도가 그것입니다.
- 공유 panel 커널의 나머지 한계는 `analyze()`에서 검사합니다. 볼록 다각형, 상자의
  폭/높이 범위(한 접지 [0.25, 4], 두 접지 [0.25, 64], 접지 없음 [0.25, 16]), 벽 거리,
  적분 수렴이 그것입니다.

전송선을 담는 문서(회로, 스터디, panel 선로, 방법 명시 선로 등)는 transmission-line/1–/7을
받고 /8·/9는 거절합니다. P1으로 조용히 계산하지 않습니다. 새 컨테이너 버전은 /8·/9를 명시적으로
받습니다. [`sipi.circuit/2`](circuit_document.md#버전-2-기본-panel-선로)는 내부
transmission-line/8·/9를 그대로 실행하며 결과는 선로 단독 결과와 비트 단위로 같습니다.
[`sipi.network-assembly/2`](network_assembly.md#버전-2-기본-panel-선로)와
[`sipi.network-transforms/3`](network_document.md#버전-3-기본-panel-선로),
[`sipi.network-band/2`](band.md#버전-2-기본-panel-선로),
[`sipi.line-length-design/3`](extracted_length.md#버전-3-기본-panel-선로)도 같습니다.

## 버전 9: 이름으로 고르는 복원 방법

`sipi.transmission-line/9`(같은 클래스, `schema='sipi.transmission-line/9'`)는 버전 8의
필드에 선택 필드 `recovery`를 더합니다. `current_method: "volume-p1-recovered"`도 받지만
이름을 적을 때만입니다. 기본값은 계속 `panel`이고, panel·`volume-p1` 문서는 버전 8과
똑같이 실행됩니다. `recovery`(`support_fraction`, 생략하면 `DEFAULT_RECOVERY_CONTROLS`의
0.4)는 저장 문서에 적힙니다. 다른 방법에서는 `recovery`를, 복원 방법에서는 `panel`을
거절합니다. 버전 8은 두 값만 받고 `recovery`를 거절합니다. `method_document()`는
`sipi.method-transmission-line/2` 문서를 돌려주며, 이것이
[복원 선로](method_line.md#버전-2-복원-전류)를 실행합니다. 복원 방법에서 `perfect`·
`surface-faces` 도체는 거절합니다.

```python
saved = DefaultPanelTransmissionLineDocument(geometry, [1e9, 5e9], materials={}, length=.02,
    conductor=conductor, current_method='volume-p1-recovered',
    schema='sipi.transmission-line/9')
saved.to_dict()['recovery']   # {'support_fraction': 0.4}
```
