# 유한 주파수 격자에서의 형상전류 제조 표본

[English](../../../../../packages/sipi/shape_sampled_panel_pair_study.md) ·
[단일 주파수 표본](shape_panel_pair_study.md) · [기존 주파수 표본 계약](sampled_panel_pair_study.md)

`ShapeSampledPanelForwardPairStudyDocument`는 정전용량 형상미분 전류를 명시적으로
사용하며 하나의 제조 기하·재료 표본을 전체 주파수 격자에서 유지합니다. 엄격한
`sipi.shape-sampled-panel-forward-pair-study/1` 키는 `schema`, `study`,
`step_fraction`입니다. 내부 sampled-panel study/1 또는 /2의 벌크·고정 코팅
경계 선택을 보존하고 기존 스키마의 방식은 바꾸지 않습니다.

주파수는 엄격하게 증가하는 양의 값 2..64개이고 첫 값은 원래 재료 평가
주파수와 같아야 합니다. 상관·표본 순서·중복·고정 피치·재료 변수는 유지합니다.
기하당 하나의 전류 풀이 묶음을 주파수 전체에 재사용하지만 유전체와 금속 법칙은
각 주파수에서 평가합니다. RLGC가 주파수에 무관하거나 차동·공통 여기가 독립
모드라고 가정하지 않습니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.shape_sampled_panel_pair_study import ShapeSampledPanelForwardPairStudyDocument
from sipi.execution_request import SavedExecutionRequest

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.5e-3, gap=.3e-3, substrate_height=.2e-3, eps_r=1.,
         thickness=35e-6, air_height=3e-3, box_width=8e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='sweep', count=3,
        variables=[dict(name='width', lower=.45e-3, upper=.55e-3)]))
panel = SampledPanelForwardPairStudyDocument(source, conductor={'kind':'perfect'},
    frequencies=[1e9, 2e9, 4e9], panels_per_edge=16,
    ground_modes=512, interpolation_degree=16)
document = ShapeSampledPanelForwardPairStudyDocument(panel, step_fraction=1e-3)
request = SavedExecutionRequest(document.dumps(), max_evaluations=3)
assert ShapeSampledPanelForwardPairStudyDocument.loads(document.dumps()).dumps() == document.dumps()
# receipt = request.run()  # Three manufactured rows, each with all three frequencies.
```

예산은 제조 행 하나당 선로 전체 주파수 추출 한 번을 셉니다. 주파수별 결과를
독립 제조 표본으로 세거나 내부 패널 풀이 횟수와 혼동하지 않습니다. 전체 행 수가
정수 2..10000인 예산 안에 있어야 전계를 풉니다. 메시·패널·상대 이동폭 제어는
고정하며 주파수 사이의 보간 정확도나 자동 수치 인증을 뜻하지 않습니다.

명목 기하와 전체 격자의 재료 유효성은 전계 없이 검사합니다. 잘못된 표본 기하·
재료·이동 경계나 추출·진단 실패는 행 단위 실패로 보존합니다. 한 주파수의 실패도
그 행 전체를 무효화하지만 후속 행은 계속 계산합니다. 행이나 주파수 항을 조용히
버리지 않습니다. 모든 행이 완료해야 주파수별 기술통계를 제공합니다. 진단 실패
전까지 얻은 전체 전류 기록도 유지하고 형상 선로 오류의 단계별 부분 근거는
`cause_details`에 보존합니다.

공통 실행은 완료·미완료 결과, 정확한 입력과 모든 행을 보존하며 기록·프로젝트
복원은 전계를 다시 풀지 않습니다. 기존 단일 주파수·쌍 수율 스키마가 이 격자나
방식을 암묵적으로 선택하지 않습니다. 유한 격자로 주파수 사이 극값, 연속 대역
조건 만족, 생산 수율이나 실측 재료 정확도를 보장하지 않습니다.

## 검증 범위

독립 모달 격자·통계, 중복·상관, 고정 피치·재료 변수, 행 단위 실패, 이동 경계,
예산·엄격한 JSON·기록을 기존 주파수 표본·수율 소비자와 함께 검사합니다.
벌크·코팅 금속의 실제 모서리 조합 각 4개를 1/2/4 GHz에서 계산하고 균일 스칼라
Debye 법칙의 독립 유전율로 복소 C·G를 대조합니다. 외부 LC, 금속 전달식과
4포트 네트워크도 독립 기준과 비교합니다. 각 금속의 선택한 행 하나는 세 주파수를
각각 따로 풀어 대조합니다. 유전체 메타데이터·주파수 격자에 따라 전류 기록이
달라지지 않는지도 확인합니다.

이 유한 영역 사례에는 단일 주파수 표본 문서의 작은 영역 한계가 그대로 있습니다.
재료·네트워크 불변식과 전송 검증이 원래 외곽·작은 상호항·절대 정확도를 인증하지
않습니다.
