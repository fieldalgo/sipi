# 유손실 선로 고정 후보의 동시 수율 구간

[English](../../../../../packages/sipi/lossy_yield_design.md) · [단일 study 수율](line_yield.md) · [기존 선택 계약](yield_design.md) · [공통 실행](execution.md)

명시적 `sipi.yield-design/2`는 기존 고정 후보 선택 규칙을
`line-quantity-study/1` 또는 `/2` 입력에 적용합니다. constructor 기본은 여전히
준정적 impedance study를 받는 `/1`이며 출력 형태도 유지합니다. /2 후보들은
명시적 유손실 물리량과 양수 주파수가 모두 같아야 합니다. Re(Zc)/순방향
Re(Zdd)는 ohm, 단일 선로 감쇠는 Np/m이며 감쇠 0도 허용합니다. 물리량 또는
주파수를 섞으면 field 전에 거부합니다.

각 후보의 필드는 name, cost, study입니다. 이름은 고유하고 비용은 유한한
0 이상이며 cost_unit은 caller가 명시한 공통 단위입니다. 1~32 후보와 각 iid
uniform/normal 분포를 어떤 표본도 평가하기 전에 고정합니다. 기하 목적함수·
적응 탐색·비용 모델을 추정하지 않습니다. 원source의 pitch·height·재료·도체·
순방향 입력 정의는 유지합니다. 다음 예제의 넓은 한계와 낮은 수율 목표 0.1은
후보당 두 표본으로 저장/실행을 보여주기 위한 값이며 제조 수락 권장값이 아닙니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved, execute_saved

def metal(sigma, rms):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

def candidate_study(lower, upper):
    nominal = (lower+upper)/2
    source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
        dict(left_width=nominal, right_width=.5e-3, gap=.95e-3-(nominal+.5e-3)/2,
            substrate_height=.5e-3, eps_r=4., tan_delta=.02,
            left_thickness=35e-6, right_thickness=50e-6, air_height=5e-3, box_width=12e-3),
        quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
        mesh=dict(edge_size=2.5e-6, far_size=.125e-3, grade=.075),
        sampling=dict(kind='uniform', count=2, seed=123,
            variables=[dict(name='left_width', lower=lower, upper=upper)]))
    return LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/2',
        quantity='differential_forward_impedance_real',
        conductor=dict(kind='surface-boundaries',
            conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
            reference=metal(58e6, 0.), ground_thickness=35e-6)).to_dict()

request = YieldDesignDocument([
    dict(name='narrow', cost=2., study=candidate_study(.6e-3, .7e-3)),
    dict(name='wide', cost=1., study=candidate_study(.7e-3, .8e-3))],
    schema='sipi.yield-design/2', cost_unit='relative cost',
    minimum=1., maximum=1000., confidence=.9, minimum_yield=.1)
assert normalize_saved(request.dumps()) == request.dumps()
report = execute_saved(request.dumps(), max_evaluations=4)
assert report['status'] == 'complete'
assert report['result']['status'] == 'selected'
assert report['result']['selected'] == dict(index=1, name='wide', cost=1.)
assert report['result']['unit'] == 'ohm' and report['result']['evaluations'] == 4
assert len(report['result']['candidates']) == 2
```

모든 후보의 전체 표본 수가 caller 예산 안에 있어야 첫 field solve를 시작합니다.
유효한 표본 벡터를 생성한 모든 후보를 평가하고 각 source study와 assessment를
보존합니다. field 실패는 [line-yield 계약](line_yield.md)의 미확정 행이 됩니다.
overflow 등 표본 생성 오류는 재표본하거나 부분 선택 결과를 반환하지 않고
오류로 전달합니다.

고정 후보 m개와 전체 신뢰도 c에 대해 후보별 신뢰도를 1−(1−c)/m 이상으로
배분합니다. 필요한 경우 binary64를 더 높은 신뢰도 쪽으로 반올림해 저장한
값의 정확한 유리수 계산에서도 m*(1−candidate_confidence) <= 1−c를 유지합니다.
표현할 수 없는 배분은 거부하며 신뢰도를 낮추지 않습니다. 각 후보는 배분된
수준의 exact binomial 미확정 envelope를 사용합니다. 후보끼리 독립일 필요가
없어 같은 seed도 허용하지만 각 후보 내부의 iid 가정은 필요합니다. 고정 집합의
Bonferroni 동시 구간이며 적응적·연속 최적화 보장은 아닙니다.

신뢰 하한이 minimum_yield 이상인 후보 중 caller 비용이 가장 낮은 후보를
선택하고, 동률이면 원래 입력 순서를 따릅니다. `selected`는 인증된 구성원이
있음을 뜻합니다. `none-certified`는 모든 후보의 상한이 목표보다 낮은 경우이며
그 외는 `undetermined`입니다. 더 싼 미확정 후보가 실제로 가능할 수도 있으므로
전체 assessment를 남기고 선택 후보를 물리적·전역 최적의 증명으로 다루지 않습니다.

공통 실행은 미확정 행이 하나라도 있으면 후보가 선택되어도 별도로 `incomplete`를
반환합니다. 모든 후보·행·단위·정확한 source 입력을 보존합니다. /2 선택 보고에는
물리량 단위가 포함되며 /1 출력은 유지합니다. 신뢰구간은 명시한 표본 모델과
미확정 label을 다루며 field/메시/재료 fitting/제조 분포 오차를 포함하지 않습니다.
후보 선택으로 실측 생산 수율이나 물리 정확도를 확립하지 않습니다.

후보 1~32개의 전체 실패확률 예산을 정확한 Fraction으로 검사하고 후보별 구간을
독립 유한 이항합 반전과 끝점 절대 오차 1e−12 이내로 비교합니다. 더 싼 미확정
후보·동률·전부 탈락/미정·단일 선로 0 감쇠·같은 normal seed·complete/incomplete
구분·field 전 전체 예산을 검사합니다. 실제 유한 금속 차동 후보는 개별 assessment와
정확한 행/source 및 RLGC/Zc 1e−10으로 재생 비교합니다. 기존 선택·line-yield 회귀도
포함합니다. 관련 검증이며 새 전체 회귀·앱·Windows 수락이 아닙니다.

```sh
python -m pytest -q tests/sipi/test_lossy_yield_design.py tests/sipi/test_yield_design.py tests/sipi/test_line_yield.py tests/sipi/test_execution.py
```
