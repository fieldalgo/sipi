# 차동 순방향 임피던스 목표 저장

[English](../../../../../packages/sipi/differential_goal_document.md) · [단일 선로 저장 목표](line_goal_document.md) · [순방향 입력 계약](differential_line_goal.md) · [공통 실행](execution.md)

명시적 `sipi.line-quantity-design/2`는 기존 두 단일 선로 물리량에
`differential_forward_impedance_real`을 추가합니다. constructor 기본은 여전히
`/1`이며 이 버전은 차동 물리량을 거부합니다. /2의 단일 선로 요청은 /1과 같은
동작을 합니다. 미래의 물리량 이름을 어느 버전도 암묵적으로 수락하지 않습니다.

차동 물리량은 전체 유손실 Zdd의 실수부[ohm]를 목표로 합니다. Vd=V1−V2,
Id=(I1−I2)/2, 입력 단면 Ic=I1+I2=0입니다. 비대칭 결합과 공통 전압을 유지하며
독립 고유모드, 유한 종단 임피던스, abs(Zdd), 전파 중 Ic=0 유지 보장을 뜻하지
않습니다. [API 정의와 수렴 기준](differential_line_goal.md)을 함께 확인하세요.

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
        air_height=5e-3, box_width=12e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='left_width', lower=.2e-3, upper=1e-3)]))
goal = LineQuantityDesignDocument(source, schema='sipi.line-quantity-design/2',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='differential_forward_impedance_real', target=100.,
    tolerance=.5, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert max(abs(report['result']['residual']), abs(report['result']['refined_residual'])) <= .5
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
assert report['result']['quantity'] == 'differential_forward_impedance_real'
```

최상위 필드는 schema, study, conductor, quantity, target, tolerance,
max_evaluations로 유지됩니다. 차동 물리량의 중첩 study/3 또는 /4는
`z_diff_forward`, 두 신호, 고정 양수 주파수 하나, count=2 sweep, 양수 증가
bounds를 가진 변수 하나를 요구합니다. `z_diff` 모드 source를 조용히 재해석하지
않고 거부합니다. 중첩 `z_diff_forward`는 입력 계약을 지정하며 실제 목표는
실수 준정적 진단 대신 전체 복소 유손실 RLGC를 사용합니다. 선행 study 해석은
실행하지 않습니다.

지원 template의 고정 중심 피치와 전체 plane spacing 제약을 재사용합니다.
/4 source는 재료 모델 숫자 leaf 하나를 연결할 수 있으며 선택 재료가 원래·세분
입력에 모두 남습니다. 도체 법칙은 지원 면별 법칙을 포함하는 고정 strict
line/6 입력입니다. parsing은 메시 없이 source의 endpoint 기하·재료 사전 검사와
nominal 도체 검사를 유지합니다. 이후 후보·도체 실패는 API 시도 횟수에 포함하며
실패 단계와 가능한 입력을 남깁니다.

공통 실행은 field solve 전에 caller 예산을 검사합니다. 성공 보고는 정확한
시도 이력·단위와 길이 0인 원래·세분 line/6 입력을 보존합니다. 50Ω network
reference는 Zdd 정의와 무관합니다. 실패 시 완료 이력과 실패 시도를 남기고
부분 성공 설계를 반환하지 않습니다. 전체 행렬은 Python 결과 또는 저장된
선택 선로의 재실행으로 얻습니다. 1변수 탐색·물리 모델·외곽 수렴의 한계는
API 계약을 유지합니다. 저장 `line-quantity-study/1`은 여전히 단일 신호 전용이며
이 목표 스키마를 차동 공차·수율 스키마로 해석하지 않습니다.

폭·두께·금속이 다른 고정 피치 100Ω 사례에서 직접 API와 정확한 이력·입력,
RLGC/Zc 1e−10 및 양 목표 잔차 0.5Ω를 비교합니다. 균일 PEC 쌍의 복소
임피던스는 Zvac/sqrt(eps_r*(1-j*tan_delta))로 변합니다. 재료 유전율 목표는
이 항등식 1e−10, 유전율 해 1.5%, 양 잔차 0.5Ω를 검사합니다. 계산한 진공
기하 기준을 쓰는 해석적 재료 scaling 검사이며 독립 실측 기하 benchmark가
아닙니다. 고정 높이·기울어진 재료 source 보존·단일 신호 등가·엄격 입력·공통
예산·실패 보존도 검사합니다. 관련 시험을 새 전체 회귀·실측 정확도·앱·Windows
수락으로 해석하지 않습니다.

별도 균형화 전압·전류 전신방정식 고유공간으로 저장된 선택 Zc/Zdd를 1e−10 이내로 검사하며 제품의 Schur 제곱근을 사용하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_differential_goal_document.py tests/sipi/test_line_goal_document.py tests/sipi/test_line_study.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
