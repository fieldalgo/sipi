# 매립 coplanar stripline

[English](../../../../../packages/sipi/coplanar_stripline.md)

`coplanar_stripline`은 균일 유전체의 두 접지면 사이에 신호 하나와 유한 폭 측면
접지 두 개를 둡니다. `coupled_coplanar_stripline`은 같은 폭의 수평 신호 쌍을
그 측면 접지 사이에 둡니다. 길이 방향으로 균일한 준정적 단면입니다. 모든 기준
도체는 같은 PEC 전위이며, 접지 전류를 그룹으로 나누어도 포트가 늘지는 않습니다.

```python
from sipi import coupled_coplanar_stripline, CrossSectionDocument

parameters = dict(width=.3e-3, gap=.3e-3, ground_gap=.3e-3,
    ground_width=.8e-3, plane_spacing=1e-3, trace_height=.4e-3,
    eps_r=4., thickness=35e-6, tan_delta=.02, box_width=6e-3)
mesh = dict(edge_size=5e-6, far_size=.125e-3, grade=.15)
section = coupled_coplanar_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
assert CrossSectionDocument.loads(document.dumps()).dumps() == document.dumps()
line = document.analyze()
assert line.even_odd()["z_diff"] > 0
```

길이 단위는 m입니다.

| 매개변수 | 의미 |
|---|---|
| `plane_spacing` | 금속 두께를 포함한 접지면 사이 전체 높이 B |
| `trace_height` | 모든 도체의 명시적 **아래면** 높이 h. 0 < h, h + thickness < B |
| `width` | 신호 아래면 폭. 쌍의 두 신호에 동일하게 적용 |
| `top_width` | 선택적 신호 윗면 폭. 측면 접지는 직사각형 유지 |
| `gap` | 단일: 신호↔접지 아래면 모서리 간격. 쌍: 두 신호 아래면 모서리 간격 |
| `ground_gap` | 쌍에만 사용. 바깥쪽 신호↔측면 접지 아래면 모서리 간격 |
| `ground_width` | 측면 접지 각각의 실제 유한 폭 |
| `thickness` | 측면 접지를 포함한 모든 도체의 공통 두께. 0 허용 |
| `box_width` | 절연 측벽을 둔 계산 영역 폭. 실제 접지 폭과 구분 |

신호 이름은 `signal`, 또는 왼쪽 `positive`·오른쪽 `negative`입니다. 접지는
`ground_left`·`ground_right`, 유전체는 `dielectric`입니다. 접지면은 y=0과 B에
있고 신호 쌍 사이에는 접지를 넣지 않습니다. 양의 치수·음이 아닌 손실, 접지면과의
분리, 도체 비겹침과 상자 안의 포함을 검사합니다. 신호 윗면을 넓히면 아래면 간격이
양수여도 겹침 때문에 거부될 수 있습니다.

접지 중심 거리 d는 단일에서 `(width+ground_width)/2+gap`, 쌍에서
`width+gap/2+ground_gap+ground_width/2`입니다. 상자 폭 생략 시 단일은
`max(12*B, 4*width, 2*d+ground_width+4*B)`, 쌍은
`max(12*B, 4*(2*width+gap), 2*d+ground_width+4*B)`를 씁니다. 기본값은 수렴
보증이 아닙니다. 외곽 수렴에서는 **실제 접지 폭과 간격을 고정**하고 상자만
넓혀야 합니다. 접지 폭을 바꾸면 물리 형상 자체가 달라집니다.

두께 0은 정전기와 얇은 CPW 해석 극한에 사용할 수 있습니다. 기존 표면 도체 손실은
양의 두께 및 skin-depth·전류 보존 검사를 그대로 요구합니다. 유한 두께 신호는
[면별 표면 법칙](face_conductor.md)과 [기준 도체 표면 법칙](reference_surfaces.md)을
재사용할 수 있습니다.

## JSON·공차·역산

