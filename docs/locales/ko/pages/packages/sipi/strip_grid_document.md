# 얇은 신호선·격자 접지 정전용량 입력 저장

[English](../../../../../packages/sipi/strip_grid_document.md) | **한국어**

`StripGridCapacitanceDocument`는 [세 영역의 얇은 신호선·격자 셀](strip_grid.md)의
14개 명시 입력을 `sipi.strip-grid-capacitance/1`로 저장합니다. 전체 정전용량 C[F]
입력 스키마이며 선로·주파수·파동 모델이 아닙니다. 원래의 물리 범위·기하·재료·수렴
제한을 그대로 유지합니다.

```python
from sipi import StripGridCapacitanceDocument

document = StripGridCapacitanceDocument(
    pitch=1e-3, grid_width=.5e-3, trace_width=.5e-3, height=.5e-3,
    top_clearance=1e-3, backside_depth=1e-3,
    eps_substrate=3.8, eps_above=1., eps_below=1.,
    transverse_periods=1, cells_per_pitch=4,
    cells_substrate=2, cells_above=4, cells_below=4)
saved = document.dumps()
reloaded = StripGridCapacitanceDocument.loads(saved)
assert reloaded.dumps() == saved
result = reloaded.analyze(max_evaluations=1)
assert result.capacitance_f > 0
```

루트는 정확히15키입니다. `schema`, `pitch_m`, `grid_width_m`, `trace_width_m`,
`height_m`, `top_clearance_m`, `backside_depth_m`, `eps_substrate`, `eps_above`,
`eps_below`, `transverse_periods`, `cells_per_pitch`, `cells_substrate`,
`cells_above`, `cells_below`입니다. SI 기하·양의 실수 상대 유전율·엄격한 정수 셀 수가
필요합니다. 누락/추가 키·중복 JSON 키·미지원 버전·불리언·비유한 값·다른 단위·비정합
폭은 거부합니다. 세 유전율과 세 수직 셀 수를 모두 명시해야 합니다.

`from_dict`, `loads`, `dumps`, `to_dict`와 공통 정규화는 원래의 스칼라·정합·노드/
사면체 자원·유한 체적·위 여유 기준을 검사하지만 메시 생성이나 장 풀이는 하지 않습니다.
사전은 새 사본으로 반환하며 canonical JSON은 키를 정렬하고 비유한 수를 제외합니다.
기하·셀 수·재료를 반올림·축소·추론하지 않습니다.

직접 `analyze(max_evaluations=1)`는1..10000의 정수 예산을 받으며 기하 자원 제한과
별도로 실제 장을 한 번 풉니다. [공통 실행기](execution.md)는 기존2..10000 범위를
유지하고2를 주어도 이 문서의 장 풀이는 한 번입니다. 예산은 반복 풀이·수렴 검사를
요청하는 값이 아닙니다.

```python
from sipi.execution import normalize_saved, execute_saved

assert normalize_saved(saved) == saved
# Common execution keeps its existing minimum budget of 2.
# The new static document still performs exactly one field evaluation.
output = execute_saved(saved, max_evaluations=2)
assert output['status'] == 'complete'
assert output['result'] == result.to_dict()
assert not output['result']['fields_included']
```

재현 결과는 자료형·입력 일치, 계산된 노드/사면체/전극 개수, 실제 폭·edge index,
재료·장 배열 크기를 검사합니다. 좌표 범위·인덱스 범위·전극 평면과 좌표에 따른 세
유전체 영역도 확인합니다. 반환된 기하로 검사하므로 새 메시를 만들지 않습니다.
원래 장 예외가 전달되며 수치 기준도 바꾸지 않습니다. 재현 성공이 물리 정확도나
개방 공간 극한을 보증하지는 않습니다.

공통 결과는 간결합니다. 직접 받은 `StripGridCapacitance`는
`to_dict(include_fields=True)`로 메시·재료·전위를 내보낼 수 있습니다. 입력 스키마와
결과 직렬화는 구분되며 확장 장 결과를 입력 파일로 읽을 수는 없습니다. 파일 읽기·쓰기는
호출자가 처리하고 엔진은 암묵적으로 수행하지 않습니다.

`tests/sipi/test_strip_grid_document.py`는 부분/전체 격자, 넓은 횡방향 영역,
비균일 수직 간격과 서로 다른 유전체, 반올림 범위의 요청 폭에서 직접 계산과 저장 재현의
전체 장 결과가 정확히 같은지 확인합니다. 엄격 키·단위·셀 수·예산·사본, 결과/기하/재료
훼손, 다른 종류 입력 거부, 원래 실패를 검사합니다. 독립 장·해석·수렴 시험은 물리 API
suite에 유지하고 함께 실행합니다. 새로운 수치 근사·의존성·플랫폼/측정 검증을 추가하지 않습니다.
