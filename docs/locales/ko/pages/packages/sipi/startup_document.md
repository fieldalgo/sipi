# 무손실 시작 응답 입력 저장

`LosslessStartupDocument`는 `sipi.lossless-startup/1`을 저장하고
[무손실 단일 선로 시작 API](startup.md)를 공통 저장 실행에 연결합니다.
초기 에너지 0인 선로, PWL 입력, 저항 경계와 출력 시각을 명시적으로 보존하며
주파수 자료에서 시간 응답을 추정하지 않습니다.

```python
from sipi import LosslessStartupDocument
from sipi.execution import normalize_saved, execute_saved

document = LosslessStartupDocument([0., 1e-9, 2e-9, 3e-9],
    source_times=[0.], source_voltages=[1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=10000)
text = document.dumps()
assert normalize_saved(text) == text
assert document.required_terms == 1
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete'
assert out['result']['terms'] == 1
assert out['result']['voltage_v'] == [[.5, 0.], [.5, 1.], [1., 1.], [1., 1.]]
assert out['input']['max_terms'] == 10000
```

## 엄격한 스키마

아홉 필드가 모두 필수입니다: `schema`, `time_s`, `source_times_s`,
`source_voltages_v`, `z0_ohm`, `delay_s`, `source_resistance_ohm`,
`load_resistance_ohm`, `max_terms`. 알 수 없는 키/버전, 중복 키, 비유한 수,
숫자 필드의 bool은 거부합니다. 시간은 비음수이며 비어 있지 않고 엄격히
증가해야 합니다. 전압 형상은 입력 시간과 일치하며 한 knot로 step을 나타낼
수 있습니다. 단위, 입력 이전 0 및 마지막 값 유지는 API와 같습니다.
부하 null은 개방, 0은 단락이며 필드 생략을 뜻하지 않습니다.

로드는 API와 공유하는 입력 검증 및 필요 항 수 사전 계산을 사용합니다.
파형, 메시, 장을 계산하지 않습니다. 정규 JSON과 사전 접근은 독립적인
복사본입니다. 이후 모든 이동 knot의 해상도나 출력 진폭의 유한성을 사전에
보증하지는 않으며 해당 수치 검사는 실제 솔버에서 수행합니다.

## 별개의 두 한도

저장된 `max_terms`(1..10000)는 도달 가능한 전방 왕복 항의 상한이며 그대로
보존합니다. `required_terms`는 저장 시간 범위, 첫 입력 knot와 반사 계수로
정해지는 실제 필요 항 수입니다. `analyze(max_evaluations=128)`와 공통 실행은
이 수가 호출자 예산(기존 정수 범위 2..10000) 안인지 파형 계산 전에 검사합니다.
사용하지 않는 저장 상한 전체를 호출자가 허용할 필요는 없으며 저장 상한을
작은 값으로 바꾸지도 않습니다.

예제의 정합 소스는 저장 상한 10000에도 전방 항 하나만 필요하며 개방 부하의
귀환파는 유지합니다. 비감쇠 이상 소스에서 세 항이 필요한 시간 범위는 호출자
예산 2로 실행할 수 없습니다. 첫 입력 이전이면 필요 항 수는 0일 수 있습니다.
출력 시각 수와 보간 작업은 항 수와 다르므로 시간/메모리 보장은 아닙니다.

`analyze()`는 솔버가 저장 입력, 출력 시각과 필요 항 수를 보존했는지 확인합니다.
공통 실행은 기존 `sipi.execution/1` 봉투에 API의 유한 결과 사전을 담습니다.
양쪽 포트 전류는 선로 안 방향이며 포트 이름, 단위, 진행파와 원입력을 유지합니다.
기존 바이트 한도와 진단 제한을 적용하고 characteristic/mode 진단은 최상위
transmission/volume line만 허용합니다.

잘못된 입력, 예산 및 일반 솔버 실패는 원래 예외를 전달합니다. 특히 이동 knot의
해상도 실패를 부분 성공으로 바꾸지 않습니다. 이는 공통 실행의 기존 비역산
솔버 실패 정책과 같습니다.

수락 검사는 엄격 파싱, 파형 없는 정규화, 복사, 실제 항 예산, 저장 상한 보존,
결과 동일성과 step/pulse의 직접 API 재현을 확인합니다. 개방, 단락, 정합,
부정합 및 극단적 유한 부하를 포함합니다. 기반 API의 독립 LC 세분과 정확한
에너지 기준은 유지하며 실제 문서를 저장 스키마 registry에 등록합니다.

이 제한 모델은 리액티브 종단, 손실, 분산, 결합 선로 시작 응답이나 일반 TDR
해석을 추가하지 않습니다. 저장 스키마만으로 앱 폼이나 브라우저/Windows 지원이
완료되는 것은 아닙니다.

[시작 API](startup.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/startup_document.md)
