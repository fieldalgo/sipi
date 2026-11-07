# 두 유전체 경계의 비대칭 매립 코플래너 쌍

`asymmetric_coupled_layered_coplanar_stripline`은 두 접지 평면 사이에 독립
치수의 신호 두 개와 유한 직사각형 접지 두 개를 놓습니다. 모든 바닥면은
`lower_height`의 재료 경계에 있고 금속은 위로 뻗습니다. `upper_height`는
금속 두께를 포함하며 각 신호·접지 두께보다 커야 합니다. 측면은 절연이고
중앙 접지는 없습니다. 위·아래 재료를 임의 평균하지 않습니다.

좌우 신호 폭·두께·윗면 폭은 독립입니다. 접지는 `ground_gap`, `ground_width`,
`ground_thickness`를 공유하며 접지 두께 기본값은 0입니다. 신호 두께에서
접지 두께를 추정하지 않습니다. 길이는 m입니다. 전체 신호 바닥 폭
S=wL+wR+gap를 중심에 놓고 신호 중심은 `-(gap+wR)/2`, `(gap+wL)/2`,
접지 중심은 `+/-(S/2+ground_gap+ground_width/2)`입니다. 왼쪽은 positive,
오른쪽은 negative입니다. 간격은 바닥 모서리 기준이며 taper 접촉·겹침과
외곽·평면 침범은 기존 기하 검증이 거부합니다.

`lower_eps_r`, `upper_eps_r`, `lower_tan_delta`, `upper_tan_delta`는 `lower`와
`upper` 영역을 별도로 정의합니다. 두 신호가 같고 접지 두께도 같으면 기존
`coupled_layered_coplanar_stripline`의 정규 기하 JSON과 정확히 일치합니다.
전체 높이 H일 때 기본 외곽 폭은 `max(12*H,4*S,S+2*ground_gap+2*ground_width+4*H)`입니다.
접지 폭은 물리 치수이고 외곽 폭은 별도 절단 영역입니다. 균일한 2D 단면 모델입니다.

## 저장·공차·역산 연결

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    lower_tan_delta=.01, upper_tan_delta=.03,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=8e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_layered_coplanar_stripline',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    fixed_plane_spacing_m=1e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='lower_height', lower=.38e-3, upper=.42e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=2)
assert result.failed == 0 and len(result.rows) == 2
for row in result.rows:
    p = row.parameters
    assert abs(p['lower_height']+p['upper_height']-1e-3) < 1e-15
    assert abs(p['gap']+(p['left_width']+p['right_width'])/2-.7e-3) < 1e-15
```

고정 피치는 `gap=pitch-(left_width+right_width)/2`를 유도하고 접지도 함께
이동해 바깥 간격을 유지합니다. 전체 적층 두께 고정은 정확히 한 층 높이를
샘플링하고 나머지를 유도합니다. 두 제약을 동시에 사용할 수 있습니다.
유한 범위의 잘못된 기하는 계산 전에 거부하고 정규분포의 실패 행은
클리핑·재샘플링 없이 남깁니다. 재료 study/3·/4는 `lower`·`upper`에 각각
연결하며 iid 수율·폭 목표·유손실 쌍 line study/2를 재사용합니다.

`z_diff_forward`는 공통 전류 0의 명시 차동 전류 입사값입니다. 대칭 odd mode나
종단 입력 임피던스로 해석하지 않습니다. 유손실 study/2는 전체 복소 행렬의
`differential_forward_impedance_real`을 사용합니다. 저장 스키마·런타임 의존성은
추가하지 않습니다. 이전 엔진은 새 템플릿 이름을 거부할 수 있으므로 엔진·wheel
식별자를 입력과 함께 보관합니다.

## 독립 수락 계약

위 유한 금속 사례의 메시 `(5 um,.25 mm,.2)`→`(2.5 um,.125 mm,.1)`에서
C/forward-Z 변화 <1.5%, 세밀한 메시의 외곽 8→16 mm 변화 <.5%를 요구합니다.
접지 폭 1.5→3 mm의 <1% 기준은 별도 물리 민감도이며 외곽 수렴이 아닙니다.
scikit-fem 12.0.2(BSD-3-Clause)의 독립 복소·진공 P1 에너지 조립과 C/C_loss/C0
정규 오차 1e-10으로 비교합니다. 같은 메시를 사용하므로 독립 기하 생성 검증은
아닙니다. 계수 배율·공통 loss 비례·상반성·L=mu0·eps0·inv(C0)는 1e-12,
동일 재료의 균일 단면 환원 및 좌우 반사·신호 순열은 .5% 기준입니다.

별도 해석 한계는 **네 도체 모두 두께 0**, 위·아래 높이 각 .5 mm입니다.
수직 대칭으로 복소 에너지가 `[(epsL*(1-j*tanL)+epsU*(1-j*tanU))/2]*C0`가 됩니다.
epsL=2, epsU=6, loss=.01/.03에서 C=4*C0, C_loss=.1*C0의 세밀한 메시 오차를
.5% 이내로 요구합니다. 유한 금속이나 비대칭 높이에 이 평균식을 적용하지 않습니다.
별도 .4/.6 mm 두께 0 사례에서 높이와 재료를 함께 반사한 행렬·forward Z도
.5% 이내여야 합니다.

피치 .7 mm, 왼쪽 폭 [.08,.6] mm, 목표 100Ω, 평가 한도 30, 허용 1Ω입니다.
요청 메시·세분 메시·외곽 16 mm에서 같은 후보 폭이 모두 허용 범위를 만족해야 합니다.
저장 재료·복소 선로 재실행은 1e-10 기준입니다. 특정 사례의 수치 수락이며
실측 보드·일반 3D·플랫폼 정확도를 확정하지 않습니다.

[공차 계산](study.md) · [English](../../../../../packages/sipi/asymmetric_layered_coplanar_stripline.md)
