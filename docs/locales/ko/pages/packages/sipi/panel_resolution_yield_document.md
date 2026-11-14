# 수치 해상도 간 수락 비교 저장

`PanelResolutionYieldDocument`는 명시적인
`sipi.panel-resolution-yield/1` 요청을 저장합니다. 키는 `schema`, `studies`,
`acceptance`, `confidence`, `minimum_yield` 다섯 개입니다. 버전·전류 방법,
물리 입력, IID uniform·normal 표본 규칙이 같은 쌍 study 2~8개를 지정합니다.
체적 메시와 패널 설정만 달라질 수 있으며 중복 설정, 외곽 상자 변경,
seed나 표본 순서 변경은 거부합니다.

[직접 유한 해상도 비교](panel_resolution_yield.md)의 의미를 유지합니다.
모두 합격이면 합격, 모두 불합격이면 불합격, 라벨이 다르거나 원래 실패 행이
있으면 미확정입니다. 연속해나 공통 체계적 오류의 상한을 추정하지 않습니다.
코팅 study는 명시적인 버전 2를 사용하며 기존 버전과 명목 수율 결과는 그대로입니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.panel_pair_study import PanelForwardPairStudyDocument
from sipi.panel_resolution_yield_document import PanelResolutionYieldDocument
from sipi.execution import execute_saved, normalize_saved

source = ImpedanceStudyDocument('coupled_microstrip',
    dict(width=.3e-3, gap=.2e-3, substrate_height=.5e-3, eps_r=4.,
         thickness=35e-6, box_width=6e-3, air_height=2e-3),
    quantity='z_diff_forward', frequency=1e9, materials={},
    mesh=dict(edge_size=10e-6, far_size=.2e-3, grade=.1),
    sampling=dict(kind='uniform', count=2, seed=3, variables=[
        dict(name='width', lower=.28e-3, upper=.32e-3)]))
base = PanelForwardPairStudyDocument(source, conductor={'kind': 'perfect'})
fine = base.to_dict()
for key in ('edge_size', 'far_size', 'grade'):
    fine['study']['mesh'][key] /= 2
fine['panel']['panels_per_edge'] *= 2
request = PanelResolutionYieldDocument(
    [base, PanelForwardPairStudyDocument.from_dict(fine)], acceptance={
    'differential_forward_impedance_real': dict(minimum=90., maximum=130.),
    'common_forward_impedance_real': dict(minimum=20., maximum=60.)},
    confidence=.95, minimum_yield=.9)
assert request.required_evaluations == 4
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output['status'] in ('complete', 'incomplete') and output['error'] is None
assert output['result']['count'] == 2 and output['result']['resolution_count'] == 2
```

`required_evaluations`는 표본 수×해상도 수이며 전체 계획은 선로 행 시도
10000회 이하여야 합니다. 분석과 공통 실행은 호출 예산이 부족하면 전계를
풀기 전에 거부합니다. 실패 행도 계획된 자리를 차지합니다. 내부 전계 풀이 수,
메모리나 시간의 한계는 아닙니다. 공통 표본 생성의 실패를 첫 전계 전에 확인하고,
각 source는 원래 행 순서와 실패 처리를 유지합니다. KeyboardInterrupt는 전파합니다.

`studies`는 새 문서 스냅샷을 반환하고 `dumps`/`loads`는 정확한 요청을 보존합니다.
파싱은 전계 계산 없이 추가 키·중복 JSON 키·비유한 수·암묵적인 전류 방법 변환을
거부합니다. 여기서는 공통 실행의 특성·모드 diagnostic 덮어쓰기를 허용하지 않습니다.

미확정 표본이 하나라도 있으면 공통 결과의 `status`는 `incomplete`이고 전체
비교 결과는 `result`에 남습니다. 개별 오류가 원래 행에 보존되므로 `error`는 null입니다.
계획한 모든 행을 시도했어도 분류는 미확정일 수 있습니다. 미확정 행이 없으면
status는 `complete`지만 신뢰 구간이 넓어 `goal_status`가 `undetermined`일 수 있습니다.
계산 상태·분류·요청한 수율 목표를 구분해야 합니다.

검증은 엄격한 정규화, source 동일성, 전계 전 전체 예산 거부, 각 해상도의
원래 행 실패, 인터럽트, 직접·공통 결과의 정확한 재생을 포함합니다. 실제 코팅
경계 예제는 두 표본을 네 해상도에서 다시 계산하여 미확정 하나·합격 하나를
보존합니다. 별도 코팅 전달·전체 특성·비영 길이 네트워크 기준도 유지합니다.
기존 정규화 입력과 직접 비교 기록은 그대로이며 이 요청이 메시를 자동으로
선택하거나 세분하는 것은 아닙니다.

[코팅 공차](layered_panel_study.md) · [English](../../../../../packages/sipi/panel_resolution_yield_document.md)
