# 공통 전류 물리량의 iid 합격 확률 구간

[English](../../../../../packages/sipi/common_forward_line_yield.md) | **한국어**

명시적 `sipi.line-quantity-yield/2`는 고정된 확률 표본 요청인
`sipi.line-quantity-study/3`와 `common_forward_impedance_real`을 지원합니다.
직접 API `assess_line_yield`도 이 study 버전을 받습니다. 저장 생성자의
기본값 `/1`은 study `/1`·`/2`만 받습니다. 고정 후보 선택 `/2`도 이전
입력 범위를 유지합니다.

물리량은 Vc=(V1+V2)/2, Ic=I1+I2, 입력 Id=(I1-I2)/2=0에서 정의하는
Re(Zcc)[ohm]입니다. 비대칭 결합을 유지하며 선로 전체의 Id=0이나 독립
공통 고유모드를 가정하지 않습니다. 기하·재료·고정 pitch·메시·도체
조건은 [공차 계약](common_forward_line_study.md)을 따릅니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.line_yield import LineQuantityYieldDocument
from sipi.execution import normalize_saved, execute_saved

def metal(conductivity, rms):
    return dict(conductivity=conductivity, relative_permeability=1.,
                roughness=dict(kind='hammerstad', rms_m=rms))

source = ImpedanceStudyDocument('asymmetric_coupled_microstrip',
    dict(left_width=.6e-3, right_width=.5e-3, gap=.4e-3,
        substrate_height=.5e-3, eps_r=4., tan_delta=.02,
        left_thickness=35e-6, right_thickness=50e-6,
        air_height=10e-3, box_width=24e-3),
    quantity='z_diff_forward', frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='uniform', count=4, seed=17,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
study = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
    quantity='common_forward_impedance_real',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6))
doc = LineQuantityYieldDocument(study, schema='sipi.line-quantity-yield/2',
    minimum=38., maximum=41., confidence=.95, minimum_yield=.5)
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=4)
assert result.passed == 4 and result.failed == result.unresolved == 0
assert [row.index for row in result.study.rows] == list(range(4))
assert result.goal_status == 'undetermined'
```

루트 키는 `schema`, `study`, `minimum`, `maximum`, `confidence`,
`minimum_yield` 여섯 개입니다. 합격 범위는 양 끝을 포함합니다.
uniform·상관 normal의 각 행을 명시된 분포의 iid 표본으로 취급하며
한 행 안의 변수 간 상관은 허용합니다. sweep·corners는 이 신뢰구간
계산에서 거부합니다. 제조 데이터에서 분포를 자동 추정하지 않습니다.

원래 행 전체·순서·다시 생성한 정확한 표본 벡터를 확인합니다. 실패 행은
미확정으로 남고 분모에 포함됩니다. 계획 n행 중 p행 합격, u행 미확정이면
관측 비율 범위는 [p/n, (p+u)/n]입니다. 신뢰구간은 p개 성공일 때의
Clopper–Pearson 하한과 p+u개 성공일 때의 상한을 사용하여 미확정 분류의
모든 가능성을 포함합니다. 행을 버리거나 다시 추출하지 않습니다.
이 구조 검사는 외부에서 임의 작성한 솔버 결과의 진위를 보증하지 않습니다.

```python
import json
import numpy as np
np.testing.assert_allclose(result.confidence_interval, [.025**(1/4), 1.], rtol=0., atol=1e-12)
assert result.sample_fraction_bounds == (1., 1.)
report = execute_saved(doc.dumps(), max_evaluations=4)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['unit'] == 'ohm'
assert report['result']['quantity'] == 'common_forward_impedance_real'
assert report['result']['scope'] == 'iid-stated-distribution-not-measured-production-yield'
json.dumps(report, allow_nan=False)
```

이 예제의 네 표본은 모두 합격하지만, 네 관측만으로 95% 신뢰수준에서
모집단 합격률 50%를 인증할 수 없습니다. 따라서 분석이 정상 완료되어도
목표 상태는 미확정일 수 있습니다. 실측 생산 수율을 뜻하지 않으며 메시·
재료 적합·모델·분포 오차는 구간에 포함하지 않습니다. 표본 예산 초과는
field 계산 전에 거부하지만, 메모리나 실행 시간을 제한하는 예산은 아닙니다.

독립 유한 이항합 역산과 구간 끝점을 1e-12 이내로 비교하며 전부 성공·
전부 실패와 미확정 분류의 모든 경우를 포함합니다. 실제 공통 전류 표본은
저장/직접 계산의 전체 RLGC를 1e-10 이내, 보고서를 정확히 재생합니다.
상관 normal의 잘못된 기하 3행을 8행 중 미확정으로 보존하고 뒤 행도
계속 계산합니다. 행번호·순서·벡터·실패·엄격 입력·예산 불변식을 확인합니다.

수치 추출과 확률 수식은 재사용합니다. 이전 scalar·차동 보고서와 저장
입력 95종의 정규형을 보존합니다. 소스·정확한 설치 휠 및 영한 예제를
검증합니다. 앞선 세 폭의 메시·유한 외곽 검증은 그 조건에 한정되며,
이번 통계 연결이 모든 확률 표본의 수렴·실측 정확도·새 플랫폼·배포를
추가로 검증한 것은 아닙니다.
