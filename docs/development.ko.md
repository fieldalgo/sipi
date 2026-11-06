# 개발

SIPI는 외부 설치된 galerkin·meshine을 사용합니다. 공동 개발 시 dependencies.json의
커밋으로 만든 휠을 설치하고 `python -m pip install --no-deps .`로 SIPI를 설치합니다.
이 커밋은 개발 기준선이며 PyPI 게시 완료를 의미하지 않습니다.

`PYTHONPATH=src python -m pytest -q tests/sipi`로 소스 시험을 실행합니다.
PowerShell에서는 먼저 `$env:PYTHONPATH="src"`를 설정합니다. 휠을 만들어 별도 환경에 설치한 뒤
시험을 체크아웃 밖으로 복사해 동일한 전체 시험을 실행합니다. 독립 네트워크 비교에는
scikit-rf 2.2.0, 독립 유한요소 비교에는 scikit-fem 12.0.2가 필요합니다.
둘 다 `sipi[test]`의 시험 전용 의존성이며 CI에서도 명시적으로 설치합니다.
일반 galerkin 휠 설치만으로 비교 도구 extra가 설치되지는 않습니다.
`OPENPHYSICS_REQUIRE_CROSSCHECK=1`로 누락된 도구를 skip 대신 오류로 처리합니다.
기하 계약은 해당 simcase reader와 함께
`integration/test_geometry_adapters.py`를 명시적으로 실행합니다.

provenance.json은 이전한 파일과 원본 SHA-256을 기록합니다. 수치 구현·기준값은
변경하지 않았습니다. 원본 이력은 기록된 상류 커밋에 남으며 새 저장소는 출처가 있는
스냅샷으로 시작합니다. 이번 이전은 웹 배포·Windows EXE 생성·새 플랫폼 지원을 뜻하지 않습니다.

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
