# 두 기판층 위의 평면 코팅 표면선로

[English](../../../../../packages/sipi/layered_coated_microstrip.md)

하단 접지면과 두 독립 기판층 위의 도체를 계산 폭 전체를 덮는 평면 유전체
코팅 안에 놓는 세 API입니다.

- `layered_coated_microstrip`: 단일 신호.
- `coupled_layered_coated_microstrip`: 같은 신호 두 개, 왼쪽이 양극.
- `asymmetric_coupled_layered_coated_microstrip`: 독립 바닥 폭·두께·중앙 정렬
  윗면 폭을 갖는 쌍. 왼쪽이 양극, 오른쪽이 음극입니다.

기판 두 높이는 구리를 제외합니다. 도체 바닥은 두 높이의 합에 놓입니다.
`coating_height`는 그 표면부터 시작하여 구리를 포함하며 모든 도체보다
두꺼워야 합니다. `air_height`는 **코팅 위**부터 시작합니다. 양의 공기 높이를
기하로 허용하지만 작은 공기 여유는 별도의 외곽 수렴 확인이 필요합니다.
코팅은 신호 사이를 채우는 평면층이며 경사진 구리에 수직인 일정 두께의
필름을 뜻하지 않습니다. 하단면만 접지하고 윗면·옆면은 전기적으로 절연합니다.

```python
from sipi import layered_coated_microstrip, CrossSectionDocument
section = layered_coated_microstrip(
    width=.5e-3, thickness=35e-6, top_width=.4e-3,
    lower_height=.3e-3, upper_height=.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    coating_height=80e-6, coating_eps_r=3.3, coating_tan_delta=.02,
    air_height=.01, box_width=.02)
text = CrossSectionDocument(section).dumps()
```

쌍의 `gap`은 구리 바닥 모서리 사이이며 전체 바닥 폭의 중앙을 원점에 둡니다.
단일 `z0`, 대칭쌍의 even/odd 진단과 비대칭쌍의 Icommon=0 조건에서 구하는
실수 `z_diff_forward`는 기존 정의를 유지합니다. 비대칭쌍에 독립 대칭 모드를
가정하지 않습니다. Python 직접 호출과 기하 JSON을 지원합니다. 이름 있는
편집 입력·저장 공차·폭 역산 등록·전용 폼은 별도 연결 단계입니다.

대표 쌍 간격은 0.3mm입니다. 비대칭 예제의 폭은 0.4/0.7mm, 두께는
25/45µm, 윗면 폭은 0.32/0.55mm입니다. 높이로 복소 재료를 독립 배정한
scikit-fem 12.0.2 P1 에너지 행렬과 진공 행렬을 정규화 오차 1e-10으로
검사합니다. edge/far/grade를 5µm/0.25mm/0.2에서
2.5µm/0.125mm/0.1로 세분할 때 C와 해당 임피던스 변화는 1% 이하,
세분 메시에서 상자 폭·공기 높이를 각각 두 배로 늘린 변화는 0.5% 이하입니다.
같은 기판 재료 및 공기와 같은 코팅의 극한을 기존 API와 각각 0.5%로 대조하며
공기 극한에서는 전체 외곽 높이를 맞춥니다. 진공 항등식·양의 에너지·상반성·
JSON 왕복·잘못된 층 거부도 검사합니다. 이 근거는 기록된 대표 단면에 대한
것이며 임의 기하나 실측 PCB의 정확도 보증이 아닙니다. 기존 API와 수치
수락 기준은 바꾸지 않습니다.
