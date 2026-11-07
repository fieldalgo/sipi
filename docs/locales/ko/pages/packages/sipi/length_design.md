# 주파수 표본별 제한을 이용한 선로 길이 경계 역산

[English](../../../../../packages/sipi/length_design.md) · [대역 제한](band.md)

`LineLengthDesignDocument`는 주어진 균일 선로 RLGC에서 길이만 바꿉니다.
삽입·반사·누화 등 여러 제한을 동시에 만족하는 쪽과 위반하는 쪽의 길이 경계를
찾습니다. **전역 최대 길이**를 보장하지 않습니다. 부정합 선로에서는 허용 구간이
여러 개로 나뉘거나 응답이 비단조일 수 있습니다.

```python
import numpy as np
from sipi.length_design import LineLengthDesignDocument

network = dict(kind='rlgc', frequency_hz=[0, 1e8, 2e8],
    R=[[15]], L=[[2.5e-7]], G=[[.006]], C=[[1e-10]],
    length_m=0, reference_ohms=50, names=['s'])
plan = LineLengthDesignDocument(network, bounds=[0, 2], tolerance=1e-7,
    limits=[dict(name='insertion', input_port='near:s', output_port='far:s',
                 frequency_hz=[0, 2e8], minimum=.8, maximum=None)])
result = LineLengthDesignDocument.loads(plan.dumps()).solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.infeasible_length_m-result.feasible_length_m <= 1e-7
assert abs(result.feasible_length_m-(-np.log(.8)/.3)) <= 1e-7+1e-10
```

엄격한 `sipi.line-length-design/1`은 `schema`, `network`, `limits`, `basis`,
`bounds_m`, `tolerance_m`, `max_evaluations`만 포함합니다. 입력은 **length_m=0**인
명시적 `rlgc` 객체여야 합니다. 영길이는 주어진 단위길이 계수를 검증하기 위한
기준이며 실제 시도 길이는 두 탐색 경계에서 정합니다. 기존 실수 대칭·수동 RLGC
조건을 유지합니다. 계수는 명시한 주파수별로 다를 수 있지만 보간하거나 fitting하지
않습니다. 기하에서 추출한 RLGC도 별도로 검증한 뒤 명시적으로 넣을 수 있습니다.
이 문서는 필드 메시를 다시 추출하거나 세분화하지 않습니다.

탐색 경계는 유한한 0 이상 길이이고 오름차순, 정밀도는 양수 m 단위입니다.
기준과 1–64개 제한은 [대역 제한](band.md)의 명시적 포트·주파수 양끝점·선택적
mixed-mode 규칙을 따릅니다. 하한은 모든 제한을 만족하고 상한은 하나 이상을
위반해야 합니다. 거부할 경계여도 양 끝점을 모두 계산합니다. 둘 다 만족하면
사용자 상한 밖을 찾지 않고 거부하며, 하한이 실패하면 다른 허용 구간으로 건너뛰지 않습니다.

이분법은 만족하는 하한과 위반하는 상한을 유지하고 폭이 tolerance_m 이하일 때
종료합니다. 반환 하한은 표본별 제한을 만족하며 상한은 가까운 위반을 보여 줍니다.
이는 주어진 탐색 구간의 경계 하나이며 유일하거나 가장 큰 허용 길이의 증명이 아닙니다.
주파수 표본 사이의 제한, 불확도·수율·제조 여유·인과성·재료 유효범위를 보장하지 않습니다.

계산 예산 2–10000회에는 양 끝점과 모든 중간점이 포함되며 숨은 최종 계산은
없습니다. 입력 정규화는 기존 영길이 네트워크 대수를 수행할 수 있습니다.
처음부터 충분히 좁은 구간은 두 번만 계산해 끝날 수 있습니다. 예산 소진·새
중간점의 부동소수 표현 불가·수치 계산 실패는 `LengthGoalError`이며 부분 후보를
수락된 설계로 내보내지 않습니다. 완료된 이력을 보존하고 수치 실패에는
`failed_length_m`, `cause_type`도 남깁니다. 인터럽트는 정상 완료로 바꾸지 않습니다.

결과는 두 길이 경계와 양쪽의 전체 대역 판정, 계산 이력, 정규 입력 JSON을
보존합니다. `to_dict()`의 scope는 `sampled-band-bracket-boundary`입니다. 공통
실행은 같은 결과 또는 오류/이력이 있는 `status='failed'`를 내보내며 탐색 전에
호출자의 예산도 검사합니다. 기존 앱 엔진 pin은 새 계약과 별도로 유지됩니다.

검증은 주파수별 정합 무왜곡 RLGC의 해석적 길이 경계 -log(minimum)/alpha,
1e−7m 구간 폭, exp(-alpha*length) 크기 상대 1e−10, 양 끝점의 독립
scikit-rf 2.2.0 네트워크 절대 차이 1e−10을 사용합니다. 복수 대역·혼합모드 기준,
예산·잘못된 경계·재생·수치 실패 보존도 검사합니다. 필드 솔버는 추가하지 않으므로
메시·외곽·모델 정확도는 원래 추출의 검증 범위를 따릅니다.

```sh
python -m pytest -q tests/sipi/test_length_design.py tests/sipi/test_band.py tests/sipi/test_execution.py::test_registry_all_versions_normalize_without_field_solve
```
