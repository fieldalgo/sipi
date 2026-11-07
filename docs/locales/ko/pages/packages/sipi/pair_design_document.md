# 두 변수 임피던스 목표 저장

`PairImpedanceDesignDocument`는 `sipi.pair-impedance-design/1`을 저장합니다.
이름 있는 템플릿 변수를 [두 목표 API](pair_design.md)에 연결하며 callable이나
임의 실행 코드를 JSON에 넣지 않습니다. 목표와 절대 허용 오차는 정확히
`z_diff`, `z_common` 키를 가진 객체이고 단위는 Ω입니다. JSON 키 순서로 모드를
선택하지 않습니다. 실수 정전 대칭쌍 임피던스이며 복소 유손실·비대칭 전방 여기·
종단 임피던스가 아닙니다.

```python
from sipi import PairImpedanceDesignDocument
from sipi.execution import normalize_saved, execute_saved

goal = PairImpedanceDesignDocument('coupled_grounded_coplanar',
    dict(width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
         substrate_height=.5e-3, eps_r=1., box_width=12e-3, air_height=6e-3),
    variables=['width', 'gap'], bounds=[[.3e-3, .7e-3], [.1e-3, .5e-3]],
    targets={'z_diff':172.45677879183611, 'z_common':65.9597000672247},
    tolerances={'z_diff':1.5, 'z_common':.5}, max_evaluations=2,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
text = goal.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result']['quantities'] == ['z_diff', 'z_common']
assert output['result']['evaluations'] == 2
```

이 예제의 중간 시작점은 독립 얇은 도체 기준해에 이미 가깝습니다. 두 시도는 요청
메시와 세분 메시입니다. 먼 초기점 탐색에는 더 큰 저장 예산이 필요합니다.
예를 들어 `initial=[.35e-3,.45e-3]`, 예산64를 사용할 수 있습니다. 호출 API의
차분 비용·메시·물리 한계는 그대로 적용됩니다. 이전 reader는 새 스키마를 거부하며,
이 계약만으로 브라우저나 네이티브 앱의 엔진이 자동 갱신되지는 않습니다.

## 입력 계약

필수 최상위 필드는 `schema`, `template`, `parameters`, `variables`,
`targets_ohm`, `tolerances_ohm`, `initial`, `max_evaluations`, `mesh`,
`fixed_pitch_m`, `fixed_plane_spacing_m`, `material_evaluation`입니다.
순서 있는 두 `variables`는 각각 `name`, `bounds`만 가지며 이름은 서로 달라야 합니다.
각 bounds는 변수 단위의 양수·유한·엄격 증가 쌍입니다. `initial`은 null(중간값)
또는 변수 순서대로 각 범위 안의 두 값입니다. 목표·허용 오차는 양수이고 예산은
2..10000입니다. 알 수 없는 필드·중복 키·비유한 값·미지원 버전은 거부합니다.
생성 입력과 반환 사전은 분리된 복사본입니다.

기존 대칭쌍 study registry로 명목·네 모서리·초기 기하를 검증하고 명목 메시 설정을
확정합니다. 읽는 동안 장해석·통계 study·optimizer를 실행하지 않습니다.
이 비메시 기하 사전 검사는 solve 시도 예산 밖입니다. 모서리가 유효해도 모든 내부점의
기하 유효성이나 임피던스 범위를 보장하지 않으며 내부 실패는 solver 이력에 남습니다.

`fixed_pitch_m`, `fixed_plane_spacing_m`은 기존 공차 제약을 재사용합니다.
예를 들어 폭과 한 층 높이를 바꾸면서 간격과 다른 층 높이를 유도할 수 있습니다.
유도되는 간격을 동시에 독립 변수로 삼을 수 없습니다. 이 버전은 material-leaf 별칭을
저장하지 않습니다. 고정 주파수 scalar/주축 재료는 `frequency_hz`, `materials`를 가진
정확한 `material_evaluation` 객체 또는 null을 사용합니다. 기존 재료 override와
횡방향 대칭 제한은 유지합니다.

## 실행과 재현

`solve()`는 API의 `PairImpedanceDesign`을 반환하고 `execute_saved()`는 기존
`sipi.execution/1` 외곽 계약을 사용합니다. 호출자의 `max_evaluations`가 저장 예산보다
작으면 solve 전에 거부하며 자동으로 줄이지 않습니다. 성공 결과에는 순서 있는 변수
값, 두 모드의 목표·허용 오차, 요청/세분 값·입력, 완료 이력과 고정 재료가 포함됩니다.
탐색을 재현하려면 목표 JSON을 저장해야 하며 선택 기하만으로 원래 범위·제약을 알 수 없습니다.

실패한 목표는 `status='failed'`, `result=None`이며 시도 수·단계·실패 변수·원인 종류·
가능한 입력·완료 이력·고정 재료를 보존합니다. 잘못된 입력이나 작은 호출자 예산은
solve 전에 예외를 발생시킵니다. 실패를 부분 성공으로 바꾸지 않습니다.
transport adapter는 파일·네트워크·프로세스 작업이나 앱 배포를 하지 않습니다.

수락 시험은 장해석 없는 엄격 파싱, 변수/모드 순서, 합성 제약, 고정 재료 재현,
호출자 격리, 예산 거부와 실패 직렬화를 검사합니다. 얇은 image-panel 사례에서는
실제 저장/직접 실행 일치와 양쪽 메시의 1.5Ω/.5Ω 목표를 확인하며 선택 기하의 별도
160패널 Green 계산도 같은 목표를 만족해야 합니다. 먼 초기점 탐색·메시·외곽 검사는
기초 API 시험이 담당합니다. 실측 기판·전역 최적화·브라우저·Windows 수락은 아닙니다.

[공통 실행](execution.md) · [두 목표 API](pair_design.md) ·
[English](../../../../../packages/sipi/pair_design_document.md)
