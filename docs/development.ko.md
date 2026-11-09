# 개발

SIPI는 외부 설치된 galerkin·meshine을 사용합니다. 공동 개발 시 dependencies.json의
커밋으로 만든 휠을 설치하고 `python -m pip install --no-deps .`로 SIPI를 설치합니다.
이 커밋은 개발 기준선이며 PyPI 게시 완료를 의미하지 않습니다.

미출시 개발 커밋은 같은 패키지 버전을 쓸 수 있습니다. 수치 결과와 함께 정확한
SIPI 커밋·wheel SHA-256·의존 패키지 산출물을 기록하세요. 버전 문자열만으로
해당 개발 빌드를 식별할 수 없습니다.

`PYTHONPATH=src python -m pytest -q tests/sipi`로 소스 시험을 실행합니다.
PowerShell에서는 먼저 `$env:PYTHONPATH="src"`를 설정합니다. 휠을 만들어 별도 환경에 설치한 뒤
시험을 체크아웃 밖으로 복사해 동일한 전체 시험을 실행합니다. 독립 네트워크 비교에는
scikit-rf 2.2.0, 독립 유한요소 비교에는 scikit-fem 12.0.2가 필요합니다.
둘 다 `sipi[test]`의 시험 전용 의존성이며 CI에서도 명시적으로 설치합니다.
일반 galerkin 휠 설치만으로 비교 도구 extra가 설치되지는 않습니다.
`OPENPHYSICS_REQUIRE_CROSSCHECK=1`로 누락된 도구를 skip 대신 오류로 처리합니다.
기하 계약은 해당 simcase reader와 함께
`integration/test_geometry_adapters.py`를 명시적으로 실행합니다.

provenance.json은 최초 이전 스냅샷의 파일과 상류 SHA-256을 기록합니다. 그 스냅샷은
수치 구현·기준값을 보존했고 이후 커밋은 독립 엔진을 확장합니다. 원본 출처 기록을
고쳐 쓰지 않고 정확한 커밋·wheel hash로 후속 빌드를 구분합니다. 원본 이력은 기록된
상류 커밋에 남습니다. 최초 이전은 웹 배포·Windows EXE 생성·새 플랫폼 지원을 뜻하지 않습니다.

## 설치 아티팩트 대조

검증 도구는 `python -m pytest -q tools/tests`로 시험합니다. 정확한 자체 패키지 휠을
설치한 뒤 `python tools/check_installed.py --wheels WHEEL_DIRECTORY`를 실행합니다.
이 폴더에는 sipi·galerkin·meshine·simcase 휠이 각각 하나 있어야 합니다. simcase는
기하 계약 통합 시험용입니다. 체크아웃 밖 새 프로세스에서 PYTHONPATH를 제거하고
실제 import 경로와 설치 파일을 휠 내용과 대조합니다. 같은 버전 번호만으로 올바른
코드를 시험했다고 판단하지 않습니다. 설치기가 재작성하는 RECORD를 제외하고
코드·메타데이터·라이선스 등 휠 내용을 대조하며 남아 있는 다른 Python 모듈도 거부합니다.

`.validation/installed.json`에 상태·실패 단계/원인·휠 SHA-256·검사 파일 수·런타임 버전을
기록합니다. 시작 시 이전 XML을 지우므로 실행/사전 검사 실패가 과거 성공 XML을 남기지
않습니다. 수치 시험 실패는 이번 실패 JUnit을 보존합니다. 이 검사는 아티팩트 일치 확인이며
물리 정확도나 임의 휠의 출처 보증은 아닙니다. 기존 수치/독립 비교 시험과 고정 빌드도 필요합니다.

현재 공동 개발 기준은 galerkin·meshine 0.0.2 개발 wheel을 사용한다. 선언 범위는
기존 0.1 개발 계열도 유지한다. 범위나 버전만으로 미출시 API의 존재를 확인할 수
없으므로 정확한 의존성 커밋으로 빌드하고 wheel 해시를 보존해야 한다. 경계 패널
API는 공유 galerkin 기능이며, 이 pin 변경만으로 기존 SIPI 계산이 이를 선택하지 않는다.

큰 매개변수 시험 입력에는 짧은 `ids`를 명시한다. pytest는 node ID를
`PYTEST_CURRENT_TEST`에 넣고 Windows 환경변수 값은 32767자로 제한된다.
실제 큰 입력과 거부 기준은 그대로 유지한다.
