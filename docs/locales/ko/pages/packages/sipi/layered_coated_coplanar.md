# 두 기판층 위의 평면 코팅 coplanar 선로

[English](../../../../../packages/sipi/layered_coated_coplanar.md)

두 독립 기판 재료·폭 전체의 평면 코팅·유한한 직사각형 옆 접지선을 조합합니다.

| 신호 | 하단 접지면 있음 | 하단 접지면 없음 |
|---|---|---|
| 단일 | `layered_coated_grounded_coplanar` | `layered_coated_unbacked_coplanar` |
| 같은 쌍 | `coupled_layered_coated_grounded_coplanar` | `coupled_layered_coated_unbacked_coplanar` |
| 비대칭쌍 | `asymmetric_coupled_layered_coated_grounded_coplanar` | `asymmetric_coupled_layered_coated_unbacked_coplanar` |

기판 높이는 구리를 제외합니다. 코팅은 기판 윗면에서 시작하여 간격과 모든
구리를 포함하므로 `coating_height`가 모든 신호·접지선 두께보다 커야 합니다.
`air_height`는 코팅 위부터 시작합니다. 코팅은 평면층이며 경사진 구리 표면에
수직인 일정 두께 필름이 아닙니다.

단일선의 `gap`은 신호 바닥 모서리와 옆 접지선 사이입니다. 쌍의 `gap`은
신호 바닥 모서리 사이, `ground_gap`은 바깥 신호와 접지선 사이입니다.
접지선 폭은 유한한 `ground_width`입니다. 대칭 구조는 신호·접지선 두께를
공유합니다. 비대칭 구조는 신호 바닥 폭·두께·중앙 정렬 윗면 폭을 각각
지정하고 `ground_thickness`를 따로 받습니다. 왼쪽이 양극, 오른쪽이 음극이며
중앙 접지선이나 옆 접지선 사이의 3D 연결을 추정하지 않습니다.

grounded 구조는 유한 계산 경계의 하단을 접지면으로 두고 윗면·옆면을
개방합니다. unbacked 구조는 유한 기판 아래에 공기를 두고 네 외곽을 모두
개방하며 두 유한 옆 접지선만 기준 전위를 정합니다. `lower_air_height`만큼
두 기판층·코팅·모든 구리를 함께 이동합니다. 기본값은 코팅과 구리를 제외한
두 기판 높이 합의 열 배입니다. 위·아래 공기는 각각 외곽 수렴을 확인해야 합니다.

```python
from sipi import layered_coated_unbacked_coplanar, CrossSectionDocument
section = layered_coated_unbacked_coplanar(
    width=.5e-3, gap=.2e-3, ground_width=1e-3,
    thickness=35e-6, top_width=.4e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    coating_height=80e-6, coating_eps_r=3.3, coating_tan_delta=.02,
    lower_air_height=.01, air_height=.01, box_width=.02)
text = CrossSectionDocument(section).dumps()
```

Python 직접 호출과 기하 JSON을 지원합니다. 이름 있는 공차·폭 역산·전용 폼은
별도 연결 단계입니다. 단일 `z0`, 대칭쌍 even/odd 진단, 비대칭쌍의
Icommon=0 조건에서 구하는 실수 `z_diff_forward`는 기존 정의를 유지합니다.
비대칭 신호에 독립 대칭 모드를 가정하지 않습니다.

대표 쌍은 신호 간격 0.3mm, 바깥 접지 간격 0.2mm입니다. 비대칭 신호는
폭 0.4/0.7mm, 두께 25/45µm, 윗면 폭 0.32/0.55mm, 접지선 두께 35µm입니다.
높이로 복소·진공 재료를 독립 배정한 scikit-fem 12.0.2 P1 에너지를
정규화 오차 1e-10으로 대조합니다. edge/far/grade를
5µm/0.25mm/0.2에서 2.5µm/0.125mm/0.1로 세분한 C/임피던스 변화는 1%,
상자 폭·코팅 위 공기·unbacked 아래 공기를 각각 두 배로 바꾼 변화는 0.5%
기준입니다. 같은 기판 재료 및 공기와 같은 필름의 극한을 대응 기존 API와
각각 0.5%로 대조하며 공기 극한의 전체 윗면 높이를 맞춥니다. 진공 항등식·
상반성·양의 에너지·층 이동·접지 간격·JSON 왕복·잘못된 층 거부도 검사합니다.
이 대표 단면의 기준은 임의 배치나 실측 PCB의 검증을 대신하지 않습니다.
