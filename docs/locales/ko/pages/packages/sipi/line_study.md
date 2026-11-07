# 유손실 단일 선로 물리량의 공차 계산

[명시적 /2 차동 공차](differential_line_study.md)는 비대칭 쌍의 순방향 입력 물리량을 추가합니다. 기본 /1과 아래 단일 선로 계약은 유지합니다.

[English](../../../../../packages/sipi/line_study.md) · [Source sampling](study.md) · [유손실 목표](line_goal_document.md)

`LineQuantityStudyDocument`는 기하·재료 표본마다 전체 유손실 R/L/G/C를 추출합니다.
물리량은 `impedance_real`(Re(Zc), ohm) 또는 `attenuation`(Re(gamma), Np/m)입니다.
단일 신호 순방향 진행파 물리량이며 abs(Zc), 유한 선로 삽입손실, 차동 모드 목표와
구별합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.execution import normalize_saved, execute_saved

mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
source = ImpedanceStudyDocument('stripline', dict(width=.5e-3, plane_spacing=1e-3,
    thickness=50e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    quantity='z0', frequency=1e9, materials={}, mesh=mesh,
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.3e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, quantity='impedance_real',
    conductor=dict(kind='surface', conductivity=58e6, relative_permeability=1.,
        roughness=dict(kind='hammerstad', rms_m=.5e-6), ground_thickness=35e-6))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['failed'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['summary']['minimum'] > 0
```

저장 필드는 정확히 `schema='sipi.line-quantity-study/1'`, `study`, `conductor`,
`quantity`입니다. source는 /3 또는 /4, scalar z0 template, 양수 고정 material
평가 주파수 하나여야 합니다. 중첩 z0는 source 계약을 선택하며 유손실 계산값이
아닙니다. source study 자체 분석은 하지 않습니다. 기존 sweep/corners/uniform/
correlated-normal, seed, 숫자 재료 leaf, 전체 기준면 간격 고정 조건을 그대로
재사용하며 여러 기하·재료 변수를 함께 바꿀 수 있습니다.

도체는 명시적인 접지 면을 포함하는 고정된 strict line/6 record입니다. 후보는
길이 0, reference 50Ω의 line/6이며 이 reference가 Zc나 gamma를 정하지 않습니다.
nominal 메시 설정을 재사용하지만 기하마다 다시 메시를 만듭니다. 모든 표본의 수렴을
보장하지 않으므로 실제 범위에서 물리적 유효성과 메시·외곽 수렴을 따로 확인하세요.

```python
import json
from sipi.dielectric import ConstantDielectric

loss_source = ImpedanceStudyDocument('stripline', dict(width=.5e-3,
    plane_spacing=1e-3, eps_r=1., box_width=4e-3), quantity='z0', frequency=1e9,
    materials={'dielectric': ConstantDielectric(4., .02)}, mesh=mesh,
    material_variables={'loss': dict(region='dielectric', path=['tan_delta'])},
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='loss', lower=0., upper=.1)]))
loss_study = LineQuantityStudyDocument(loss_source, conductor=dict(kind='perfect'),
                                      quantity='attenuation')
result = loss_study.analyze(max_evaluations=3)
assert result.failed == 0 and result.rows[0].value == 0
assert result.variable_names == ('loss',) and result.unit == 'Np/m'
assert result.summary['minimum'] == 0
json.dumps(result.to_dict(), allow_nan=False)
```

정규화는 기존 source의 유한 endpoint 기하·재료 사전 검사와 nominal 도체 검사를
메시 없이 수행합니다. Normal 표본은 무한 범위이므로 물리적으로 잘못된 표본도
실패 행으로 남습니다. 잘라내거나 다시 뽑지 않습니다. 표본 생성 overflow는 유한
입력으로 재생 기록을 만들 수 없으므로 field 계산 전에 예외로 전달합니다.

호출자 `max_evaluations`(2~10000 정수, 기본128)는 field 전에 전체 표본 수를
감당해야 합니다. 앞서 실패했어도 생성된 모든 표본을 순서대로 시도합니다. 행은
index, 순서 있는 `sample_values`, 가능한 template 매개변수·실제 표본 재료·정규
선로 입력과 값 또는 오류 타입·메시지·단계를 보존합니다. 벡터 순서는
`variable_names`가 정합니다. 파생 입력을 유한 JSON으로 표현할 수 없으면 해당
snapshot은 null이며 원래 표본과 실패는 남깁니다. 단계는 parameters, materials,
input, extraction, diagnostic, complete입니다. Python 행에는 가능한 전체 선로
결과도 남고 공통 출력은 객체를 빼되 정확한 선로 입력으로 성공한 field를 재생합니다.

공통 실행은 실패 행이 있으면 `incomplete`, summary는 null로 반환하며 모든 행을
보존합니다. 성공한 일부만으로 통계를 만들지 않습니다. 모두 성공하면 최소·최대·
평균·표본 표준편차(ddof=1)·선형 보간 p05/p95를 계산합니다. 비음수 값을 스케일해
불필요한 중간 overflow를 피하고 감쇠 0도 유효합니다. 이는 주어진 표본의 기술통계이며
생산 수율·신뢰구간·분포 보정·최악치 증명이 아닙니다. 입력·표본 예산은 메모리·시간·
메시 복잡도 상한이 아닙니다.

직접 선로 입력/RLGC/값은 1e−10, 균일 PEC 감쇠 표본의 폐형식은 1e−10,
동일 추출 RLGC의 독립 scikit-rf Zc/gamma는 1e−10 이내인지 검사합니다. 독립적인
안정적 통계·수동 percentile 보간과 1e−12 이내 일치해야 하며 0·극단적 유한 수·
subnormal도 포함합니다. 상관 normal 실패·후속 시도·기하/재료 결합 표본·고정 높이·
접지 면을 검사하고 공통 source 생성 분리 후 기존 저장 목표도 재검증합니다.
엔진 계약의 검증이며 실측 제조 정확도·앱·Windows 수락을 뜻하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_line_study.py tests/sipi/test_line_goal_document.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
