# 법선 두께 코팅을 갖는 비대칭 unbacked 쌍

[English](../../../../../packages/sipi/asymmetric_conformal_unbacked.md) ·
[하부 접지면 있는 구조](asymmetric_conformal_coplanar.md) · [평면 unbacked 코팅](asymmetric_coated_unbacked_coplanar.md)

`asymmetric_coupled_conformal_coated_unbacked_coplanar`는 유한 기판 위 두
유한 직사각 접지 사이에 비대칭 신호를 놓고 아래에는 공기, 위에는 법선 두께의
mitered 필름을 둡니다. 하부·중앙 접지는 없습니다. 모든 외곽은 절연이며 유한
접지만 기준입니다. 교환 대칭을 가정하지 않는 균일 준정적2D 단면입니다.

길이는 m입니다. positive는 왼쪽, negative는 오른쪽이고 신호 바닥 전체 폭의
중심을 맞춥니다. gap은 신호 바닥 사이, ground_gap은 외측 신호 바닥과 접지
사이입니다. 좌우 폭·두께·좁아지는 상단 폭은 독립입니다. 접지는 ground_width와
명시 직사각 ground_thickness(기본0)를 공유하고 신호 두께를 따라가지 않습니다.

동일 coating_thickness가 기판·도체 윗면·직선 옆면에 수직이며 모서리는 miter로
만납니다. 만나는 envelope는 한 coating 영역으로 합치고 overhang·잘림·갇힌
공기·해상도 이하 형상은 거부합니다. meniscus·둥근 모서리·실측 증착 모델이
아닙니다. coating_eps_r/coating_tan_delta는 독립이며 안쪽 금속이 우선합니다.

레이어는 lower_air/substrate/air입니다. 금속과 국소 필름은 lower_air_height
(기본 기판 높이10배)만큼 함께 이동합니다. 위 공기는 가장 높은 신호/접지
코팅면 위부터 잽니다. 제조 치수 표집 시 box와 두 air를 명시하며 각각의 외곽
수렴을 검사해야 합니다. 접지 폭은 물리 변수입니다. 신호와 접지 두께를 모두
같게 주면 기존 동일폭 conformal unbacked 기하와 정확히 같습니다.
기존 cross-section/3·study/design에 기하와 이름을 저장하며 이전 reader는
새 이름을 거부할 수 있습니다.

## 상관 공차 저장

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3, lower_air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_unbacked_coplanar',
    parameters, quantity='z_diff_forward', fixed_pitch_m=.7e-3,
    sampling=dict(kind='normal', count=2, seed=71, correlation=[[1., .4], [.4, 1.]],
        variables=[dict(name='left_width', mean=.3e-3, std=10e-6),
                   dict(name='coating_thickness', mean=20e-6, std=2e-6)]),
    mesh=dict(edge_size=5e-6, far_size=.25e-3, grade=.2))
assert normalize_saved(study.dumps()) == study.dumps()
output = execute_saved(study.dumps(), max_evaluations=2)
assert output['status'] == 'complete' and output['result']['failed'] == 0
for row in study.sample_parameters():
    assert abs(row['gap']+(row['left_width']+row['right_width'])/2-.7e-3) < 1e-15
    assert row['ground_gap'] == parameters['ground_gap']
```

고정 pitch는 gap=pitch-(left_width+right_width)/2로 계산하고 외측 접지 간격을
유지합니다. 잘못된 유계 입력은 메시 전에 거부하고 잘못된 normal 행은 원값과
실패로 남겨 잘라내거나 재표집하지 않습니다. 영역 재료 study/4·iid 수율·
full-complex 선로 재실행은 명시 재료/도체 capability 검사를 유지합니다.
새 기하가 모든 도체 근사를 open-bottom 영역에 자동 허용하는 것은 아닙니다.

z_diff_forward는 공통 전류0인 실수 정전계 launch이며 odd 고유모드나 부하
임피던스가 아닙니다. 대칭을 요구하는 z_diff는 거부하며 full-complex
differential_forward_impedance_real은 별도 양입니다.

## 독립 수락 계약

아래 공기 이동이 금속·국소 필름 형상을 보존하는지 검사합니다. 별도 법선거리·
면적·비대칭높이 합류·명시접지두께·동일입력·JSON 검사를 수행합니다.
thin-metal→planar와 같은 외곽의 vacuum-film→uncoated 극한은 fine에서
C/Z·정전용량/손실 차이0.5%미만이어야 합니다.

명시 사례의 coarse(edge5um/far.25mm/grade.2)→fine(2.5um/.125mm/.1)
C/Z 변화1.5%미만, 각각 box12→24mm·위 공기6→12mm·아래 공기6→12mm 및 반사
순열0.5%미만을 요구합니다. 접지 폭1.5→3mm는 물리 민감도입니다. 배율·vacuum·
상호성·같은 메시 필름 유전율 증가 에너지 단조성은1e-12입니다.

test-only scikit-fem12.0.2(BSD-3-Clause) 같은 메시 complex/vacuum P1 에너지
독립 조립은 C/C_loss/C0 정규화 오차1e-10 이내입니다. 별도 얇은 전진공 기준은
미지 공통전위·전체 전하0인 자유공간 -log(distance) 적분이며 image plane이나
먼 접지 외벽을 두지 않습니다. 신호[-.55,-.25]/[.05,.55]mm와
접지[-2.3,-.8]/[.8,2.3]mm를 factory와 독립 지정합니다. 80→160panel 변화0.3%미만;
box24mm·상하 공기12mm에서 FEM(4um/.5mm/.2)→(1um/.25mm/.1) 오차 감소/최종2%미만;
모든 외곽2배 시 C/Z 변화1%미만입니다.

pitch.7mm·왼쪽 폭 [.08,.85]mm·100Ω±1Ω·최대30평가 역산을 검사합니다.
fine·자동 half 세분·각각 box/상하 air2배에서 같은 폭이 목표 허용치 안에 있고
외곽 상대 변화도0.5%미만이어야 합니다. 재료/full-complex 재실행은1e-10입니다.
임의 기하·실측 정확도·방사/3D·브라우저·Windows 지원 인증을 뜻하지 않습니다.
