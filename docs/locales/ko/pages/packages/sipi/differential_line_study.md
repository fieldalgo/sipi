# 유손실 차동 순방향 임피던스 표본 분석

[유손실 iid 수율](line_yield.md)은 무작위 표본의 미확정 행을 보존한 신뢰구간을 제공합니다.

[English](../../../../../packages/sipi/differential_line_study.md) · [단일 선로 공차](line_study.md) · [순방향 입력](differential_line_goal.md) · [원표본](study.md)

명시적 `sipi.line-quantity-study/2`는 기존 단일 선로 공차 계약에
`differential_forward_impedance_real`을 추가합니다. constructor 기본은 단일 신호
전용 `/1`입니다. /2의 단일 선로 물리량은 기존 동작을 유지하며 미래 물리량
이름을 자동 수락하지 않습니다.

차동 source는 `z_diff_forward`, 순서가 있는 정확히 두 신호, 고정 양수 주파수
하나를 가진 study/3 또는 /4입니다. 모드 `z_diff`를 재해석하지 않고 거부합니다.
각 표본은 전체 유손실 Zc에서 Zdd=[1,-1] Zc [1,-1]^T의 실수부[ohm]를
계산합니다. Id=(I1−I2)/2, 입력 단면 Ic=I1+I2=0 조건이며 공통 전압과 비대칭
결합을 유지합니다. 독립 고유모드·유한 종단 임피던스·절댓값 또는 전파 중
Ic=0 유지 보장을 뜻하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
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
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
    quantity='differential_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
assert normalize_saved(study.dumps()) == study.dumps()
report = execute_saved(study.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['failed'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['summary']['minimum'] > 0
assert all(row['input']['schema'] == 'sipi.transmission-line/6'
           for row in report['result']['rows'])
```

최상위 필드는 schema, study, conductor, quantity입니다. 원래 sweep/corners/
uniform/correlated-normal 표본 벡터·순서·seed·상관을 유지합니다. 여러 기하·재료
숫자 leaf 변수, 고정 피치와 지원되는 전체 stack-height 제약을 재사용합니다.
source의 실수 준정적 study는 실행하지 않습니다. 도체 법칙은 고정 strict
line/6이며 각 표본에 길이 0인 line/6 입력을 만듭니다. 50Ω network reference는
Zdd를 정의하지 않습니다.

bounded source의 endpoint 기하·재료 검사와 nominal 도체 검사를 메시 전에
유지합니다. 무한 범위 normal 표본에는 잘못된 폭·간격·재료가 나올 수 있습니다.
그 행과 원표본·단계·오류·표현 가능한 중간 입력을 남기며 잘라내기·대체·누락을
하지 않습니다. 뒤 표본도 계속 시도합니다. caller 예산은 field 전에 전체 count를
검사합니다. sampling overflow는 재표본 없이 field 전에 오류로 전달합니다.

실패 행이 하나라도 있으면 공통 실행은 `incomplete`, summary=null과 모든 행을
반환합니다. 전부 성공한 집합만 최소·최대·평균·표본 표준편차(ddof=1)·선형
p05/p95를 계산합니다. 유한 표본의 기술통계이며 수율 신뢰구간·최악치 경계·
생산 수락을 의미하지 않습니다. 메시 설정을 재사용하지만 각 기하를 다시
메시하므로 모든 표본의 수렴이 자동 확보되지는 않습니다. 범위 전체에서 메시·
외곽 유효성을 확인하세요. 전체 행렬은 Python row 결과 또는 저장 선로의
재해석으로 얻습니다.

실제 비대칭 유한 금속 표본의 직접 RLGC/Zc/ReZdd 비교 1e−10과 독립 균형화
전압·전류 순방향 고유공간 비교 1e−10을 요구합니다. 균일 PEC 유전율/손실
corner는 계산한 진공 기하 기준을 사용한 Zvac/sqrt(eps_r*(1-j*tan_delta))
관계를 1e−10으로 검사합니다. 독립 기술통계는 1e−12를 요구합니다. 상관 normal의
잘못된 폭·간격은 원래 위치에 남고 뒤의 유효 행도 보존됩니다. 고정 높이·단일
선로 /2 등가·identity/진단 실패·스키마·예산 검사도 수행합니다. 관련 시험을
새 실측 기하 정확도·전체 회귀·앱 지원·Windows 수락으로 해석하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_differential_line_study.py tests/sipi/test_line_study.py tests/sipi/test_execution.py tests/sipi/test_material_variables.py
```
