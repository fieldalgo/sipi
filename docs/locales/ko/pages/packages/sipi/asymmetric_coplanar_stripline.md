# 유한 코플래너 접지를 둔 비대칭 매립 신호쌍

`asymmetric_coupled_coplanar_stripline`은 두 접지 평면 사이에 독립 치수의
신호 두 개와 유한 직사각형 접지선 두 개를 배치합니다. 유전체는 균일한
`eps_r`, `tan_delta`이며 측면은 절연 경계입니다. 네 도체 밑면은 하부 평면에서
명시한 `trace_height`를 공유하고 `plane_spacing`은 두 평면 사이 전체 거리입니다.

신호의 `left_width`, `right_width`, `left_thickness`, `right_thickness`,
`left_top_width`, `right_top_width`는 독립입니다. 두께 기본값은 0, 윗폭은 밑폭입니다.
접지선은 `ground_width`, `ground_gap`, `ground_thickness`를 공유하며 접지 두께
기본값은 0입니다. 신호 두께에서 접지 두께를 추론하지 않습니다. 중앙 접지와
교환 대칭 가정은 없으며 길이는 모두 m입니다.

positive는 왼쪽, negative는 오른쪽입니다. 신호 밑면 전체 폭 S=wL+wR+gap에서:

```
x_left = -(gap+wR)/2
x_right = (gap+wL)/2
x_ground = +/-(S/2+ground_gap+ground_width/2)
```

`gap`, `ground_gap`은 밑면 모서리 간격입니다. 테이퍼는 실제 면 간격을 줄일 수
있으며 접촉·겹침·상자/평면 클리핑 검사를 유지합니다. 신호는 공통 밑면에서 위로
뻗으므로 두께가 다르면 수직 중심도 다릅니다. 이는
[수직 중심을 맞춘 비대칭 stripline](asymmetric_stripline.md)과 다른 계약입니다.
동일 신호와 같은 접지 두께는 자동 상자 치수를 포함해 기존
`coupled_coplanar_stripline`의 정규 기하와 정확히 일치합니다.

기본 상자 폭은 `max(12*plane_spacing,4*S,
S+2*ground_gap+2*ground_width+4*plane_spacing)`입니다. 접지선 폭은 물리 치수,
상자 폭은 별도 수치 외곽입니다. 평면·접지선은 하나의 PEC 기준 전위를 공유합니다.
균일 2D 단면이며 비아나 공간 변화 귀환면 모델이 아닙니다.

## 저장·공차·목표값

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    plane_spacing=1e-3, trace_height=.4e-3, eps_r=4., tan_delta=.02,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=8e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coplanar_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71,
        variables=[dict(name='left_width', lower=.28e-3, upper=.32e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    a, b, left_ground, right_ground = row.document.section.traces
    assert abs(b.x-a.x-.7e-3) < 1e-15
    assert abs(a.x0-left_ground.x1-.25e-3) < 1e-15
```

비대칭쌍 저장 study/goal은 공통 전류 0의 명시적 순방향 차동 전류 구동량
`z_diff_forward`를 요구합니다. 대칭 odd mode나 종단 입력 임피던스가 아닙니다.
[고정 피치](asymmetric_pitch.md)는 `gap=pitch-(left_width+right_width)/2`를
유도하며 접지선도 신호 외측 폭을 따라 움직여 접지 간격을 유지합니다. 이때 gap을
독립 표본화하지 않습니다. `plane_spacing`은 직접 치수이며 두 층 높이의 고정 합
제약으로 취급하지 않습니다.

sweep/corners/uniform/상관 normal의 기존 실패 규칙을 유지합니다. 잘못된 bounded
기하는 장 계산 전에 실패하고, normal 실패행은 클리핑·재추출 없이 보존합니다.
재료 study/3·/4의 영역 이름은 `dielectric`입니다. 기존 iid 수율·왼쪽 폭 목표·
paired full-loss line study/2에 연결됩니다. 유손실은 전체 결합 행렬과 별도
`differential_forward_impedance_real`을 사용합니다. 저장 스키마·런타임 의존성은
변경하지 않습니다. 구버전은 새 이름을 거부할 수 있으므로 입력과 정확한 엔진·wheel을 보존합니다.

## 독립 수락 기준

위 유한 단면의 `(edge_size,far_size,grade)`를 `(5 um,.25 mm,.2)`에서
`(2.5 um,.125 mm,.1)`로 세분할 때 C/순방향 Z 변화는 1.5% 미만이어야 합니다.
fine에서 상자 폭 8→16 mm 변화는 .5% 미만입니다. 접지 폭 1.5→3 mm는 별도의
1% 미만 물리 민감도 기준이며 외곽 수렴이나 모든 접지 폭의 무관성을 뜻하지 않습니다.

scikit-fem 12.0.2(BSD-3-Clause)의 독립 complex/vacuum P1 에너지 조립으로
동일 메시의 C/C_loss/C0를 정규 상대 1e−10에 대조합니다. 독립 기하 메시 비교는
아닙니다. 균일 C=eps_r·C0, C_loss=tan_delta·C, L=mu0·eps0·inv(C0), 재료 계수
배율·상반성은 1e−12입니다. 좌우 교환·반사 기하를 독립 메시로 계산하면 행렬 순열·
순방향 Z가 .5% 이내여야 합니다.

별도 두께 0·진공 한계는 해석 영상전하 Green 적분과 상수 전하 패널 풀이를
사용하며 SIPI 기하·메시·솔버와 독립입니다. 한 무한 하부 접지면 위 .5 mm 높이의
신호 [-.55,-.25], [.05,.55] mm와 접지 [-2.3,-.8], [.8,2.3] mm를 명시합니다.
이 기준에는 상부 평면이 없습니다. 80→160 패널/도체의 C/Z 변화는 .3% 미만,
fine FEM 오차는 2% 미만이고 coarse보다 감소해야 합니다. FEM 한계는 상부 평면
12 mm·상자 폭 12 mm에서 각각 독립적으로 24 mm로 늘려 C/Z 변화 .5% 미만을
확인합니다. 이 높은 상부 평면 한계가 실제 유한 1 mm 단면 수락을 대체하지 않습니다.

100Ω 왼쪽 폭 목표는 [.08,.6] mm 범위·고정 .7 mm 피치를 사용합니다. 같은 후보의
요청 메시·절반 세분·16 mm 상자 결과가 모두 목표 ±1Ω 이내여야 합니다.
재료/유손실 재실행은 1e−10을 사용합니다. 특정 기하의 수치 검증이며 실측 정확도·
일반 3D·앱·플랫폼 수락이 아닙니다.

이 기하에서 C/Z 메시 변화는 .2262%/.3099%, 상자 변화는 .000044% 미만,
접지 폭 민감도는 .000700% 미만이었습니다. 동일 메시 독립 최대 차이는
5.557e−15입니다. 100Ω 후보 왼쪽 폭 .12875 mm에서 요청·세분·확장 상자 잔차는
0.094641/0.430341/0.430097Ω입니다. 별도 얇은 도체 한계의 fine C/Z 기준 오차는
.2767%/.3521%였으며 상부 평면을 올린 변화는 .06355%, 상자를 넓힌 변화는
.03419% 미만이었습니다.

[공차](study.md) · [English](../../../../../packages/sipi/asymmetric_coplanar_stripline.md)
