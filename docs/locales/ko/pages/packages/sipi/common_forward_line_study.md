# 공통 전류 순방향 임피던스 표본 분석

[English](../../../../../packages/sipi/common_forward_line_study.md) | **한국어**

명시적 `sipi.line-quantity-study/3`는 sweep·corners·uniform·상관normal에서
`common_forward_impedance_real`을 추가하고 기존 단일 신호·차동 물리량도 유지합니다.
생성자 기본은 `/1`이며 v1·v2는 공통 전류 물리량을 계속 거부합니다.

각 값은 고정 양의 주파수 하나에서 전체 유손실 비대칭 RLGC로 구하는 Re(Zcc)[ohm]입니다.
Vc=(V1+V2)/2,Ic=I1+I2,입력면 Id=(I1-I2)/2=0에서 Vc=Zcc Ic이며 차동 전압은
0이 아닐 수 있습니다. 하류 Id=0·독립 고유모드·abs(Zcc)를 가정하지 않습니다.
[순방향 계약](common_forward_line_goal.md)과 [저장 목표](common_forward_goal_document.md)를 참고하세요.

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
        air_height=10e-3, box_width=24e-3), quantity='z_diff_forward',
    frequency=1e9, materials={}, fixed_pitch_m=.95e-3,
    mesh=dict(edge_size=2.5e-6, far_size=.25e-3, grade=.075),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='left_width', lower=.6e-3, upper=.8e-3)]))
doc = LineQuantityStudyDocument(source, schema='sipi.line-quantity-study/3',
    conductor=dict(kind='surface-boundaries',
        conductors={'positive': metal(58e6, .5e-6), 'negative': metal(35e6, 1e-6)},
        reference=metal(58e6, 0.), ground_thickness=35e-6),
    quantity='common_forward_impedance_real')
assert normalize_saved(doc.dumps()) == doc.dumps()
result = doc.analyze(max_evaluations=3)
assert result.failed == 0 and len(result.rows) == 3
assert result.unit == 'ohm' and result.variable_names == ('left_width',)
assert all(row.value > 0 and row.phase == 'complete' for row in result.rows)
```

최상위4키는 schema,study,conductor,quantity입니다. 중첩 study/3 또는/4의
`z_diff_forward`는 두 신호의 기하·재료 입력 계약만 선택하며 해당 준정적 study를
해석하지 않습니다. 지원하는 고정 피치·전체 적층 높이·재료 숫자 leaf와 고정 line/6
도체 법칙을 재사용합니다. 각 표본은 길이0·기준저항50Ω의 line/6 입력이 되며
이 기준저항은 Zcc를 정의하지 않습니다.

nominal의 결정된 메시 설정을 재사용하지만 같은 물리 메시를 재사용하지는 않습니다.
생성한 모든 표본을 순서대로 시도하며 기하·재료·입력·장·진단 실패는 원래 표본과
단계·가능한 중간 입력을 보존합니다. 이후 표본도 계속 계산합니다. 잘라내기·재추출·
실패 행 제거는 없고 실패가 하나라도 있으면 전체 요약을 반환하지 않습니다.
표본 생성 오류·계산 개수 예산 초과는 장 계산 전에 거부합니다. 표본 개수 예산은
메모리나 실행 시간의 상한이 아닙니다.

```python
import json
import statistics
import numpy as np
values = [row.value for row in result.rows]
np.testing.assert_allclose(result.summary['mean'], statistics.mean(values), rtol=1e-12)
np.testing.assert_allclose(result.summary['sample_std'], statistics.stdev(values), rtol=1e-12)
for row in result.rows:
    mixed = row.result.characteristic().mixed_mode().z_characteristic[0]
    np.testing.assert_allclose(row.value, mixed[1, 1].real, rtol=1e-10)
    assert abs(mixed[0, 1]) > 1e-3
report = execute_saved(doc.dumps(), max_evaluations=3)
assert report['status'] == 'complete' and report['result'] == result.to_dict()
assert report['result']['scope'] == 'stated-samples-descriptive-not-production-yield'
json.dumps(report, allow_nan=False)
```

통계는 기술 통계로 평균·표본 표준편차(ddof1)·선형 보간5/95백분위입니다. 신뢰구간이나
실측 제조 수율이 아닙니다. normal의 행 내부 상관을 유지하며 제조 데이터로부터
분포 가정을 자동 추정하지 않습니다. 직접 수율 평가 API와 명시적 [저장 yield /2](common_forward_line_yield.md)는
별도 iid 추론 계약으로 study /3도 지원합니다. 저장 yield /1과 고정 후보
선택 /2는 study /1·/2만 받습니다.

폭.6/.7/.8mm 각각 직접 선로 재생·독립 balanced2N 전신방정식 고유공간을1e-10 안에서,
독립 통계를1e-12 안에서 비교합니다. 각 표본의 edge/far/grade를 모두 절반으로 줄여
원래/세분 상대 변화<=.005를 요구합니다. 고정 세분 설정에서 box/air를24/10mm→
36/15mm→48/20mm로 늘려 각 세분 기준 대비 상대 변화<=.005와 연속 절대 변화
감소를 요구합니다. 유한 영역 검증이며 무한 외곽 오차 상한이나 모든 표본 입력의
보장은 아닙니다. 일반 표본 분석이 매 행을 자동 세분하지도 않습니다.

균일 PEC 쌍은 독립 SPD 진공 기하평균과 Zvac/sqrt(eps_r*(1-j*tan_delta))로
유전율3/5×손실0/.04의4개 재료 corner를1e-10 안에서 검사하고 정확한 재료 입력을
보존합니다. seed를 고정한 상관normal8표본에서는 잘못된3행을 보존하고 나머지도
계속 계산합니다. 엄격 제어·identity·원래 실패·이전 버전 등가·기존94종 정규 입력을
소스와 설치본에서 검사합니다. ENKO 예제와95스키마/37템플릿을 유지합니다.
수치 추출·통계 수식은 그대로이며 실측/full-wave 정확도·앱/플랫폼·배포 수락을
새로 주장하지 않습니다.
