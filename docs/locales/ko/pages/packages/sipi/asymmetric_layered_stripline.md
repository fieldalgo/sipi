# 두 유전체 경계의 비대칭 쌍

`asymmetric_coupled_layered_stripline`은 접지면 사이에서 두 도체의 **바닥면**을
`y=lower_height`에 놓습니다. 동박은 위쪽 유전체로 뻗습니다. `upper_height`는
동박을 포함하며 각 위쪽 여유는 `upper_height - thickness`입니다. 전체 접지면
간격은 `lower_height+upper_height`입니다. 각 도체의 수직 중심을 접지면 사이
중앙에 놓는 [균일 유전체 비대칭 쌍](asymmetric_stripline.md)과 구분됩니다.

길이는 미터입니다. 필수 입력은 `left_width`, `right_width`, `gap`,
`lower_height`, `upper_height`, `lower_eps_r`, `upper_eps_r`입니다.
독립적인 `left_thickness`, `right_thickness` 기본값은 0이며,
`left_top_width`, `right_top_width`로 대칭 사다리꼴 윗폭을 지정합니다.
`lower_tan_delta`, `upper_tan_delta` 기본값은 0입니다. `lower`, `upper`
유전체는 평균내지 않고 각각의 물성으로 해석합니다.

왼쪽이 positive, 오른쪽이 negative입니다. 전체 바닥 폭 구간의 중심은 x=0이며
`x_left=-(gap+right_width)/2`, `x_right=(gap+left_width)/2`입니다.
gap은 바닥 폭의 수평 간격으로, 사다리꼴 면 사이 최소 거리와 다를 수 있습니다.
기존 접촉·겹침·윗폭·상자 검사와 측면 절연 경계를 유지합니다. 기본 상자 폭은
`max(12*(lower_height+upper_height), 4*(left_width+gap+right_width))`입니다.
재현하려면 명시하고 메시 세분화와 별도로 외곽 크기 수렴을 확인하세요.

양쪽 폭·두께·윗폭이 같으면 기존 `coupled_layered_stripline`의 정규 기하와
정확히 일치합니다. 비대칭 쌍은 교환 대칭이나 독립 짝/홀 모드를 가정하지 않습니다.
저장 공차·역산은 `z_diff_forward`만 받습니다. 이는 공통 발사 전류가 0인
전방 차동 전류 발사 임피던스이며, 공통 전압 0이나 종단 입력 임피던스를 뜻하지 않습니다.

## 피치와 적층 두께의 복합 제약

[두 폭 피치 규칙](asymmetric_pitch.md)은
`gap=fixed_pitch_m-(left_width+right_width)/2`로 간격을 유도합니다.
별도로 `fixed_plane_spacing_m`은 정확히 한 층 높이를 샘플링할 때 나머지 높이를
유도합니다. 두 제약을 함께 사용할 수 있습니다. nominal부터 제약을 만족해야 하며
유도되는 gap이나 양쪽 높이를 동시에 독립 변수로 샘플링할 수 없습니다.
유계 입력의 잘못된 꼭짓점은 계산 전에 거부하며, 정규분포의 잘못된 표본은
잘라내거나 재추출하지 않고 원래 실패 행으로 남깁니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.4e-3,
    lower_height=.4e-3, upper_height=.6e-3, lower_eps_r=3., upper_eps_r=5.,
    left_thickness=35e-6, right_thickness=50e-6,
    lower_tan_delta=.01, upper_tan_delta=.03, box_width=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_layered_stripline', parameters,
    quantity='z_diff_forward', fixed_pitch_m=.8e-3, fixed_plane_spacing_m=1e-3,
    sampling=dict(kind='corners', variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='lower_height', lower=.35e-3, upper=.45e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
result = study.analyze(max_evaluations=4)
assert result.failed == 0 and len(result.rows) == 4
for row in result.rows:
    a, b = row.document.section.traces
    assert abs(b.x-a.x-.8e-3) < 1e-15
    assert abs(row.document.section.height-1e-3) < 1e-15
```

재료 study/3·/4는 `lower`, `upper`를 별도로 연결합니다. 기존 iid 수율,
단일 변수 역산과 유손실 쌍 line study/2도 같은 입력을 사용합니다. 유손실 쌍은
`differential_forward_impedance_real`을 명시하고 전체 결합 특성 행렬을 유지합니다.
템플릿 32종·저장 스키마 42종이며 필드나 의존성은 추가되지 않습니다. 이전 판독기는
새 이름을 거부할 수 있으므로 정확한 엔진·휠 식별자를 기록하세요.

## 검증 범위

위 유한 동박 fixture에서 메시 `(edge_size,far_size,grade)`를
`(5 um,.25 mm,.2)`에서 `(2.5 um,.125 mm,.1)`로 줄일 때 C/전방 Z 차이는
0.1916%/0.2700%로 사전 기준 1.5% 이내입니다. 세밀한 메시에서 상자 폭을
6→12 mm로 늘린 차이는 0.000774%/0.000672%로 .5% 기준 이내입니다.
세밀한 메시의 전방 임피던스는 89.4784 ohm입니다. 해당 fixture의 근거입니다.

scikit-fem 12.0.2(BSD-3-Clause)의 독립 복소/진공 P1 조립과 같은 메시에서
C/C_loss/C0를 normwise 상대 `1e-10`으로 대조합니다. 별도로 상반성·수동성,
균일 유전율 배율과 동일 손실 항등식을 `1e-12`로 확인합니다. 동일 재료·동일
두께의 중앙 배치는 균일 쌍에 .5% 이내로 환원됩니다. **두께 0에서만** 아래/위
높이와 재료 교환을 수직 반사로 볼 수 있으며 C/C0/L/C_loss/Z 차이가 .5%
이내입니다. 위로 뻗은 유한 동박은 이 교환의 반사 대칭을 갖지 않습니다.

피치 .8 mm·왼쪽 폭 [.1,.8] mm 범위의 100 ohm 역산은 .1984375 mm를 선택합니다.
요청/세분/외곽 확대 잔차 −.271112/−.188334/−.271320 ohm은 모두 1 ohm 기준을
만족합니다. 저장 재료·수율·유손실 쌍 입력은 직접 계산과 `1e-10`으로 재현합니다.
실측 보드 정확도, 임의 입력 수렴, 일반 3D 전이 구조나 앱·플랫폼 수락을 뜻하지 않습니다.

[공차](study.md) · [English](../../../../../packages/sipi/asymmetric_layered_stripline.md)
