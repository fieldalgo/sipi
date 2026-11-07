# 평면 코팅층의 비대칭 코플래너 쌍

`asymmetric_coupled_coated_grounded_coplanar`는 바닥 접지 평면 위에 서로 다른
신호 두 개와 유한 직사각형 접지 두 개를 놓습니다. 모든 금속 바닥은
`substrate_height`에 있습니다. 전폭 평면 코팅도 여기서 시작하며
`coating_height`는 모든 신호·접지 금속 두께보다 커야 합니다.
`air_height`는 **코팅 위** 높이이므로 금속 두께보다 작은 값도 가능합니다.
상단·측면은 절연입니다. 균일 2D 단면이며 conformal film·meniscus 모델이 아닙니다.

좌우 신호의 폭·두께·윗면 폭은 독립입니다. 유한 접지는 `ground_width`,
`ground_gap`, `ground_thickness`를 공유하고 접지 두께 기본값은 0입니다.
신호 두께에서 접지 두께를 추정하지 않습니다. 중앙 접지·교환 대칭 가정은 없습니다.
길이는 m입니다. 왼쪽 positive, 오른쪽 negative이며 전체 신호 바닥 폭을
중심에 놓습니다. 두 gap은 바닥 모서리 기준이고 taper 접촉·침범은 기존 검증이
거부합니다. 동일 신호·접지 두께는 기존 `coupled_coated_grounded_coplanar`의
자동 외곽을 포함한 정규 기하와 정확히 일치합니다.

영역 이름은 `substrate`, `coating`, `air`입니다. 기판 `eps_r`·`tan_delta`와
코팅 `coating_eps_r`·`coating_tan_delta`는 별도 값입니다. 기본 외곽·공기 높이는
기존 비코팅 구조의 규칙을 따릅니다. 자동 공기 높이는 기판 높이 10배와 가장
큰 금속 두께의 합이며 코팅 위에 놓습니다. 공차 계산에서는 명시 치수로 이러한
연동을 피할 수 있습니다. 접지 폭은 물리 치수, 외곽 폭·공기 높이는 별도 절단입니다.

## 저장·공차·역산

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_width=1.5e-3, ground_gap=.25e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=5e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_grounded_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    p = row.parameters
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
    assert row.document.section.layers[1].thickness == p['coating_height']
    assert row.document.section.layers[2].thickness == 5e-3
```

고정 피치는 `gap=pitch-(left_width+right_width)/2`를 유도하며 접지도 이동해
외측 간격을 유지합니다. `z_diff_forward`는 공통 전류 0의 명시 차동 입사값이며
대칭 odd mode나 종단 임피던스가 아닙니다. 잘못된 유한 범위는 전계 계산 전에
거부하고 정규분포의 실패 행은 클리핑·재샘플링 없이 남깁니다. 재료 study/3·/4는
`substrate`·`coating`을 별도로 연결합니다. iid 수율·왼쪽 폭 목표·유손실 쌍
line study/2를 재사용하며 후자는 전체 복소 행렬의
`differential_forward_impedance_real`을 사용합니다. 새 저장 스키마·의존성은
없고 이전 엔진은 새 템플릿 이름을 거부할 수 있습니다.

## 독립 수락 계약

위 유한 금속 사례의 edge/far/grade `(5 um,.25 mm,.2)`→`(2.5 um,.125 mm,.1)`
C/Z 변화는 1.5% 미만, 세밀한 메시의 외곽 12→24 mm와 공기 5→10 mm 변화는
각 .5% 미만이어야 합니다. 접지 폭 1.5→3 mm의 1% 기준은 별도 물리 민감도입니다.
scikit-fem 12.0.2(BSD-3-Clause)의 독립 복소·진공 P1 조립과 같은 메시의
C/C_loss/C0를 정규 오차 1e-10으로 비교합니다. 독립 기하·메시 생성 비교는 아닙니다.
전체 계수 배율·공통 loss·상반성·진공 L은 1e-12, 좌우 반사·신호 순열은 .5% 기준입니다.

코팅 유전율 1·손실 0이면 같은 상단 높이의 비코팅 구조
(`air_height=코팅 높이+코팅 위 공기 높이`)와 C/C_loss/C0/forward Z가 .5% 이내여야 합니다.
별도 두께 0·전체 진공 한계는 독립 image-charge Green 적분 panel 해와 비교합니다.
명시 신호 구간 [-.55,-.25], [.05,.55] mm, 접지 구간 [-2.3,-.8], [.8,2.3] mm가
무한 접지 평면 .5 mm 위에 있습니다. 80→160 panel의 C/Z 변화 .3% 미만,
세밀한 FEM 오차 2% 미만 및 coarse보다 감소를 요구합니다. 이 진공 한계를
유한 금속·실제 코팅의 검증으로 대체하지 않습니다.

피치 .7 mm, 왼쪽 폭 [.08,.6] mm, 100Ω 목표·허용 1Ω·평가 한도 30입니다.
역산은 위의 세밀한 메시와 자동 `(1.25 um,.0625 mm,.05)` 세분을 사용합니다.
최초 coarse 요청은 세분 결과가 같은 1Ω 목표를 벗어나 거부됐습니다.
그 실패를 보존하고 허용 오차를 완화하지 않습니다.
요청/세분/외곽 24 mm/공기 10 mm에서 동일 후보 폭이 모두 허용 범위를 만족해야 합니다.
저장 재료·복소 선로 재실행은 1e-10입니다. 특정 사례의 수치 기준이며 실측 보드·
일반 3D·브라우저·Windows 정확도를 확정하지 않습니다.

[공차 계산](study.md) · [English](../../../../../packages/sipi/asymmetric_coated_coplanar.md)
