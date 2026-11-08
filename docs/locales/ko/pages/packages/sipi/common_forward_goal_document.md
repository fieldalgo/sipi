# 공통 전류 순방향 임피던스 목표 저장

[명시적 study /3](common_forward_line_study.md)는 공통 전류 물리량의 기술적 표본 분석을 제공합니다.

[English](../../../../../packages/sipi/common_forward_goal_document.md) | **한국어**

명시적 `sipi.line-quantity-design/3`는 `common_forward_impedance_real`을 추가하고
기존 두 단일 신호 물리량과 차동 순방향 물리량도 유지합니다. 생성자 기본은 `/1`이며
v1·v2는 공통 전류 목표를 계속 거부합니다. 기존 단일 신호·차동 요청 결과는 그대로이고
저장 공차 v1·v2도 새 물리량을 거부합니다.

목표는 Vc=(V1+V2)/2,Ic=I1+I2,입력면 Id=(I1-I2)/2=0에서의 Re(Zcc)[ohm]입니다.
전체 유손실 비대칭 결합을 유지하므로 차동 전압이 0일 필요가 없고 하류 Id도0으로
유지된다고 가정하지 않습니다. 지정 순방향 입력이며 독립 고유모드·abs(Zcc)·유한
종단 임피던스가 아닙니다. [API와 수렴 한계](common_forward_line_goal.md)를 확인하세요.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma, rms):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))
source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3, substrate_height=.5e-3,
        eps_r=4., tan_delta=.02, left_thickness=35e-6, right_thickness=50e-6,
        air_height=10e-3, box_width=24e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='left_width', lower=.2e-3, upper=1e-3)]))
goal = LineQuantityDesignDocument(source, schema='sipi.line-quantity-design/3',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='common_forward_impedance_real', target=40.,
    tolerance=.125, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert max(abs(report['result']['residual']), abs(report['result']['refined_residual'])) <= .125
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
assert report['result']['quantity'] == 'common_forward_impedance_real'
```

최상위7키는 schema,study,conductor,quantity,target,tolerance,max_evaluations입니다.
중첩 study/3 또는 /4의 기존 `z_diff_forward` 표시는 두 신호 기하·재료 입력 계약을
선택할 뿐입니다. 해당 준정적 study 해석은 호출하지 않으며 바깥 `quantity`가 공통
전류 목표를 선택합니다. `z_diff` 모드 입력은 거부합니다. 고정 양의 주파수 하나,
count=2 sweep,양의 증가 bounds를 가진 변수 하나,정확히 두 ordered 신호가 필요합니다.

고정 피치·전체 적층 높이,재료 숫자 leaf 연결,엄격한 고정 line/6 도체 법칙,
양끝 기하·재료 사전 검사와 nominal 도체 검사를 유지합니다. 파싱은 메시를 만들지
않습니다. 이후 factory·장·진단 실패는 실제 시도 횟수·완료 이력·단계·가능한 입력을
보존합니다. 공통 실행은 계산 전에 예산을 검사하고 실패한 탐색의 부분 성공 설계를
반환하지 않습니다.

```python
import json
from sipi.line_model import TransmissionLineDocument
selected = TransmissionLineDocument.from_dict(report['result']['input'])
assert selected.to_dict()['length_m'] == 0.
assert report['result']['scope'] == 'bounded-single-parameter-common-forward-line-goal'
assert report['result']['history'][-1]['stage'] == 'refinement'
assert report['result']['evaluations'] <= 24
assert report['result']['unit'] == 'ohm'
assert goal.to_dict()['study']['quantity'] == 'z_diff_forward'
json.dumps(report, allow_nan=False)
```

성공 보고는 길이0·50Ω network reference의 원래/세분 line/6 입력을 보존합니다.
이 기준저항은 Zcc를 정의하지 않습니다. 선택 물리 입력을 고정하고 edge/far/grade를
모두 절반으로 줄이며 두 잔차 모두 같은 허용오차를 통과해야 합니다. 외곽 수렴은
별도 caller 검사이고 정규화·유계 탐색 성공이 전역 해의 존재·유일성·제조 수율을
보장하지 않습니다.

비대칭40Ω 조건은 직접 API와 정확한 이력·입력,전체 RLGC/Zc 상대1e-10 및 양쪽
잔차<=.125Ω를 비교합니다. 별도 balanced2N 전신방정식 고유공간으로 선택 Zc/Zcc를
1e-10 안에서 비교하며 제품 Schur 제곱근과 독립입니다. 균일 PEC 쌍의 진공 Zc는
독립 SPD 기하평균으로 구하고 재료 해석식 Zvac/sqrt(eps_r*(1-j*tan_delta))를 씁니다.
eps_r3.7/tan_delta.02 조건은 scaling상대1e-10·유전율오차<=1.5%·양쪽 잔차<=.05Ω를
요구합니다. 계산된 기하를 이용한 재료 항등식이며 실측 기하 정확도가 아닙니다.
앞선 API의 메시·외곽 수락 범위는 그대로입니다.

이전93종 저장 입력은 소스·설치본에서 정확히 유지하고 엄격한 입력·고정 높이·기울어진
재료 보존·기존 단일/차동 등가·공통 예산·원래 실패도 검사합니다. 새 명시 스키마
하나를 더해94스키마/37템플릿이며 새 전체 회귀·실측/full-wave·앱·Windows·배포 수락을
뜻하지 않습니다.
