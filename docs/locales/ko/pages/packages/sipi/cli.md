# 저장 입력 명령

[English](../../../../../packages/sipi/cli.md)

개발 wheel은 `sipi run`, `sipi validate`를 설치하며 `python -m sipi`도 같은 명령을
제공합니다. [개발 안내](../../../../../development.ko.md)의 정확히 검증한 wheel과
대응 의존성을 사용합니다. PyPI 출시 안내는 아닙니다. 명령은 브라우저·서버를
시작하지 않습니다. UI 자산과 기본 UI 실행기는 별도 작업이며 현재 하위 명령 없는
`sipi`는 사용법을 표시하고 종료 코드 2를 반환합니다.

기존 API로 입력을 만듭니다.

```python
from pathlib import Path
from sipi import LumpedNetworkDocument

doc = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9,
                            port_names=("input", "output"))
Path("input.json").write_text(doc.dumps(), encoding="utf-8")
```

```sh
sipi validate input.json --output canonical.json
sipi run input.json --output result.json
```

`validate`는 전계를 풀지 않고 정규 입력을 저장합니다. `run`은
[SavedExecutionRequest](execution_request.md)의 `sipi.execution-receipt/1`을 기록합니다.
정규 입력·실행 제어·의미상 요청 ID와 기존 `sipi.execution/1` 출력이 들어갑니다.
개별 실행 ID, artifact 선언, 런타임 증명은 아닙니다. 입력·결과와 정확한 엔진·의존성
wheel 해시를 함께 보관합니다. 개발 버전 문자열만으로는 배포물을 식별할 수 없습니다.

```python
import json
from pathlib import Path

receipt = json.loads(Path("result.json").read_text(encoding="utf-8"))
assert receipt["schema"] == "sipi.execution-receipt/1"
assert receipt["execution"]["status"] == "complete"
assert receipt["execution"]["input"]["schema"] == "sipi.lumped-network/1"
```

[등록된 계산 입력](execution.md)을 받으며 프로젝트·receipt·결과 기록은 계산 입력이
아닙니다. 미지원 버전·중복 키·비유한 값은 기존 엔진대로 거부합니다. 템플릿 추정이나
자동 메시 세분은 추가하지 않습니다.

`--output` 생략 시 UTF-8 JSON을 stdout으로 씁니다. `-`는 stdin 또는 stdout이며
오류는 stderr로 나옵니다. `--max-input-bytes`는 기본 262144, 범위 1..67108864로
파싱 전에 원문 UTF-8 바이트를 제한합니다. `run --max-evaluations`는 기본 128이며
기존 공통 범위 2..10000과 모델별 실행 전 검사를 유지합니다. 저장 예산을 임의로
줄이지 않습니다. 지원하는 최상위 선로에서 `--diagnostic characteristic`,
`--diagnostic modes`를 사용할 수 있고 중복 지정은 거부합니다. 이 설정은 실행 시간이나
메모리 한도가 아닙니다.

| 종료 | 의미 |
|---|---|
| 0 | 검증 또는 실행 완료. fitting의 `accepted`와 선택적 진단 실패는 별도 결과 판단입니다. |
| 1 | 실패·불완전 실행 또는 계산·모델 실행 전 검사 예외. 실패·불완전 receipt의 원래 행·이력을 보존하며 예외에 가짜 receipt를 만들지 않습니다. |
| 2 | 사용법·입력 읽기·요청 준비 실패. |
| 3 | 기존 목적지·닫힌 출력 파이프 등을 포함한 출력 실패. |
| 130 | Ctrl+C 중단. 재시도 전에 출력 경로를 확인합니다. |

출력은 새 경로여야 하며 부모 디렉터리는 이미 있어야 합니다. 유한 JSON 전체를
직렬화하여 같은 디렉터리의 임시 파일에 쓰고 fsync 후 배타적 hard link로 게시합니다.
동시 실행에서도 서로의 결과를 덮어쓰지 않습니다. 자기 임시 파일만 제거하며 게시 후
오류이면 완전한 결과가 이미 존재함을 알립니다. 재시도할 때 새 경로를 사용합니다.
자동 교체·백업·남은 파일 복구·전원 장애 내구성 기능은 아닙니다. hard link 지원이
필요합니다. 파일시스템 검사는 Linux에서 실행했으며 Windows/macOS 검증은 별도입니다.
입력 파일은 수정하지 않습니다.
