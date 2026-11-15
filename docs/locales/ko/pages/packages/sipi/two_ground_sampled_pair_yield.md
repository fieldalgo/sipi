# 두 접지면의 여러 주파수 공동 합격 평가

[English](../../../../../packages/sipi/two_ground_sampled_pair_yield.md)

`TwoGroundSampledForwardPairYieldDocument`는
`sipi.two-ground-sampled-forward-pair-yield/1` 입력을 저장합니다.
[두 접지면 제조 표본](two_ground_sampled_pair_study.md)의 같은 기하·재료 표본이
모든 지정 주파수에서 차동·공통 실수 순방향 임피던스 한계를 함께 만족하는지
검사합니다. 제조 표본 하나가 시행 하나입니다. 주파수를 늘려도 표본 수는
늘어나지 않으며 각 주파수의 합격 비율을 곱해 공동 확률을 구하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00038, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, tan_delta=.003, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9, materials={},
    sampling=dict(kind='uniform', count=4, seed=17, variables=[
        dict(name='width', lower=.00043, upper=.00044),
        dict(name='gap', lower=.00028, upper=.00030)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundSampledForwardPairStudyDocument(source, frequencies=[2e9,3.5e9,5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 4

from sipi.two_ground_sampled_pair_yield import TwoGroundSampledForwardPairYieldDocument
acceptance = dict(
    differential_forward_impedance_real=dict(minimum=[89.]*3, maximum=[91.]*3),
    common_forward_impedance_real=dict(minimum=[44.]*3, maximum=[46.]*3))
assessment = TwoGroundSampledForwardPairYieldDocument(study, acceptance=acceptance,
                                             confidence=.95, minimum_yield=.8)
assert TwoGroundSampledForwardPairYieldDocument.loads(assessment.dumps()).dumps() == assessment.dumps()
```

준비·정규화는 장 계산을 하지 않습니다. `assessment.analyze(max_evaluations=4)`는
네 제조 표본 각각에서 세 주파수를 계산합니다. 주파수는 증가하는 양수 2~64개이며,
각 물리량의 최소·최대 배열 길이가 주파수 수와 같아야 합니다. 모든 위치에는
최소한 한 유한 경계가 필요하며 경계값을 포함합니다. 단일 값의 자동 확장이나
주파수 보간은 하지 않습니다. 네 표본은 계약 예시이며 생산 수율 추정에 충분한
표본 수를 뜻하지 않습니다.

명시된 분포에서 독립·동일하게 뽑는 seeded uniform/normal만 허용하며 한 표본 안의
변수 상관은 허용합니다. corner/sweep은 거부합니다. 주파수 묶음 하나라도 계산에
실패하면 그 제조 표본은 미확정으로 남고 원래 분모에서 빼지 않습니다. 기존의
정확 Clopper–Pearson 미확정 구간은 알 수 없는 표본의 모든 합격/불합격 배치를
포함합니다. 전부 미확정이면 [0,1]입니다. 요청 최소 확률보다 하한이 높거나 같을
때만 합격, 상한이 낮을 때 불합격이며 그 외는 판정 보류입니다.

`assess_two_ground_sampled_pair_yield(result, acceptance=..., confidence=.95)`는
기존 결과를 장 계산 없이 평가합니다. 원 study·주파수 순서·표본·전류/메시 관측·
유형 있는 실패를 보존합니다. 원 계획 표본과 완료/실패 구조를 검사하지만 수동으로
조작한 장 계산 결과의 진위를 인증하지는 않습니다. 다른 전류 방법이나 기하로
바꾸지 않습니다. 미확정이 있으면 공통 실행은 incomplete이며 기록·프로젝트에도
모든 행을 유지합니다. 사용자 중단은 실패 표본으로 바꾸지 않고 전파합니다.

구간은 명시된 모델의 표본 불확실성만 다룹니다. 수치 오차·주파수 사이의 거동·
분포 오류·결과를 보고 고른 합격 조건·실측 생산 수율은 포함하지 않습니다.
정확도와 패널/체적/외곽 수렴은 별도 조건입니다. 원 study의 물리 검증을 참조하며
이 통계 연결로 새 수렴을 주장하지 않습니다. 독립 이항 꼬리 역산, 모든 미확정
배치, 서로 다른 주파수에서 실패하는 표본, 기존 사건 검사의 보존, 엄격한 저장
입력·실행·기록·프로젝트 복원, 2/3.5/5 GHz Debye 모델 네 표본을 검사합니다.
소스와 정확한 설치 산출물을 별도로 검증하며 Linux 근거를 다른 플랫폼으로
확대하지 않습니다.
