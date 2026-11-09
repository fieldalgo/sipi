# 비대칭 평면 코팅 unbacked coplanar 쌍

[English](../../../../../packages/sipi/asymmetric_coated_unbacked_coplanar.md) ·
[비코팅 비대칭 쌍](asymmetric_unbacked_coplanar.md) · [동일폭 코팅 쌍](coated_unbacked.md)

`asymmetric_coupled_coated_unbacked_coplanar`는 유한 기판 위 두 유한 coplanar
접지 사이에 비대칭 신호 쌍을 두고 전체 폭 평면 코팅으로 덮습니다. 하부 접지면과
중앙 접지는 없습니다. 모든 외곽은 절연 경계이며 유한 접지 trace만 기준입니다.
교환 대칭을 가정하지 않는 균일 준정적 2D 단면입니다.

좌우 폭·두께·선택 상단 폭은 독립입니다. 직사각 접지는 ground_width,
ground_gap, 명시 ground_thickness(기본0)를 공유하며 신호 두께를 따라가지 않습니다.
positive는 왼쪽, negative는 오른쪽이고 신호 바닥 전체 폭의 중심을 맞춥니다.
gap은 두 신호 바닥 사이, ground_gap은 외측 신호 바닥과 접지의 간격입니다.
기존 taper·접촉·잘림 검사를 유지하며 모든 길이는 m입니다.

영역 순서는 lower_air/substrate/coating/air입니다. 모든 금속 바닥은
lower_air_height+substrate_height에 있습니다. coating_height는 기판 위부터
전체 구리 높이를 포함하며 모든 금속 두께보다 커야 합니다. air_height는 코팅
위에서 시작하므로 구리 두께보다 작더라도 양수이면 기하상 허용됩니다. 코팅은
독립 coating_eps_r/coating_tan_delta를 갖습니다. 평평한 전체 폭 필름이며
conformal mask나 meniscus를 뜻하지 않습니다.

아래 공기는 기본 기판 높이의10배입니다. 자동 위 공기는 기판 높이10배+최대
금속 두께이며 코팅 위부터 잽니다. 다른 치수를 표집할 때 자동 외곽도 바뀌지
않도록 두 공기 높이와 box 폭을 명시하는 편이 좋습니다. 접지 폭은 물리 변수이고
box·상하 공기는 별도 절단 경계입니다. 접지 확대는 외곽 수렴 검사가 아닙니다.

좌우 폭·두께·taper와 접지 두께를 같게 주면 기존
coupled_coated_unbacked_coplanar 기하와 정확히 같습니다. 기존 study/design
JSON에 새 template 이름을 등록하며 새 저장 schema를 추가하지 않습니다.
이름을 모르는 이전 reader는 거부할 수 있습니다.

## 저장 기하·재료 공차

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_unbacked_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['failed'] == 0
for parameters in study.sample_parameters():
    assert abs(parameters['gap']+(parameters['left_width']+parameters['right_width'])/2-.7e-3) < 1e-15
```

z_diff_forward는 공통 전류0인 실수 정전계 forward launch이며 odd 고유모드나
부하 임피던스가 아닙니다. 교환 대칭을 요구하는 z_diff는 거부합니다. 고정 pitch는
gap=pitch-(left_width+right_width)/2로 계산하고 외측 접지 간격을 유지합니다.
잘못된 유계 입력은 메시 전에 거부하며 잘못된 normal 행은 원파라미터와 함께
실패로 남겨 재표집·잘라내기를 하지 않습니다.

study/4에서 substrate/coating 재료 모델의 수치 leaf를 표집할 수 있습니다.
기존 iid 수율과 full-complex line-quantity study/2도 명시한 재료·도체 조건으로
기하를 재사용합니다. 후자의 differential_forward_impedance_real은 정전계 양과
다릅니다. 이 template 등록이 모든 장 방법·도체 근사를 open-bottom 단면에
허용하는 것은 아니며 기존 capability와 skin-depth 검사를 유지합니다.

## 독립 수락 계약

명시한 유한 비대칭 사례에서 coarse(edge5um/far.25mm/grade.2)→fine
(2.5um/.125mm/.1) C/Z 변화는1.5%미만이어야 합니다. fine에서 box12→24mm,
상부 공기6→12mm, 하부 공기6→12mm 각각0.5%미만을 요구합니다. 접지 폭1.5→3mm는
물리 민감도로 별도 보고합니다. 반사 도체 순열과 동일 상단 높이의 vacuum-film→air
극한은 각각0.5%, 균일 유전율 배율·vacuum L·공통 손실·상호성은1e-12입니다.

test-only scikit-fem12.0.2(BSD-3-Clause)의 같은 메시 complex/vacuum P1 에너지로
C/C_loss/C0를 정규화1e-10 이내에서 대조합니다. 독립 기하나 메시 생성은 아닙니다.
별도 얇은 전진공 사례는 전체 전하0·미지 공통전위를 둔 자유공간 -log(distance)
적분 패널을 사용하며 image plane이나 먼 접지 외벽을 두지 않습니다. 신호 구간
[-.55,-.25]/[.05,.55]mm와 접지[-2.3,-.8]/[.8,2.3]mm는 factory와 독립 지정합니다.
80→160panel 변화0.3%미만;box24mm·상하 공기12mm에서 FEM
(4um/.5mm/.2)→(1um/.25mm/.1) C/Z 오차 감소·최종2%미만, 전체 외곽2배 시1%미만입니다.

pitch.7mm에서 왼쪽 폭 [.08,.85]mm·100Ω±1Ω·최대30평가의 역산을 검사합니다.
요청 fine/자동 half 세분과 각각의 box·상하 공기2배에서도 같은 폭의 결과가 목표
허용치 안에 있어야 하며 외곽 변화는0.5%미만입니다. 재료/full-complex 재실행은
1e-10을 씁니다. 임의 치수, 실측 보드, 방사·3D 전이, 브라우저나 Windows의
정확도·지원 인증을 뜻하지 않습니다.
