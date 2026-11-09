# 법선 두께 코팅을 갖는 비대칭 coplanar 쌍

[하부 접지면 없는 구조](asymmetric_conformal_unbacked.md)는 유한 측면 접지·법선 필름을 유지하고 독립 아래 공기를 추가합니다.

[English](../../../../../packages/sipi/asymmetric_conformal_coplanar.md) ·
[측면 접지 없는 쌍](asymmetric_conformal_microstrip.md) · [동일폭 코팅 coplanar](conformal_coplanar.md)

`asymmetric_coupled_conformal_coated_grounded_coplanar`는 하부 접지면 위 두
유한 직사각 coplanar 접지 사이에 비대칭 신호를 놓습니다. 법선 두께의 mitered
유전체 필름이 기판과 네 도체를 덮습니다. 중앙 접지는 없으며 교환 대칭도
가정하지 않습니다.

길이는 m입니다. positive는 왼쪽, negative는 오른쪽이고 신호 바닥 전체 폭의
중심을 맞춥니다. gap은 신호 바닥 사이, ground_gap은 외측 신호 바닥과 인접
접지 사이입니다. 신호 폭·두께·좁아지는 상단 폭은 독립입니다. 접지는
ground_width와 명시 ground_thickness를 공유합니다. 접지 두께는 기본0이며
신호 두께를 따라가지 않습니다. coating_thickness는 기판·윗면·직선 옆면에
수직입니다. 만나는 envelope는 합치며 overhang·갇힌 공기·잘림·기존 해상도
기준 이하 형상은 거부합니다. 둥근 모서리·meniscus·실측 증착 모델이 아닙니다.

coating은 독립 유전율·손실을 갖는 하나의 국소 영역이며 안쪽 금속이 우선합니다.
air_height는 가장 높은 신호/접지 코팅면인
substrate_height+max(left_thickness,right_thickness,ground_thickness)+coating_thickness
위부터 잽니다. 표현 가능한 양의 air는 기하 조건이며 수렴 근거는 아닙니다.
위·옆은 절연이고 유한 접지와 하부 접지면이 기준입니다.

신호와 접지 두께를 모두 같게 주면 기존 동일폭 코팅 coplanar 기하와 정확히
같습니다. 기존 cross-section/3과 study/design에 기하/새 template 이름을
저장하며 새 schema는 없습니다. 이전 reader는 이름을 거부할 수 있습니다.
box/air를 명시해 물리 표집과 외곽 절단을 분리합니다. 접지 폭 변경은 물리
민감도이며 외곽 수렴 검사가 아닙니다.

## 고정 pitch 상관 공차

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    ground_gap=.25e-3, ground_width=1.5e-3, ground_thickness=35e-6,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_grounded_coplanar',
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

고정 pitch는 gap=pitch-(left_width+right_width)/2로 계산하며 외측 접지 간격을
유지합니다. 잘못된 유계 입력은 장 계산 전에 거부하고 잘못된 normal 행은
원파라미터와 실패로 남겨 잘라내거나 재표집하지 않습니다. study/4 영역 재료
수치 leaf·iid 수율·full-complex 선로 공차는 명시 재료·도체 capability 검사로
기하를 재실행합니다.

z_diff_forward는 공통 전류0인 실수 정전계 launch이며 odd 고유모드나 부하
임피던스가 아닙니다. 교환 대칭 z_diff는 거부하고 full-complex의
differential_forward_impedance_real은 별도 양입니다.

## 독립 수락 계약

독립 offset-line 거리와 필름에서 모든 금속을 뺀 면적으로 분리된 mitered
envelope를 검사합니다. 20um필름·간격20/40/60um에서 높이가 다른 신호의
합류/분리를 확인합니다. 접지 두께0/20/80um로 최고 코팅 높이와 독립성을
검사합니다. thin-metal→planar와 같은 외곽의 vacuum-film→uncoated 극한은
fine에서 C/C_loss/C0/Z 차이0.5%미만입니다.

명시 사례의 coarse(edge5um/far.25mm/grade.2)→fine(2.5um/.125mm/.1)
C/Z 변화1.5%미만, 각각 box12→24mm·air6→12mm·taper 반사 순열0.5%미만을
요구합니다. 접지 폭1.5→3mm는 별도 기록합니다. 배율·vacuum·상호성·같은 메시
유전율 증가 에너지 단조성은1e-12입니다.

test-only scikit-fem12.0.2(BSD-3-Clause) 같은 메시의 complex/vacuum P1
독립 에너지 조립은 C/C_loss/C0 정규화1e-10 이내입니다. 별도 얇은 전진공
grounded-image 적분은 신호[-.55,-.25]/[.05,.55]mm와
접지[-2.3,-.8]/[.8,2.3]mm·높이.5mm를 명시합니다. 전체 행렬에서 접지 전위0인
신호 블록을 취합니다. 80→160panel 변화0.3%미만·FEM 세분 오차 감소/최종2%미만·
box/air2배 변화1%미만입니다.

pitch.7mm·왼쪽 폭 [.08,.85]mm·100Ω±1Ω·최대30평가 역산을 검사합니다.
fine·자동 half 세분·각각 box/air2배에서 같은 폭이 목표 허용치 안에 있고
외곽 변화도0.5%미만이어야 합니다. 재료/full-complex 재실행은1e-10입니다.
유계 사례 검증이며 임의 기하·실측 정확도·방사/3D·브라우저·Windows 지원
인증을 뜻하지 않습니다.
