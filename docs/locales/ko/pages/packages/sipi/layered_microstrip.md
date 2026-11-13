# 두 기판층 위의 표면 선로

[English](../../../../../packages/sipi/layered_microstrip.md)

`layered_microstrip`과 `coupled_layered_microstrip`은 서로 다른 두 유전체
기판층 위에 단일 신호 또는 같은 폭의 쌍을 놓습니다. 두 층 모두 도체 아래에
있습니다. 하부 접지는 높이 0, 도체 아랫면은 `lower_height + upper_height`입니다.
두 높이에는 도체가 포함되지 않으며, 유전체 경계에 도체를 놓는 stripline의
upper_height 계약과 다릅니다. 상부·측면은 주변 공기를 유한 영역에서 자르는
open 경계입니다.

```python
from sipi import layered_microstrip, CrossSectionDocument

section = layered_microstrip(
    width=0.5e-3, thickness=35e-6,
    lower_height=0.3e-3, upper_height=0.7e-3,
    lower_eps_r=3.0, upper_eps_r=5.0,
    lower_tan_delta=0.01, upper_tan_delta=0.03,
    air_height=10e-3, box_width=20e-3,
)
document = CrossSectionDocument(section, mesh={
    'edge_size': 2.5e-6, 'far_size': 0.125e-3, 'grade': 0.1,
})
line = document.analyze()
print(line.z0)
```

길이는 모두 m입니다. 각 기판 높이는 양수, 상대 유전율은 1 이상,
손실탄젠트는 0 이상입니다. 도체 두께는 0도 가능하지만 서로 다른 윗폭을
쓰려면 유한 두께가 필요합니다. 사다리꼴의 중심을 유지하고 아랫폭을 명시합니다.
쌍은 도체 아랫면 가장자리 사이의 양수 `gap`도 필요하며 왼쪽이 `positive`,
오른쪽이 `negative`입니다. 같은 도체와 좌우 대칭을 유지하여 기존 even/odd
진단을 사용할 수 있습니다.

`air_height`는 기판 위 공기층의 전체 높이이며 도체를 포함합니다. 기본값은
총 기판 높이의 10배에 도체 두께를 더한 값입니다. 기본 상자 폭은 총 기판
높이의 20배 이상이고 기존 단일/쌍의 도체 폭 규칙도 적용합니다. 도체를 자르는
명시 영역은 거부합니다. 메시를 세분하고 공기 높이와 상자 폭을 각각 늘려
경계 영향을 확인해야 합니다.

기존 정전계·복소 유전체 추출을 사용하며 주파수 분산·도체 저항·거칠기 모델을
추정하지 않습니다. 반환값은 일반 `CrossSection`이므로 `CrossSectionDocument`로
저장하고, 폭을 바꾸는 함수를 `seek_impedance`에 전달할 수 있습니다. 목표
역산의 별도 세분 검사는 유지합니다. 편집 템플릿 등록·저장 공차/목표·전용
workbench 폼은 후속 연결 단계이며 기존 등록 입력은 이번 API에서 바꾸지 않습니다.

검증은 scikit-fem 12.0.2의 독립 재료 배치와 복소·진공 에너지 조립을 사용합니다.
`tests/sipi/test_layered_microstrip.py`의 명시 단일/쌍 조건에서 C/C_loss/C0의
최대 정규화 차이는 `1e-10` 이하입니다. 진공 불변식과 같은 재료의 기판 한계도
별도로 검사합니다. 사전 등록한 메시 변화 기준은 1%, 상자 폭과 공기 높이를
각각 2배 늘리는 기준은 0.5%입니다. 관측 최대값은 각각 약 0.3373%, 0.3105%,
0.0147%입니다. 이는 선택한 수치 검증의 범위이며 실측 정확도나 모든 기하의
보장이 아닙니다. 균일 기판과의 차이는 0.5% 이내이며 독립 조립·외곽 검사를
대체하지 않습니다.
