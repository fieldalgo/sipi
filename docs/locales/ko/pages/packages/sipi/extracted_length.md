# 단면에서 추출한 선로의 길이 경계 역산

[English](../../../../../packages/sipi/extracted_length.md) · [길이 경계](length_design.md) · [면별 금속 선로](face_line.md)

`sipi.line-length-design/2`는 저장된 단면 선로를 기존 표본 대역 길이 역산에
연결합니다. 선언한 전체 주파수에서 한 번 추출하고 R/L/G/C를 고정한 채 길이만
바꿉니다. line/1–4의 `transmission-line` 또는 volume-line/1의 `volume-line`
source를 받으며 내부 선로의 `length_m`는 0이어야 합니다. 기본 버전 1의 명시적
RLGC 입력 계약은 그대로 유지합니다.

```python
from sipi import CrossSectionDocument, stripline
from sipi.line_model import TransmissionLineDocument
from sipi.length_design import LineLengthDesignDocument

cross = CrossSectionDocument(stripline(width=.5e-3, plane_spacing=1e-3,
    thickness=35e-6, eps_r=4., tan_delta=.02, box_width=4e-3),
    mesh=dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05))
line = TransmissionLineDocument(cross, [1e9, 2e9], materials={},
    conductor=dict(kind='perfect'), length=0.)
plan = LineLengthDesignDocument(dict(kind='transmission-line', document=line.to_dict()),
    limits=[dict(name='insertion', input_port='near:signal', output_port='far:signal',
                 frequency_hz=[1e9, 2e9], minimum=.7, maximum=None)],
    bounds=[0., 2.], tolerance=1e-5, max_evaluations=32,
    schema='sipi.line-length-design/2')
result = LineLengthDesignDocument.loads(plan.dumps()).solve()
assert result.feasible.passed and not result.infeasible.passed
assert result.infeasible_length_m-result.feasible_length_m <= 1e-5
ledger = result.to_dict()['source_evaluation']
assert ledger['field_extractions'] == 1
assert ledger['evaluations'] == 1+len(result.history) <= 32
assert ledger['resolved_network']['length_m'] == 0.
```

예제는 완전도체와 유전체 손실을 사용합니다. 표면·경계별·면별 금속 및 체적 도체
입력은 원래의 표피 깊이·재료·메시·전류 보존·지원 주파수 조건을 유지합니다.
정규화는 필드를 풀지 않습니다. 주파수 순서·도체/포트 이름·공통 실수 기준
임피던스를 보존하며 각 길이의 네트워크를 만든 뒤 필요하면 혼합모드로 변환합니다.

저장 예산 3–10000회는 **추출 작업 시도 1회와 모든 길이 네트워크 평가 시도**를
포함하며 실패한 시도도 셉니다. 추출 작업 하나에는 여러 내부 필드 계산이 포함될
수 있어 이 예산이 내부 계산 횟수·시간·메모리 제한을 뜻하지는 않습니다.
`execute_saved` 호출자 예산은 추출 전에 검사합니다. 중간점과 최종 양 끝점에서
필드를 다시 풀지 않습니다.

성공 결과의 `source_evaluation`은 `phase='complete'`, `field_extractions`,
`length_evaluations`, 총 `evaluations`와 완전한 RLGC source인
`resolved_network`를 분리된 사본으로 보존합니다. 원래 기하·재료는 정규 입력에,
Python 결과에는 `extraction`도 남습니다. resolved source는 버전 1로 재생할 수
있습니다. 이 스냅샷은 표본 행렬의 재현 근거이며 필드 수렴 근거를 대신하지 않습니다.

실패하면 `LengthGoalError.source_evaluation`과 공통 실행 오류에 같은 기록을
남기며 phase는 `extraction`, `network`, `bracket`, `budget`, `resolution`
중 하나입니다. 추출 실패에는 가짜 resolved 모델을 만들지 않습니다. 이후 실패에는
추출 행렬·완료 이력·해당 시 실패 길이·원래 예외 종류를 보존하며 미완성 구간을
수락된 결과로 내보내지 않습니다. 버전 1 결과/오류 형식은 이 추가 기록 없이 유지합니다.

하한 만족·상한 위반 구간만 받으며 모든 제한은 명시한 주파수 표본에 적용됩니다.
이분법은 경계 하나를 찾을 뿐 전역 최대·단조성·연속 대역·실측 정확도·제조 수율을
보장하지 않습니다. 원래 필드 입력의 메시·외곽 수렴 검증은 별도로 필요하며 길이
대수를 반복해도 추출 정확도가 높아지는 것은 아닙니다.

관련 검증은 실제 단일 면별 금속·결합 혼합모드·체적 추출, 요청당 1회 추출,
resolved 재생, 엄격한 내부 입력, 예산·실패 기록을 포함합니다. 독립 scikit-rf
2.2.0의 양 끝점 S와 절대 차이 1e−10 이내이며 독립 스칼라 근은 폭 1e−5m 이하의
수락 구간 안에 있습니다. 이는 같은 추출 행렬을 사용한 네트워크 역산 검증이고
행렬의 물리 정확도 검증은 아닙니다. 기존 무왜곡 해석해와 필드 수렴 검증도 유지합니다.

```sh
python -m pytest -q tests/sipi/test_extracted_length_design.py tests/sipi/test_length_design.py tests/sipi/test_band.py tests/sipi/test_execution.py
```
