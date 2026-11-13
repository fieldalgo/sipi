# 두 기판층 위의 법선 두께 코팅

[English](../../../../../packages/sipi/layered_conformal_microstrip.md) | **한국어**

`layered_conformal_coated_microstrip`, `coupled_layered_conformal_coated_microstrip`,
`asymmetric_coupled_layered_conformal_coated_microstrip`은 직선 측면을 감싸는
기존 코팅 아래의 기판을 두 재료층으로 나눕니다. 두 기판 두께는 구리를 제외합니다.
하단은 접지면, 상단·옆면은 열린 경계입니다. 단일·대칭쌍·비대칭쌍의 구리 형상은
기존 정의를 유지하며, 바닥 변 사이 간격과 비대칭 폭·두께·위쪽 폭을 명시합니다.

`coating_thickness`는 기판·도체 윗면·경사 측면에 수직인 두께입니다. 코팅은
모서리가 직선으로 만나는 하나의 다각형 영역이며 서로 닿는 외피는 합칩니다.
공기 높이는 가장 높은 코팅 윗면부터입니다. 기판을 나눌 때 이 영역을 보존하며
평평한 코팅층으로 대체하지 않습니다. 돌출된 윗면·잘린 코팅·해상할 수 없는
치수·갇힌 공기 구멍은 거부합니다. 둥근 모서리·메니스커스·실측 증착 모델은 아닙니다.

```python
from sipi import layered_conformal_coated_microstrip, CrossSectionDocument
section = layered_conformal_coated_microstrip(
    width=0.5e-3, thickness=35e-6, top_width=0.4e-3,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=0.02,
    air_height=10e-3, box_width=20e-3)
text = CrossSectionDocument(section).dumps()
```

Python 직접 호출·기하 JSON·이름 기반 단면·공차·폭 목표가 같은 단면 계약을
사용합니다. 전용 입력 화면 연결은 별도 단계입니다. 단일선 `z0`, 대칭쌍 even/odd 진단, 비대칭쌍
`z_diff_forward`의 의미를 유지하며 비대칭 신호의 독립 대칭 모드를 가정하지 않습니다.

대표 전계 검사는 기판 0.3/0.7 mm·유전율 3/5·손실탄젠트 0.01/0.03,
코팅 20 µm·유전율 3.3·손실탄젠트 0.02를 사용합니다. 단일·대칭 신호는
바닥 폭 0.5 mm·위쪽 폭 0.4 mm·두께 35 µm입니다. 비대칭쌍은 각각
바닥 폭 0.4/0.7 mm·위쪽 폭 0.32/0.55 mm·두께 25/45 µm이며 쌍 간격은 0.3 mm입니다.

독립 부호 거리 재료 마스크와 scikit-fem P1 복소·진공 조립의 정규화 오차는
1e-10 이하여야 합니다. edge 5 µm·far 0.25 mm·grade 0.2를 절반으로
세분하여 C·해당 임피던스 변화를 1% 이하로 확인합니다. 세분 메시에서 상자 폭과
상단 공기를 각각 두 배로 바꿀 때 변화는 0.5% 이하입니다. 균일 기판·유전율 1의
코팅·구리 두께 0의 평면 코팅 극한도 각각 0.5% 이내여야 합니다. 법선 거리·
진공 항등식·상반성·양의 에너지·JSON 왕복도 검사합니다. 이 선택 기하 검증은
임의 보드나 실측 정확도를 인증하지 않습니다.


## 저장 공차와 폭 목표

단일·대칭·비대칭 목표는 각각 `z0`·`z_diff`·`z_diff_forward`이며 대칭쌍은
명시적인 `z_diff_forward`도 허용합니다. 고정 피치 표본은 대칭 예제의 신호
중심 간격 0.8 mm, 비대칭 예제의 0.85 mm를 보존합니다. 다각형 코팅은 원래
법선 두께 20 µm로 다시 구성합니다. 음수 코팅 두께 표본은 메시를 만들지 않고
실패 행으로 남깁니다. 코팅 유전율 스윕은 기하를 보존하며 공통 저장 실행으로
재현합니다. 결정적 PCG64 표본은 독립적으로 확인합니다.

대표 폭 목표는 90/105/105 Ω이며 폭 0.4–0.7 mm 또는 비대칭 왼쪽 폭
0.32–0.8 mm를 사용합니다. 탐색 기준 0.05 Ω 이후 edge·far·grade를 각각
절반으로 하는 별도 세분 검사를 거칩니다. 요청·세분 잔차 모두 0.5 Ω 이내여야
하며 직접·저장 이력과 세분 결과는 정확히 일치해야 합니다. 선택 기하 검사는
명목 기하의 외곽 수렴과 구분하며 검증된 기하 범위를 넓히지 않습니다.
