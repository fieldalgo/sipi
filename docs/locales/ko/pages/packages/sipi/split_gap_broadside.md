# 선로 사이에 유전체 계면이 있는 broadside 쌍

`split_gap_broadside_stripline`은 사다리꼴 도체 두 개와 평면 유전체 네 층을
정의합니다. 모든 길이는 m입니다. `gap`은 마주 보는 금속면 사이의 수직 거리,
`gap_lower_height`는 아래 금속 윗면부터 내부 유전체 계면까지의 거리이며
`0 < gap_lower_height < gap`이어야 합니다. 위쪽 gap 두께는
`gap - gap_lower_height`입니다. 계면을 옮겨도 금속이나 접지 평면은 움직이지 않습니다.

재료 이름은 아래부터 `lower`, `gap_lower`, `gap_upper`, `upper`이고 각각 독립
유전율·손실탄젠트를 가집니다. 외부 평면 간격은 동박을 제외하고, 해당 층 두께는
동박을 포함합니다. 인접 재료 값이 같아도 층 구분을 유지합니다. 네 선폭과 두
동박 두께는 양수여야 합니다. 아래·위 선폭은 두 도체 모두 기하학적 -y·+y면을
뜻합니다. 아래 `positive`와 위 `negative` 신호 중심은 각각 `-offset/2`,
`+offset/2`입니다. 위아래 평면은 접지, 옆 벽은 법선 전속 0 경계이므로 별도
외곽 폭 수렴이 필요합니다. 교환 대칭이나 독립 even/odd 모드는 가정하지 않습니다.

```python
from sipi import split_gap_broadside_stripline, CrossSectionDocument

section = split_gap_broadside_stripline(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3,
    gap=.25e-3, gap_lower_height=.1e-3,
    lower_eps_r=3., gap_lower_eps_r=3.2,
    gap_upper_eps_r=4.6, upper_eps_r=5.,
    lower_tan_delta=.01, gap_lower_tan_delta=.015,
    gap_upper_tan_delta=.025, upper_tan_delta=.03,
    offset=.15e-3, box_width=.012,
)
document = CrossSectionDocument(
    section, mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2),
)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert section.layers[1].thickness == .1e-3
```

이 사례에는 독립적인 네 높이 영역의 재료 마스크와 scikit-fem 복소·진공 조립
대조(정규화 차이 `1e-10` 이하), half-mesh 1%, 외곽 폭 두 배 0.5% 조건을 적용합니다.
균일 재료·진공 불변식, 양의 상반 행렬과 좌우·상하 반사도 별도로 확인합니다.
상하 반사에서는 gap 재료를 맞바꾸고 계면 거리를 `gap - gap_lower_height`로
바꿉니다. gap 재료가 같은 극한은 별도 세분 메시의 기존 3층 단면과 0.5% 이내에서
일치해야 합니다. 이 조건은 절대 물리 오차, 제조 데이터 보정이나 임의의 얇은
층에 대한 정확도를 보장하지 않습니다.

[English](../../../../../packages/sipi/split_gap_broadside.md)
