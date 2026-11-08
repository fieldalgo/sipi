# 기하·재료 쌍 임피던스 목표 저장

`PairImpedanceDesignDocument`에 `material_variables`를 주면
`sipi.pair-impedance-design/2`를 저장합니다. 이름 있는 재료 숫자 필드 연결로
[쌍 재료 API](pair_material_design.md)를 재사용하며 함수나 실행 코드를 저장하지
않습니다. 양의 범위를 가진 정확히 두 변수는 기하 하나+재료 별칭 하나 또는 재료 별칭
둘입니다. 0 이상인 고정 주파수에서 실수 대칭쌍 임피던스 `z_diff`, `z_common`을
목표로 하며 단위는 Ω입니다. 복소 유손실·광대역 목적을 추가하지 않습니다.

예제의 중간점은 독립 검증한 얇은 stripline 목표를 이미 만족하므로 요청/세분 두 번만
평가합니다. 먼 초기점의 탐색은 `initial=[.35e-3,5.5]`, 예산 64처럼 더 큰 예산이 필요합니다.

```python
from sipi import PairImpedanceDesignDocument
from sipi.dielectric import DebyeDielectric
from sipi.execution import normalize_saved, execute_saved

goal = PairImpedanceDesignDocument('coupled_stripline',
    dict(width=.5e-3, gap=.1e-3, plane_spacing=1e-3, eps_r=1., box_width=8e-3),
    variables=['width', 'strength'], bounds=[[.3e-3,.7e-3],[2.,6.]],
    targets={'z_diff':69.86609070536932, 'z_common':30.721416289368904},
    tolerances={'z_diff':.5, 'z_common':.2}, max_evaluations=2,
    mesh=dict(edge_size=1e-6, far_size=.125e-3, grade=.1),
    frequency=1e9, materials={'dielectric':DebyeDielectric(2.,[4.],[1e9])},
    material_variables={'strength':dict(region='dielectric',path=['strengths',0])})
text = goal.dumps()
assert goal.to_dict()['schema'] == 'sipi.pair-impedance-design/2'
assert normalize_saved(text) == text
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete' and out['result']['evaluations'] == 2
rows = out['result']['history']
assert rows[0]['material_evaluation'] == rows[1]['material_evaluation']
assert all(abs(r)<=t for r,t in zip(out['result']['refined_residuals_ohm'], [.5,.2]))
```

## 엄격한 연결과 사전 검사

버전 2는 [버전 1 필드](pair_design_document.md)에 필수 `material_variables`를 더합니다.
`material_evaluation`은 null 대신 유효한 고정 주파수 모델 매핑이어야 합니다. 각 별칭은
정확히 `region`, `path`에 연결됩니다. 영역은 override에 있어야 하며 비어 있지 않은
경로는 해당 모델 `parameters` 아래의 기존 유한 숫자 필드를 선택합니다. 문자열 키와
정수 배열 인덱스를 사용하고 bool 인덱스·비숫자 대상·중복 대상·기하 이름 충돌·미지
필드·사용하지 않는 별칭은 거부합니다. 별칭은 1~2개이며 모두 순서 있는 두 `variables`
안에 있어야 합니다. 모델이 별도로 0이나 음수를 허용해도 역산 범위는 양수로 유지합니다.
기존 재료 study의 필드 연결 계약을 재사용합니다.

버전 1은 고정 재료만 지원하고 새 필드를 거부합니다. 버전 2를 자동으로 낮추지 않습니다.
읽을 때 입력을 복사·정규화하고 study validator로 명목 기하/재료와 네 모서리를 검사합니다.
명시한 초기점 또는 기본 중간점의 기하와 샘플 재료도 장해석·optimizer 호출 전에 확인합니다.
양끝 유효성이 내부 유효성을 보장하지 않습니다. 주축 각도 pi/2와 pi의 텐서는 대각이지만
중간 3pi/4는 기울어져 대칭쌍 목표에서 거부합니다. 비메시 사전 검사는 solve 예산 밖입니다.

기존 pitch/stack 제약은 기하 변수에 적용됩니다. 예를 들어 선폭과 재료 강도에 고정
pitch를 함께 사용할 수 있지만 유도되는 간격을 독립 변수로 추가할 수 없습니다.
기하의 유전체 변수와 명시 재료 override를 중복으로 조정하지 않습니다.

## 실행과 한계

`solve()`는 같은 순서의 값으로 기하와 재료 factory를 호출합니다. 각 완료 이력은 자신의
기하·인코딩한 모델을 보존하고 선택 입력은 동결해 factory 재호출 없이 세분 검사합니다.
실행 실패에는 현재 실패 모델과 이전 행별 모델, 단계·원인·실제 시도 수를 함께 남깁니다.
호출자 예산 검사는 solve 전에 수행합니다. 탐색 재현은 목표 JSON, 특정 행 재현은 그 행의
기하·재료 snapshot 둘을 함께 사용합니다.

별칭 두 개가 식별 가능한 재료 물성 두 개를 뜻하지 않습니다. 균일 Debye 모델의 pole
주파수에서 실수 유전율은 `eps_inf+strength/2`이므로 (2,4)와 (3,2)는 같은 기하에서 두
실수 임피던스가 같습니다. 유일한 재료 추정·자동 pole fitting·실측 보정을 주장하지 않습니다.
물리 범위와 식별 가능성은 호출자가 정해야 합니다.

수락 시험은 엄격 스키마/경로·순서·복사 격리·기하 제약·초기/모서리 모델 검사·실행 전
예산·실패 모델 보존을 확인합니다. 동일 정규화 기하·메시에서 실제 저장 실행은 raw API와
같습니다. 위 얇은 사례의 요청/세분 및 독립 Cohn 값은 (.5,.2)Ω를 만족해야 합니다.
먼 초기점 복원과 외곽 수렴은 기반 API의 별도 검증을 재사용합니다. 이전 reader는 버전 2를
거부하며 앱 엔진을 자동 변경하지 않습니다. 일반 정확도·브라우저/Windows 수락을 뜻하지 않습니다.

[쌍 목표 저장](pair_design_document.md) · [실행](execution.md) ·
[English](../../../../../packages/sipi/pair_material_document.md)
