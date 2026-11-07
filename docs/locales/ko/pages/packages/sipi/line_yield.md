# 유손실 선로 물리량의 iid 수율

[고정 후보 선택 /2](lossy_yield_design.md)는 여러 후보에 동시 신뢰구간을 적용하는 별도 계약입니다.

[English](../../../../../packages/sipi/line_yield.md) · [단일 선로 표본](line_study.md) · [차동 표본](differential_line_study.md) · [준정적 임피던스 수율](yield.md)

`sipi.line-quantity-yield/1`은 고정된 `LineQuantityStudyDocument`(/1 또는 /2)
하나에 경계를 포함하는 수락 조건을 적용합니다. 단위는 원래 물리량을 따릅니다.
Re(Zc)·순방향 Re(Zdd)는 ohm, 단일 선로 감쇠는 Np/m입니다. 완료된 감쇠는
0일 수 있습니다. 기존 준정적 `impedance-yield/1`은 유지합니다. 차동 물리량은
명시적 [Ic=0 순방향 입력](differential_line_goal.md)이며 독립 고유모드나
유한 종단 입력 임피던스가 아닙니다.

원source의 iid uniform·normal 표본만 허용합니다. normal 행 내부의 변수 상관은
허용하지만 행들은 명시된 iid 표본 모델을 따릅니다. sweep/corners를 모집단 수율
실험으로 해석하지 않고 field 전에 거부합니다. 원래 순서·seed·벡터·기하/재료
제약·선로 입력·실패 행을 유지하며 재표본·잘라내기·누락을 하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
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
    sampling=dict(kind='uniform', count=3, seed=123,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
line_study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
    quantity='differential_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
request = LineQuantityYieldDocument(line_study, minimum=95., maximum=105.,
                                    confidence=.95, minimum_yield=.9)
assert normalize_saved(request.dumps()) == request.dumps()
report = execute_saved(request.dumps(), max_evaluations=3)
assert report['status'] == 'complete'
assert report['result']['count'] == 3 and report['result']['unresolved'] == 0
assert report['result']['unit'] == 'ohm'
assert report['result']['goal_status'] == 'undetermined'
assert len(report['result']['rows']) == 3
```

저장 객체 필드는 schema, study, minimum, maximum, confidence, minimum_yield
입니다. 유한한 0 이상 경계가 하나 이상 필요하며 null인 쪽은 제한하지 않습니다.
양쪽 경계가 있으면 minimum <= maximum이고 같은 값도 허용합니다. confidence는
부동소수점 정밀도에서 0과 1 사이여야 합니다. 선택적 minimum_yield는 [0,1]입니다.
알 수 없는/누락 필드·중복 키·비유한 숫자를 거부합니다. caller 전체 표본 예산은
field 전에 검사하며 줄여서 실행하지 않습니다. 이 요청은 설계를 선택하거나
적응적으로 바꾸지 않습니다.

원래 N개 행에서 경계 안 K개, 밖 F개, 미확정 U개이면 N=K+F+U입니다.
잘못된 normal 기하를 포함한 실패는 미확정으로 남기며 숫자나 확정 불량으로
조용히 바꾸지 않습니다. 관측 비율의 범위는 [K/N, (K+U)/N]입니다. 신뢰구간은
가능한 미확정 label 전부에 대한 중앙 equal-tailed exact Clopper–Pearson 구간의
합집합입니다. 하한은 성공 K개, 상한은 성공 K+U개에서 정합니다. 0/전체 성공
끝점은 명시적 수학값이며 수치 추정을 잘라낸 값이 아닙니다. 전부 미확정이면
[0,1]을 반환합니다.

수율 목표는 신뢰 하한이 목표 이상이면 pass, 상한이 목표보다 작으면 fail,
그 외에는 undetermined입니다. 계산이 완료되어도 목표는 실패하거나 미정일 수
있습니다. 미확정 행이 있으면 공통 실행은 `incomplete`이며 모든 행과 구간을
보존합니다. 표본 비율 하나를 신뢰 보장으로 사용하지 않습니다.

```python
from sipi.dielectric import ConstantDielectric

source = ImpedanceStudyDocument('stripline',
    dict(width=.5e-3, plane_spacing=1e-3, eps_r=1., box_width=4e-3),
    quantity='z0', frequency=1e9, materials={'dielectric': ConstantDielectric(4., 0.)},
    mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
    material_variables={'dk': dict(region='dielectric', path=['eps_r'])},
    sampling=dict(kind='uniform', count=3, seed=12,
        variables=[dict(name='dk', lower=3., upper=5.)]))
line_study = LineQuantityStudyDocument(source, conductor=dict(kind='perfect'),
                                       quantity='attenuation')
assessment = LineQuantityYieldDocument(line_study, minimum=0., maximum=0.,
                                       minimum_yield=.9).analyze(max_evaluations=3)
assert assessment.passed == 3 and assessment.unresolved == 0
assert assessment.to_dict()['unit'] == 'Np/m'
assert assessment.goal_status == 'undetermined'
```

기존 study 결과에 `assess_line_yield(study_result, ...)`를 적용하면 field를 다시
계산하지 않습니다. 물리량·변수 이름·전체 count·행 순서·재생한 원표본 벡터와
완료/실패 값·단계의 일관성을 확인합니다. 이 구조 검사는 수동 구성한 결과의
실제 해석 진위를 인증하지 않습니다. `LineYieldAssessment`는 원study와 전체
Python row 결과를 보존합니다. JSON은 각행의 값·단계·오류·가능한 입력 snapshot과
분류를 함께 남깁니다.

구간은 주어진 모델의 유한 iid 표본과 미확정 label을 다룹니다. 수치/메시 오차,
재료 fitting 오차, 제조 분포 자체의 불확실성을 포함하지 않으며 실측 생산 수율이
아닙니다. 표본 범위에서 field·외곽 유효성을 확인하세요. 반복·적응적 후보 선택은
별도의 다중비교 계약이 필요하며 이 고정 study 하나의 구간으로 보장하지 않습니다.

독립 유한 이항합 반전 및 SciPy exact binomial 구간의 끝점 절대 오차 1e−12,
모든 미확정 label 경우·경계/단측 수락·신뢰구간 목표 판정을 검사합니다. 실제
유한 금속 차동 무작위 행을 직접 study와 RLGC/Zc 1e−10, 정확한 벡터·snapshot으로
재생 비교합니다. 단일 선로 0 감쇠와 상관 normal의 잘못된 기하로 단위·미확정
보존을 확인합니다. 공유 criteria 변경에는 기존 수율·고정 후보 선택 회귀도
포함합니다. 관련 검증이며 새 실측 기하·전체 회귀·앱·Windows 수락이 아닙니다.

```sh
python -m pytest -q tests/sipi/test_line_yield.py tests/sipi/test_yield_assessment.py tests/sipi/test_yield_design.py tests/sipi/test_execution.py
```
