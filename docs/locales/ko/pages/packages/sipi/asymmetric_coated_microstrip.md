# 비대칭 평면 코팅 microstrip 쌍

[법선 두께 코팅](asymmetric_conformal_microstrip.md)은 기판과 각 신호를 덮는 명시적 mitered 필름을 사용합니다.

[English](../../../../../packages/sipi/asymmetric_coated_microstrip.md) · [동일폭 코팅 쌍](coated_pair.md)

`asymmetric_coupled_coated_microstrip`는 하부 접지면 위 기판에 독립 치수의
두 신호를 놓고 전체 폭의 평평한 필름으로 덮습니다. 측면 접지 trace는 없고
위·옆 외곽은 절연 경계입니다. 균일 준정적 2D 단면입니다.

positive는 왼쪽, negative는 오른쪽이며 두 신호 바닥 전체 폭의 중심을 맞춥니다.
gap은 바닥 모서리 사이 간격입니다. 좌우 폭·금속 두께·선택 상단 폭을 m로
독립 지정하며 기존 taper·겹침·외곽 검사를 유지합니다. 레이어는
substrate/coating/air입니다. 코팅 높이는 기판 표면부터 전체 금속을 포함하며
두 금속 두께보다 커야 합니다. 위 공기는 필름 위부터 시작하므로 양수이면
기하상 허용되지만 작은 외곽의 수치 수렴을 보장하지 않습니다.
평평한 필름이며 conformal mask나 meniscus가 아닙니다.

좌우 치수를 같게 주고 box·위 공기를 명시하면 기존 coupled_coated_microstrip과
기하가 정확히 같습니다. 자동 box와 위 공기는 기존 microstrip scaffold를
재사용합니다. 제조 치수 표집과 절단 경계 변화를 분리하려면 외곽을 명시합니다.
기존 study/design schema에 새 template 이름만 등록하며 이전 reader는 그 이름을
거부할 수 있습니다. 새 저장 schema는 추가하지 않습니다.

## 고정 pitch 공차 저장·실행

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_height=.1e-3, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_coated_microstrip',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='uniform', count=2, seed=71, variables=[
        dict(name='left_width', lower=.28e-3, upper=.32e-3),
        dict(name='coating_height', lower=.09e-3, upper=.11e-3)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['failed'] == 0
for row in study.sample_parameters():
    assert abs(row['gap']+(row['left_width']+row['right_width'])/2-.7e-3) < 1e-15
```

고정 pitch는 gap=pitch-(left_width+right_width)/2로 계산합니다. 잘못된 유계
입력은 메시 전에 거부하며 잘못된 normal 행은 원파라미터와 함께 실패로 남겨
잘라내거나 재표집하지 않습니다. study/4는 substrate/coating 재료 모델의 수치
leaf를 표집할 수 있습니다. 기존 iid 수율과 full-complex line-quantity study/2도
명시 재료·도체로 같은 표본 기하를 재실행하며 capability·skin-depth 검사는 유지합니다.

z_diff_forward는 공통 전류0인 실수 정전계 launch이며 odd 고유모드나 부하
임피던스가 아닙니다. 교환 대칭을 요구하는 z_diff는 거부합니다. full-complex의
differential_forward_impedance_real은 별도 양입니다. 임의 치수는 별도 메시·외곽
수렴이 필요합니다.

## 독립 수락 계약

명시 폭.3/.5mm·gap.3mm·기판.5mm·코팅.1mm·금속35/50um 사례에서
coarse(edge5um/far.25mm/grade.2)→fine(2.5um/.125mm/.1) C/Z 변화1.5%미만,
각각 box12→24mm와 위 공기6→12mm 변화0.5%미만을 요구합니다. 반사 순열과
같은 top 높이의 vacuum-film→air 극한은0.5%, 계수 배율·vacuum·공통 손실·상호성은1e-12입니다.

test-only scikit-fem12.0.2(BSD-3-Clause)의 같은 메시 complex/vacuum P1 에너지로
C/C_loss/C0를 정규화1e-10 이내 대조합니다. 독립 조립이며 독립 기하는 아닙니다.
별도 얇은 전진공 사례는 신호 구간[-.55,-.25]/[.05,.55]mm·높이.5mm를 독립 지정한
grounded-image 적분 패널을 씁니다. 80→160panel C/Z 변화0.3%미만, FEM 세분 오차
감소·최종2%미만, box와 공기2배 변화1%미만입니다.

고정 pitch의 왼쪽 폭 [.08,.85]mm·100Ω±1Ω·최대30평가 역산을 검사합니다.
fine·자동 half 세분·box2배·공기2배에서 같은 폭이 목표 허용치 안에 있고
외곽 변화도0.5%미만이어야 합니다. 재료/full-complex 재실행은1e-10입니다.
실측 보드·방사·3D 전이·브라우저나 Windows의 지원 인증을 뜻하지 않습니다.