기존 기하 JSON과 공차·역산 스키마에서 두 이름을 받습니다. 이전 엔진은 모르는
템플릿 이름을 거부하므로 정확한 엔진 커밋을 함께 기록하세요. 단일은 `z0`, 쌍은
`z_diff` 또는 `z_diff_forward`를 사용합니다. 이 값은 도체 R·유전체 G를 제외한
실수 준정적 임피던스입니다. 주파수별 손실은 기존 선로·회로 API에서 계산합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("coupled_coplanar_stripline", parameters,
    quantity="z_diff", mesh=mesh, fixed_pitch_m=.6e-3,
    sampling=dict(kind="uniform", count=2, seed=17,
        variables=[dict(name="width", lower=.28e-3, upper=.32e-3)]))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(ImpedanceYieldDocument(study, minimum=1., maximum=1000.).dumps(),
                       max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

두 표본은 재생 예제이며 제조 수율의 신뢰도를 입증하지 않습니다. `fixed_pitch_m`은
쌍의 `width+gap`을 고정합니다. 측면 접지는 `ground_gap`을 유지하도록 이동하므로
절대 위치는 고정되지 않습니다. 상관 정규분포의 비물리 표본은 재추출하지 않고 실패
행으로 남깁니다. 단일은 고정 수평 pitch를, 두 템플릿 모두는 기존 두 층용
`fixed_plane_spacing_m`을 거부합니다. 고정 주파수 스칼라·주축 재료 연결은 기존
계약으로 `dielectric`에 적용합니다.

```python
from sipi import ImpedanceDesignDocument

goal = ImpedanceDesignDocument("coupled_coplanar_stripline", dict(parameters, gap=.5e-3),
    variable="width", bounds=[.15e-3, .65e-3], target=100., quantity="z_diff",
    fixed_pitch_m=.8e-3, tolerance=.5, max_evaluations=24, mesh=mesh)
assert normalize_saved(goal.dumps()) == goal.dumps()
result = goal.solve()
assert abs(result.residual) <= .5 and abs(result.refined_residual) <= .5
```

요청 메시와 별도 세분 메시 모두 같은 목표 허용오차를 만족해야 합니다. 양의 구간
내 한 변수의 역산이며 전역 최적값이나 실측 제조 공차를 뜻하지 않습니다.

## 수치 검증과 범위

`tests/sipi/test_coplanar_stripline.py`의 독립 scikit-fem P1 조립은 복소·진공
C 및 C_loss를 정규화 행렬 오차 1e−10으로 대조합니다. 동일 메시의 유전체·손실
배율은 1e−12, 별도로 다시 만든 메시의 수직 반사는 0.5%, 대표 C/Z 메시 변화는
1.5%, 상자 폭 두 배의 변화는 0.5% 이내를 요구합니다. 측면 접지가 멀어지는
극한은 기존 offset·coupled stripline과 2% 이내로 대조합니다.

얇고 균일한 CPW 해석 극한에서는 k=w/(w+2g), 완전 타원적분 K를 써서
C=4 eps0 eps K(k)/K(sqrt(1−k²)),
Z=sqrt(mu0/eps0) K(sqrt(1−k²))/(4 sqrt(eps) K(k))입니다.
SciPy `ellipk` 인자는 **modulus의 제곱**입니다. 두 평면과 유한 접지 끝을 멀리
둔 결과가 C/Z 각각 2% 이내이고 세분하면서 해석값 오차가 감소해야 합니다.
이 유한 형상 검증으로 모든 사용자 단면의 오차가 보장되지는 않습니다.

stitching via·pad 전환, 방사·부유 접지, 3차원 귀환 경로 또는 실측 재료 정확도는
검증 범위 밖입니다. 접지는 명시적 이상화입니다. 기준망에 실제 연결되지 않은
금속 띠는 별도의 전기적 모델이 필요합니다.

[제조 단면](manufacturing_sections.md), [공차](study.md), [수율](yield.md),
[임피던스 역산](design.md)을 참고하세요.
