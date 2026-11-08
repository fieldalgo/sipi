# 유한 격자 접지·평판 정전용량 입력 저장

`GridPlateCapacitanceDocument`는 명시한
[유한 영역의 얇은 격자·넓은 판 셀](grid_plate.md)을
`sipi.grid-plate-capacitance/1`로 저장합니다. 전체 정전용량은 F 단위이며
임의 명시3D메시를 변환하거나 개방 경계·선로 전파 모델을 추정하지 않습니다.

필수 루트 키는 정확히9개입니다: `schema`, `pitch_m`, `width_m`,
`height_m`, `backside_depth_m`, `eps_r`, `cells_xy`, `cells_above`, `cells_below`.
네 길이는 m, 유전율은 균일 실수 상수입니다. 물리 결과는 요청 폭과
반올림 정합 범위의 실제 메시 폭을 모두 보존합니다. 두께·주파수·이방성·
추가 단위 변환을 추론하지 않습니다. 누락/추가/중복 키·미지원 버전·비유한
JSON·불리언 수치·격자에 맞지 않는 폭·잘못된 정수 개수를 거부합니다.

정규화는 원래 수치·정합·유한 체적·노드/사면체 상한을 검사하지만 메시를
생성하거나 장을 계산하지 않습니다. 정규화된 입력을 복사하고 기하와
모든 개수를 그대로 유지합니다.

```python
from sipi import GridPlateCapacitanceDocument
from sipi.execution import normalize_saved, execute_saved

document = GridPlateCapacitanceDocument(pitch=1e-3, width=.5e-3,
    height=.5e-3, backside_depth=1e-3, eps_r=3.8,
    cells_xy=4, cells_above=2, cells_below=4)
text = document.dumps()
assert normalize_saved(text) == text
assert document.to_dict()['schema'] == 'sipi.grid-plate-capacitance/1'
assert len(document.to_dict()) == 9
```

```python
loaded = GridPlateCapacitanceDocument.loads(text)
result = loaded.analyze(max_evaluations=1)
# Common execution retains its existing minimum budget of two.
out = execute_saved(text, max_evaluations=2)
assert out['result'] == result.to_dict()
assert out['input'] == document.to_dict()
assert not out['result']['fields_included']
assert result.to_dict(include_fields=True)['fields_included']
```

한 번의 분석은 정전장 계산1회를 수행합니다. 문서의 직접 `analyze`는
정수 `max_evaluations=1..10000`(기본1)을 받습니다. 공통 `execute_saved`는
기존 정수2..10000 계약을 유지하므로 최소2를 지정합니다. 이 경우에도
실제 장 계산은 정확히1회입니다. 예산이 횡방향/상하 셀 수나 물리 노드/
사면체 상한을 바꾸지 않습니다. 공통 실행의 입력 바이트·관련 없는 진단
검사도 장 계산 전에 적용됩니다.

재실행은 정확한 결과/셀 자료형, 동일한 정규 입력, 실제 폭/edge 메타데이터,
예상 노드/사면체/전극 개수와 C·에너지·접지 전하·전위 배열 모양을 요구합니다.
공통 실행은 간결한 물리 결과를 반환하고 직접 결과의
`to_dict(include_fields=True)`는 메시와 장을 포함할 수 있습니다.
원래 장 계산 실패를 부분 성공으로 바꾸지 않습니다.

partial/solid/상하 비균일/반올림 정합 셀의 전체 기하·전위 배열을 정확히
재현합니다. 엄격 키·단위·수치, 메시 생성 전 자원/규모 거부, 복사,
1회 계산 예산, 결과 동일성 훼손과 원래 실패도 검사합니다. 물리 API의
독립 약형·해석·수렴 시험은 별도 근거로 유지합니다. 기존 명시 메시/선로/
파동 스키마에 이 기하 객체를 암묵적으로 허용하지 않습니다. 저장 지원은
선로 RLGC·주파수 유효범위·실측 정확도·앱 통합·플랫폼 지원을 뜻하지 않습니다.

[공통 실행](execution.md) · [물리 API](grid_plate.md)
