# 법선 두께 코팅을 갖는 비대칭 쌍

[유한 coplanar 접지](asymmetric_conformal_coplanar.md)는 같은 법선 두께 필름 아래 명시적 측면 접지를 추가합니다.

[English](../../../../../packages/sipi/asymmetric_conformal_microstrip.md) ·
[평면 코팅](asymmetric_coated_microstrip.md) · [동일폭 conformal 쌍](conformal_coating.md)

`asymmetric_coupled_conformal_coated_microstrip`는 하부 접지면 위 기판에 두
비대칭 신호를 놓습니다. 정해진 법선 두께의 필름이 기판·도체 윗면·직선 경사면을
덮고 모서리는 miter로 만납니다. 측면 접지 trace는 없습니다. 교환 대칭을
가정하지 않는 균일 준정적2D 단면이며 둥근 모서리·meniscus·실제 증착 형상
예측 모델이 아닙니다.

모든 길이는 m입니다. positive는 왼쪽, negative는 오른쪽이고 두 신호 바닥
전체 폭의 중심을 맞춥니다. gap은 바닥 모서리 사이입니다. 좌우 폭·두께·선택
상단 폭을 독립 지정하며 직사각형 또는 위쪽이 좁아지는 금속만 허용합니다.
overhang은 거부합니다. coating_thickness는 각 면에 수직인 두께이며 평면
코팅의 전체 높이와 다릅니다. 만나는 envelope는 하나의 코팅 영역으로 합치고,
잘림·갇힌 공기 주머니·기존 box 상대 해상도 기준 이하의 형상은 거부합니다.
간격을 자동으로 합치거나 삭제하지 않습니다.

substrate/air는 레이어, coating은 coating_eps_r/coating_tan_delta를 갖는
하나의 국소 유전체 영역입니다. 영역 안 금속이 우선합니다. 위 공기는 가장 높은
코팅면인 substrate_height+max(left_thickness,right_thickness)+coating_thickness
위부터 잽니다. 표현 가능한 양수이면 기하상 허용되지만 외곽 수렴은 별도입니다.
위·옆 경계는 절연이며 제조 치수를 표집할 때 box·air는 명시하는 편이 좋습니다.

좌우 치수가 같으면 coupled_conformal_coated_microstrip과 기하가 정확히 같습니다.
기하는 기존 cross-section/3을 쓰고 study/design에는 새 이름만 등록합니다.
새 저장 schema는 없으며 이전 reader는 이름을 거부할 수 있습니다.

## 상관 공차 저장·실행

```python
from sipi.study import ImpedanceStudyDocument
from sipi.execution import normalize_saved, execute_saved

parameters = dict(left_width=.3e-3, right_width=.5e-3, gap=.3e-3,
    substrate_height=.5e-3, eps_r=4., tan_delta=.02,
    coating_thickness=20e-6, coating_eps_r=3.3, coating_tan_delta=.015,
    left_thickness=35e-6, right_thickness=50e-6,
    box_width=12e-3, air_height=6e-3)
study = ImpedanceStudyDocument('asymmetric_coupled_conformal_coated_microstrip',
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
```

고정 pitch는 gap=pitch-(left_width+right_width)/2로 계산합니다. 잘못된 유계
입력은 장 계산 전에 거부하며 잘못된 normal 행은 원파라미터로 실패 처리하고
잘라내거나 재표집하지 않습니다. study/4의 재료 수치 leaf는 명명된 coating
영역을 대상으로 할 수 있습니다. 기존 iid 수율·full-complex 선로 공차도 명시
재료·도체와 기존 capability 검사로 재실행합니다.

z_diff_forward는 공통 전류0인 실수 정전계 launch이며 odd 고유모드나 부하
임피던스가 아닙니다. 교환 대칭을 요구하는 z_diff는 거부합니다.
full-complex differential_forward_impedance_real은 별도 양입니다.

## 독립 수락 계약

독립 offset-line 교점으로 법선 거리와 분리된 envelope의 film-minus-metal 면적
box_width*d+sum(2*delta_i*t_i)를 검사합니다. s_i=(width_i-top_width_i)/(2*t_i),
delta_i=d/(sqrt(1+s_i*s_i)+s_i)입니다. d20um·간격20/40/60um에서 비대칭 높이
직사각 도체 필름의 합류/분리 위상을 검사합니다. 얇은 도체의 planar-film 극한과
같은 외곽 높이의 vacuum-film→uncoated 극한은 fine에서 각각0.5%미만입니다.

명시 폭.3/.5mm·gap.3mm·기판.5mm·금속35/50um·필름20um 사례의
coarse(edge5um/far.25mm/grade.2)→fine(2.5um/.125mm/.1) C/Z 변화는1.5%미만,
각각 box12→24mm·위 공기6→12mm와 taper 반사 순열은0.5%미만입니다.
계수 배율·vacuum·상호성·같은 메시의 유전율 증가 에너지 단조성은1e-12입니다.

test-only scikit-fem12.0.2(BSD-3-Clause) 같은 메시 complex/vacuum P1 에너지의
독립 조립으로 C/C_loss/C0 정규화 오차1e-10을 검사합니다. 별도 얇은 전진공
image-plane 적분은 구간[-.55,-.25]/[.05,.55]mm·높이.5mm를 독립 지정합니다.
80→160panel 변화0.3%미만·FEM 세분 오차 감소/최종2%미만·box/air2배 변화1%미만입니다.

pitch.7mm에서 왼쪽 폭 [.08,.85]mm·100Ω±1Ω·최대30평가의 역산을 검사합니다.
fine·자동 half 세분·각각 box/air2배에서 같은 폭이 목표 허용치 안에 있고
외곽 상대 변화도0.5%미만이어야 합니다. 재료/full-complex 재실행은1e-10입니다.
유계 사례 검증이며 임의 기하·실측 정확도·방사/3D 전이·브라우저·Windows
지원 인증을 뜻하지 않습니다.
