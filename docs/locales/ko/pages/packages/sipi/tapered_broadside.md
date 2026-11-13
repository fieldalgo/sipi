# 사다리꼴 broadside 도체

`tapered_layered_broadside_stripline`은 명시적인 3유전체 broadside 단면에서
각 도체의 아래·위 면 선폭을 독립적으로 지정합니다. 길이 단위는 m입니다.
`lower_width`와 `upper_width`는 각 도체의 기하학적 아랫면(작은 y) 선폭,
`lower_top_width`와 `upper_top_width`는 윗면(큰 y) 선폭입니다.
따라서 수직 gap을 사이에 두고 마주 보는 면의 선폭은 `lower_top_width`와
`upper_width`입니다. 측면은 직선이며 안쪽·바깥쪽으로 기울어진 식각면을
모두 표현합니다.

동박 두께와 네 선폭은 모두 양수여야 합니다. `lower_height`와
`upper_height`는 동박을 제외한 접지면까지의 간격이고, `gap`은 금속 사이의
수직 간격입니다. 아래 재료는 아래 동박 윗면까지, gap 재료는 그 사이,
위 재료는 위 동박 아랫면부터입니다. 아래 도체는 `positive`, 위 도체는
`negative`이며 중심은 부호 있는 `offset`에 따라 `-offset/2`, `+offset/2`에
놓입니다. 교환 대칭은 추정하지 않습니다.

위아래 평면은 접지입니다. 측면은 법선 방향 전속이 0인 경계이므로 별도의
외곽 폭 검사가 필요합니다. 기본 폭은
`max(12*plane_spacing, 4*(네 선폭 중 최댓값 + abs(offset)))`입니다.
외곽에 닿는 동박과 잘못된 재료 입력은 거부합니다. 두 도체 각각의 위아래
선폭이 같으면 기존 사각형 `asymmetric_layered_broadside_stripline`의
기하 문서와 정확히 일치합니다.

```python
from sipi import tapered_layered_broadside_stripline, CrossSectionDocument

section = tapered_layered_broadside_stripline(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5.,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    offset=.15e-3, box_width=.012,
)
document = CrossSectionDocument(
    section, mesh=dict(edge_size=5e-6, far_size=.15e-3, grade=.15),
)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
assert section.traces[1].top_width == .55e-3
```

`section.analyze(...)`는 전체 정전용량·외부 인덕턴스 행렬과 기존 실수
전진 차동 입력량 `z_diff_forward`를 반환합니다. 비대칭 재료·도체는 일반적으로
차동·공통 좌표를 결합하므로 독립 even/odd 모드를 추정하지 않습니다.
새 도체 손실 모델이나 UI 폼을 추가하는 API는 아닙니다.

명시한 사례의 검증은 독립적인 높이별 재료 마스크와 scikit-fem 복소·진공
조립(정규화 차이 `1e-10` 이하), 별도 half-mesh(1%)·외곽 폭 두 배(0.5%) 기준,
진공·균일 재료 불변식, 양정·상반 행렬을 포함합니다. 수직 반사는 도체 순서뿐
아니라 각 도체의 위아래 선폭도 뒤집습니다. 수평·수직 반사 재메시 결과에는
각각 0.5% 기준을 적용합니다. 이는 한정된 수치 검증이며 절대 물리 오차나
임의 식각 각도의 보증이 아닙니다.

## 저장 공차와 식각면 선폭 목표

동일한 이름을 편집 템플릿·버전 있는 공차·설계 목표에 등록했습니다.
`quantity='z_diff_forward'`를 사용해야 하며 대칭 모드 기반 목표는 거부합니다.
`lower_top_width` 표본을 만들 때 아래 도체의 아랫면 선폭, 위 도체와 수직 간격은
유지합니다. 위아래 선폭의 상관 표본도 식각 각도로 자동 변환하지 않고 지원합니다.
잘못된 정규분포 표본은 재추출하지 않고 실패행으로 남깁니다. 가로 고정 pitch와
기존 2층 높이 합 제약은 이 수직 적층에 적용하지 않습니다.

```python
from sipi import ImpedanceDesignDocument
from sipi.template_document import TemplateSectionDocument

parameters = dict(
    lower_width=.4e-3, lower_top_width=.32e-3,
    upper_width=.7e-3, upper_top_width=.55e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5., offset=.15e-3,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    box_width=.012,
)
mesh = dict(edge_size=5e-6, far_size=.15e-3, grade=.15)
name = 'tapered_layered_broadside_stripline'
editable = TemplateSectionDocument(name, parameters, mesh=mesh)
goal = ImpedanceDesignDocument(
    name, parameters, variable='lower_top_width', bounds=[.2e-3, .6e-3],
    target=50., quantity='z_diff_forward', mesh=mesh,
    tolerance=.5, search_tolerance=.05,
)
assert ImpedanceDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
```

`goal.solve()`는 해당 선폭 하나를 검색하고 별도 half-mesh 검사를 수행합니다.
한정된 50Ω 사례에서 요청·세분 잔차가 각각 0.5Ω 안에 들고 직접 API의 평가
이력이 일치하는지 확인합니다. 이는 수치 수락 조건이며 절대 물리 오차 상한은
아닙니다. PCG64 표본·선폭 상관·재료 공차·공통 실행도 검사합니다.

[English](../../../../../packages/sipi/tapered_broadside.md)
