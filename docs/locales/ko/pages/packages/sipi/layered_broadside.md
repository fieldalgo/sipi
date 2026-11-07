# 세 유전체 층의 broadside 선로 쌍

[English](../../../../../packages/sipi/layered_broadside.md)

`layered_broadside_stripline`은 두 외곽 접지면 사이에 같은 폭·두께의 직사각형
도체를 위아래로 배치합니다. 아래·도체 사이·위 유전체의 유전율과 손실탄젠트를
각각 지정하며, 부호 있는 수평 오프셋과 서로 다른 외곽 간격을 허용합니다.
길이 방향으로 균일한 준정적 단면이며 비아·패드·층간 전이 모델은 아닙니다.

```python
from sipi import layered_broadside_stripline, CrossSectionDocument

parameters = dict(width=.35e-3, gap=.15e-3, lower_height=.25e-3,
    upper_height=.45e-3, lower_eps_r=3., gap_eps_r=4., upper_eps_r=5.,
    thickness=35e-6, offset=.12e-3, lower_tan_delta=.01,
    gap_tan_delta=.02, upper_tan_delta=.03, box_width=6e-3)
mesh = dict(edge_size=8e-6, far_size=.25e-3, grade=.3)
section = layered_broadside_stripline(**parameters)
document = CrossSectionDocument(section, mesh=mesh)
restored = CrossSectionDocument.loads(document.dumps())
assert restored.dumps() == document.dumps()
line = restored.analyze()
assert line.z_diff_forward > 0
```

길이는 m입니다. `width`, `thickness`, `gap`, `lower_height`, `upper_height`는
양수입니다. 두 도체의 폭·두께는 같고 이 템플릿은 사다리꼴 도체를 다루지 않습니다.
여기서 height는 **구리를 제외한 도체 바깥면과 외곽 접지면 사이 간격**이며,
gap은 두 도체 안쪽면 사이 거리입니다.

| 아래에서 위 순서 | 높이 | 재료 이름 |
|---|---|---|
| 아래 접지면~아래 도체 밑면 | `lower_height` | `lower` |
| 아래 positive 도체 | `thickness` | lower 층 내부의 금속 hole |
| 아래 도체 윗면~위 도체 밑면 | `gap` | `gap` |
| 위 negative 도체 | `thickness` | upper 층 내부의 금속 hole |
| 위 도체 윗면~위 접지면 | `upper_height` | `upper` |

전체 접지면 간격은 `lower_height + upper_height + gap + 2*thickness`입니다.
층 두께는 각각 `lower_height+thickness`, `gap`, `upper_height+thickness`이며
유전체 경계가 도체 안쪽면에 닿습니다. positive 중심 x는 -offset/2, negative는
+offset/2입니다. offset은 유한한 부호 있는 값이고 0이면 두 도체가 정렬됩니다.
유전체를 평균하지 않습니다. 유한한 옆벽에는 절연 경계조건을 쓰므로
`box_width`를 늘려 수렴을 확인해야 합니다. 기본 폭은
`max(12*total_height, 4*(width+abs(offset)))`이며 기본 메시와 함께 시작값일 뿐입니다.

## 임피던스·손실·대칭

C·C0·L·유전체 손실 행렬은 비대칭을 보존합니다. 저장된 study·design은
`quantity="z_diff_forward"`를 사용합니다. 양의 정부호 특성 임피던스 행렬에서
공통 전류 0인 순방향 Vdiff/Idiff를 구하며 독립적인 공통/차동 고유모드를 가정하지 않습니다.
다른 실수 임피던스 진단값처럼 저항·유전체 손실을 제외하므로 그 효과는 기존
주파수 의존 line/network API로 계산합니다. 비대칭 결과의 `even_odd()`는 기존
대칭성 검사에서 실패합니다. 양쪽 외곽 간격·재료가 같으면 대칭 쌍으로,
모든 재료가 같으면 기존 균질 broadside 단면으로 환원됩니다.

세 층의 이름으로 기존 scalar/principal-axis 재료 override와 재료변수 binding을
사용할 수 있습니다. 손실탄젠트 계산은 복소 정전계 모델이며 재료 데이터시트의
실측 정확도를 새로 검증했다는 뜻은 아닙니다.

## 저장·공차·수율·역산

```python
from sipi.study import ImpedanceStudyDocument
from sipi.yield_assessment import ImpedanceYieldDocument
from sipi.execution import execute_saved, normalize_saved

study = ImpedanceStudyDocument("layered_broadside_stripline", parameters,
    quantity="z_diff_forward", mesh=mesh,
    sampling=dict(kind="uniform", count=2, seed=17,
        variables=[dict(name="offset", lower=-.1e-3, upper=.1e-3)]))
saved = normalize_saved(study.dumps())
report = execute_saved(ImpedanceYieldDocument(study, minimum=40., maximum=60.).dumps(),
                       max_evaluations=2)
assert len(report["result"]["rows"]) == 2
```

소수 표본의 인터페이스 예제이며 수율 인증에 충분한 표본수라는 뜻은 아닙니다.
study/1–4, [수율 평가](yield.md), [고정 후보 선택](yield_design.md), 기존 임피던스
목표 역산이 같은 템플릿을 재사용합니다. uniform/normal offset은 0을 넘나들 수 있고,
normal의 비물리적 치수·재료 행은 실패로 보존합니다. 양수 범위의 width/gap/재료
목표는 `z_diff_forward`와 기존 세분 메시 재검증을 사용합니다. 기존 양수 search bounds를
부호 있는 구간으로 확장하지는 않습니다. 수평 `fixed_pitch_m`과 두 층용
`fixed_plane_spacing_m`은 이 세 층 수직 기하에 적용하지 않고 거부합니다.
후보 치수를 명시해야 하며 다른 두께를 몰래 유도하지 않습니다.

기하는 기존 cross-section/1 JSON으로 저장하므로 새 schema 버전은 없습니다.
study는 템플릿·치수·재료계수·결정된 메시·표본 설정·행별 오류를 보존하며,
재료변수 study는 실제 행별 재료 snapshot도 남깁니다. 일반 3D 전이,
서로 다른 도체 폭/두께·사다리꼴은 이 템플릿 범위 밖입니다.

## 검증 범위

위 대표 비대칭·오프셋 사례를 같은 메시의 독립 scikit-fem P1 복소/진공 정전계와
비교하여 C·C_loss·C0 정규화 차이 `1e-10` 이하를 요구합니다. 별도 coarse/fine에서
C·순방향 임피던스 변화 1.5% 이하, 옆 계산영역 두 배에서 0.5% 이하를 요구합니다.
이는 명시한 사례의 기준이며 모든 입력의 오차 상한이 아닙니다. 양의/수동/상호적인 행렬,
기하 반사·재료 교환, 균질 broadside 환원, 같은 메시에서 균일 유전율 배율 불변식,
넓은 평행판 차동 극한 5%와 메시 세분을 검사합니다. JSON·확률/재료 공차·실패 행,
별도 세분 검사를 거치는 저장 width 역산도 검증합니다.
실측 제조 정확도·새 앱/플랫폼 검증 완료를 뜻하지 않습니다.
