# 고정 도금 후보의 수율 기반 선택

명시적 `sipi.yield-design/4`는 고정 도금 재료의 study/4 계약을 허용합니다.
모든 후보, 같은 단위의 비용, 각 분포를 계산 전에 지정합니다. 기존 동시 신뢰구간
방식과 선택 규칙은 유지하며, 이전 선택 버전은 기존에 허용한 study 버전을 유지합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.line_study import LineQuantityStudyDocument
from sipi.yield_design import YieldDesignDocument
from sipi.execution import normalize_saved

metal = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.)])
candidates = []
for name, cost, low, high in [('first', 2., .45e-3, .55e-3),
                               ('second', 1., .5e-3, .6e-3)]:
    source = ImpedanceStudyDocument('stripline',
        dict(width=.5e-3, plane_spacing=1e-3, thickness=50e-6,
             eps_r=4., tan_delta=.02, box_width=4e-3),
        quantity='z0', frequency=1e9, materials={},
        sampling=dict(kind='uniform', count=4, seed=123,
            variables=[dict(name='width', lower=low, upper=high)]))
    study = LineQuantityStudyDocument(source, quantity='impedance_real',
        conductor=dict(kind='surface-boundaries', conductors={'signal': metal},
                       reference=metal, ground_thickness=35e-6),
        schema='sipi.line-quantity-study/4')
    candidates.append(dict(name=name, cost=cost, study=study.to_dict()))
design = YieldDesignDocument(candidates, cost_unit='relative',
    minimum=40., maximum=60., minimum_yield=.9, confidence=.95,
    schema='sipi.yield-design/4')
assert normalize_saved(design.dumps()) == design.dumps()
```

`design.analyze(max_evaluations=8)`은 예제의 총 여덟 표본을 시도합니다. 후보당
네 표본은 작은 예시이며 요청 수율을 인증하기에 충분하다고 가정하지 않습니다.
전체 표본 예산은 첫 장 해석 전에 검사합니다. 후보의 목표량과 양의 주파수는 같아야
합니다. 각 후보 안에서는 도금 파라미터가 고정되지만 후보끼리는 재료가 달라도 됩니다.

미해결 표본도 원래 행과 분모에 남습니다. 다른 후보가 통과해도 더 저렴한 미해결
후보를 지우지 않습니다. 인증된 후보 중 최저 비용을 선택하고 비용이 같으면 입력
순서를 따릅니다. 미해결 후보까지 포함한 모든 가능한 해보다 저렴하다는 뜻은 아닙니다.
공통 실행은 선택 상태가 `selected`여도 표본 실패가 남아 있으면 `incomplete`로 보고합니다.

Bonferroni 보정 Clopper–Pearson 구간은 지정된 iid 표본 가정 아래 고정 후보군의
동시 범위를 다룹니다. 후보끼리의 독립성은 필요하지 않습니다. 장 이산화, 입력 분포의
불확실성, 모델 오차는 이 구간에 포함되지 않습니다. 연속·전역 최적화, 실측 제조 수율,
자동 도금 피팅이 아니라 유한 후보 열거입니다.

단일 임피던스·감쇠와 쌍 신호 차동·공통 목표에서 실제 표피/코어 실패를 보존하고,
직접 평가 및 독립 유한 이항합 구간과 대조하며 기존 후보 순서와 단위를 검사합니다.
[도금 모델 한계](layered_metal.md)와 별도 메시·외곽 검증은 계속 적용됩니다.

[English](../../../../../packages/sipi/layered_selection.md)
