# 유손실 단일 선로 목표의 저장과 실행

[English](../../../../../packages/sipi/line_goal_document.md) · [목표 API](line_goal.md) · [Study 입력](study.md)

`sipi.line-quantity-design/1`은 Python callable 없이 제한된 단일 선로 목표를
저장합니다. 기존 study의 template·매개변수·재료 연결·메시·구간을 재사용해
[유손실 목표 API](line_goal.md)를 실행하며 사전 임피던스 study 계산은 하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_goal_document import LineQuantityDesignDocument
from sipi.execution import normalize_saved, execute_saved

mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={}, mesh=mesh,
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
goal = LineQuantityDesignDocument(source,
    conductor=dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='hammerstad', rms_m=.5e-6), ground_thickness=35e-6),
    quantity='impedance_real', target=50., tolerance=.5, max_evaluations=24)
assert normalize_saved(goal.dumps()) == goal.dumps()
report = execute_saved(goal.dumps(), max_evaluations=24)
assert report['status'] == 'complete'
assert abs(report['result']['residual']) <= .5
assert abs(report['result']['refined_residual']) <= .5
assert report['result']['input']['schema'] == 'sipi.transmission-line/6'
```

객체 필드는 정확히 `schema`, `study`, `conductor`, `quantity`, `target`,
`tolerance`, `max_evaluations`입니다. 알 수 없거나 빠진 필드, 중복 JSON 키,
비유한 수를 거부합니다. 목표는 `impedance_real`(Re(Zc), ohm) 또는
`attenuation`(Re(gamma), Np/m)이며 API의 명시적 양수 허용오차를 사용합니다.
abs(Zc)나 유한 선로 삽입손실 목표가 아닙니다.

중첩 study는 버전 3 또는 4, 명시적 양수 고정 material 평가 주파수,
`quantity='z0'`, sweep/count2, 양수의 증가하는 경계를 가진 변수 하나여야 합니다.
중첩 z0는 단일 신호 source 계약을 선택하며 새 목표 계산값이 아닙니다.
기존 study 스키마·뜻을 유지하고 count2는 endpoint를 정할 뿐 목표 평가 횟수가
아닙니다. 통계·corner sampling, 다변수, 차동 모드 목표는 거부합니다. 버전 4는
재료 모델의 숫자 leaf 하나를 연결할 수 있으며 지원하는 단일 신호 적층 template의
전체 기준면 간격 고정 조건도 유지합니다.

고정 conductor는 접지 면별 법칙을 포함하는 엄격한 line/6 record입니다. 후보는
길이 0, 50Ω power-wave reference의 line/6을 사용합니다. 이 reference가
특성 임피던스 목표를 정하지 않으며 평가 주파수는 고정됩니다.

```python
import json
from sipi.dielectric import ConstantDielectric

loss_source = ImpedanceStudyDocument('stripline', dict(width=.5e-3,
    plane_spacing=1e-3, eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
    materials={'dielectric': ConstantDielectric(4., .02)}, mesh=mesh,
    material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='loss', lower=.01, upper=.1)]))
loss_goal = LineQuantityDesignDocument(loss_source, conductor=dict(kind='perfect'),
    quantity='attenuation', target=1., tolerance=.001, max_evaluations=24)
result = LineQuantityDesignDocument.loads(loss_goal.dumps()).solve()
assert max(abs(result.residual), abs(result.refined_residual)) <= .001
assert result.document.to_dict()['materials']['dielectric']['parameters']['tan_delta'] == result.parameter
json.dumps(result.to_dict(), allow_nan=False)
```

읽을 때 메시·study·목표 계산을 실행하지 않습니다. 기존 study의 양 endpoint
기하·재료 사전 검사를 유지하고 nominal 도체 검사를 추가합니다. 그 이후 endpoint의
skin depth나 구간 내부 후보 오류는 factory 시도 횟수에 포함합니다. 입력을 자동
수정하거나 샘플을 버리지 않으며 선택된 기하·재료는 세분할 때 고정합니다.

공통 실행은 저장 예산이 호출자 예산보다 크면 field 전에 거부하고 값을 잘라내지
않습니다. 성공 결과는 값·단위·원래/세분 선로 입력·완료된 모든 평가를 보존합니다.
전체 행렬은 Python 결과 또는 보존된 선로 재생으로 얻습니다. `LineQuantityGoalError`는
failed 상태와 null result, 시도 횟수·단계·실패 매개변수·원인 타입·가능한 후보 입력·
완료 이력을 보존합니다. 잘못된 저장 입력은 예외를 발생시킵니다. 선택 진단은 이 목표가
아닌 최상위 선로 문서에서만 받습니다. 예산은 메모리·시간 상한이 아닙니다.

저장/직접 API의 정확한 이력·입력 일치, RLGC/값 1e−10, 유한 금속의 양 목표 잔차
0.5Ω를 검사합니다. 재료 leaf 감쇠 목표는 양 잔차 0.001Np/m와 해석 tanδ 대비
0.5%를 요구합니다. 독립 scikit-rf Zc/gamma는 동일 RLGC로 상대 오차 1e−10을
요구하며 기존 API field·메시·외곽 검증과 저장 연결 수락을 구분합니다. 실측 fitting,
다중 모드 목표, 전역 최적, 연속 대역, 앱 또는 Windows 수락을 의미하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_line_goal_document.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
