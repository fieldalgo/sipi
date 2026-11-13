# 3개 유전체 안의 비대칭 broadside 선로

`asymmetric_layered_broadside_stripline`은 접지 평면 사이에 사각 도체 두 개를
만듭니다. 아래 도체 이름은 `positive`, 위 도체는 `negative`이며 선폭과 양수
동박 두께를 각각 지정합니다. 길이 단위는 m, 상대유전율·손실탄젠트는 무차원입니다.

`lower_height`·`upper_height`는 동박을 제외한 도체와 접지 평면 사이 거리이며,
`gap`은 마주 보는 동박 면 사이 거리입니다. 아래 재료층은 아래 동박의 윗면에서
끝나고, gap 재료가 사이를 채우며, 위 재료층은 위 동박의 아랫면에서 시작합니다.
전체 평면 간격은 `lower_height + lower_thickness + gap + upper_thickness + upper_height`
입니다. 세 재료의 유전율과 손실탄젠트를 독립적으로 지정할 수 있습니다.

부호 있는 가로 `offset`은 도체 중심을 `-offset/2`·`+offset/2`에 놓습니다.
도체 변 사이 간격이나 고정 pitch 조건이 아닙니다. 옆 경계는 열림(정전계의
법선 플럭스 0)이며 외곽 폭 수렴을 별도로 확인해야 합니다. 기본 폭은
`max(12*plane_spacing, 4*(max(widths) + abs(offset)))`입니다.
동박 두께 0, 양수가 아닌 간격, 잘못된 재료, 외곽에 닿는 도체를 거부합니다.
taper는 추정하지 않습니다.

```python
from sipi import asymmetric_layered_broadside_stripline, CrossSectionDocument

section = asymmetric_layered_broadside_stripline(
    lower_width=.4e-3, upper_width=.7e-3,
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
assert [trace.name for trace in section.traces] == ['positive', 'negative']
```

기하 문서는 실제 도체·재료층·메시 설정을 보존합니다. 같은 factory 이름을
편집용 템플릿, 공차 분석과 선폭 목표 입력에서 사용합니다. 기존 이름 있는
입력의 계약은 유지하며 이번 등록에 UI 폼 추가는 포함하지 않습니다.

`section.analyze(...)`는 전체 정전용량 행렬과 진공 전계로 구한 인덕턴스 행렬을
반환합니다. 도체나 주변 재료가 다르면 일반적으로 차동·공통 좌표가 결합되므로
독립 even/odd 모드라고 해석하면 안 됩니다. `z_diff_forward`는 기존 실수 전진
차동 전류 구동량이며 일반 복소 유손실 모드 임피던스가 아닙니다.

위 검증 사례는 독립 높이별 재료 마스크와 scikit-fem 조립으로 복소·진공 P1
에너지 행렬을 비교합니다. 메시 1%와 외곽 폭 두 배 0.5%를 별도로 검사하고,
진공·균일 재료 불변식, 상반성·양의 에너지, 상하·좌우 반사(재메시 후 0.5%),
동일 선폭·두께의 기존 factory로 기하가 정확히 환원되는지를 확인합니다.
임의 치수·도체 손실·재료 데이터·실측 정확도를 보증하는 검사는 아닙니다.

## 저장 공차와 선폭 목표

저장 공차·목표는 `quantity='z_diff_forward'`를 명시합니다. 특정 입력이 우연히
대칭이어도 대칭 모드 목적량은 거부합니다. 아래 선폭이나 위 동박 두께를 표본화할
때 나머지 명시 치수는 유지됩니다. 동박 두께가 바뀌면 바깥 clearance는 고정이므로
전체 평면 간격이 바뀝니다. 가로 fixed pitch와 두 재료층 높이 합을 고정하는
조건은 이 수직 3재료 단면에 적용하지 않습니다.

```python
from sipi import ImpedanceDesignDocument
from sipi.template_document import TemplateSectionDocument

parameters = dict(
    lower_width=.4e-3, upper_width=.7e-3,
    lower_thickness=25e-6, upper_thickness=45e-6,
    lower_height=.35e-3, upper_height=.55e-3, gap=.25e-3,
    lower_eps_r=3., gap_eps_r=4., upper_eps_r=5., offset=.15e-3,
    lower_tan_delta=.01, gap_tan_delta=.02, upper_tan_delta=.03,
    box_width=.012,
)
mesh = dict(edge_size=5e-6, far_size=.15e-3, grade=.15)
name = 'asymmetric_layered_broadside_stripline'
editable = TemplateSectionDocument(name, parameters, mesh=mesh)
goal = ImpedanceDesignDocument(
    name, parameters, variable='lower_width', bounds=[.2e-3, .8e-3],
    target=50., quantity='z_diff_forward', mesh=mesh,
    tolerance=.5, search_tolerance=.05,
)
assert ImpedanceDesignDocument.loads(goal.dumps()).dumps() == goal.dumps()
```

`goal.solve()`는 검색 후 별도 절반 메시로 검증합니다. 요청 메시와 세분 메시의
목표 잔차가 모두 지정한 허용치를 만족해야 합니다. 검증한 50Ω 사례는 양쪽
잔차가 0.5Ω 이내이고 직접 API와 이력이 정확히 일치합니다. 절대적인 물리 임피던스
오차를 보장하는 것은 아닙니다. 저장 검사는 PCG64 표본, 상관 선폭·두께 행,
gap 재료 변화, 공통 실행과 비물리적인 정규분포 표본의 실패 행 보존을 포함합니다.
