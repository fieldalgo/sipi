# 개발

원본·후보의 정확한 소스, 설치 payload와 플랫폼별 세분 기록은
[격리된 메시 후보 진단](../tools/mesh_diagnostics/README.ko.md)을 참고하세요.
제품 의존성 pin과 기존 수치 기준은 유지합니다.

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

비배포 수치 runtime 관측용 `threadpoolctl==3.6.0`을 설치한 뒤 검증 도구를
`python -m pytest -q tools/tests`로 시험합니다. 정확한 자체 패키지 휠을
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

## 지속 검증

검증 워크플로는 Linux·macOS·Windows에서 소스 회귀와 설치 산출물 회귀를
별도 작업으로 실행합니다. 각 작업의 제한은 6시간이며 두 전체 시험이 하나의
시간 예산을 나눠 쓰지 않도록 분리합니다. 준비된 PR, main 푸시, 현재
independent-repository 개발 브랜치의 푸시에서 실행하므로 PR을 만들지 않고도
병합 전 검증을 할 수 있습니다. 각 작업은 고정된 독립 참조 도구, wheel/sdist
빌드, 검증 도구 시험과 실패 보고서를 유지합니다. 설치본 시험에는 기하 계약
검증도 포함됩니다. 이 검증은 패키지·실행 파일·웹사이트를 공개 배포하지 않습니다.

검증 보고서 업로드는 숨김 폴더 `.validation`을 명시적으로 허용하고,
경로를 `.validation/*.xml`과 `.validation/installed.json`으로 제한합니다.
이 옵션이 없으면 시험에서 보고서를 생성해도 업로드 동작이 제외합니다.
소스 체크아웃·휠·다른 숨김 파일은 수집 경로에 포함하지 않습니다.

개발 브랜치 푸시는 진행 중인 검증을 유지하고 최신 대기 실행을 남깁니다.
커밋을 원격에 보존하면서 기존 플랫폼 검증을 취소하지 않기 위한 설정입니다.
PR 갱신은 이전 실행을 취소하고 main은 전체 대기열을 유지합니다.
이전 커밋의 검증 완료가 새 브랜치 head의 검증 완료를 뜻하지 않습니다.

결합 표면 도체와 Cannonball 세분 시험은 수렴 판정 전에 JUnit testcase 속성의
`conductor_refinement` JSON에 기하, 원·세분 메시, 주파수, R/내부L/C0 행렬,
경계별 손실 계수, 전류 적분과 수치 라이브러리 버전을 기록합니다. 이미 계산한
결과를 직렬화하므로 추가 전계 풀이가 없습니다. 플랫폼 대조 시 실패 XML도
보존합니다. 작은 전류 플럭스 오차만으로 저항 오차의 상한을 보장하지 않습니다.
기존 메시 fixture, 저항 변화 5% 기준과 귀환 전류 검사는 그대로 유지합니다.

브라우저 저장 공차 검사는 수치 일치 단언 전에 `study-N.json`을 기록합니다.
정확한 입력·내려받은 결과·네이티브 기준을 실패 행까지 보존합니다.
실패 실행 디렉터리는 그대로 두고 재실행은 새 디렉터리에 저장합니다.
진단 기록은 일치 기준을 바꾸거나 실패 런타임을 수락하지 않습니다.

별도 `Numerical platform checks` 워크플로는 지정된 개발 브랜치 경로가 바뀌면
Linux·macOS·Windows의 설치 wheel에서 집중 검증을 실행합니다. 자체 패키지 4개의
실제 import 파일을 wheel 내용과 대조하고, 빌드된 모든 wheel 해시·정확한 커밋/tree·
수치 라이브러리 버전을 기록합니다. reactive 상태 극한·기존 불변식과 기존 도체
수렴 검사를 두 그룹으로 실행하며 첫 그룹이 실패해도 두 번째 그룹을 실행합니다.
실패는 작업 실패로 남깁니다. 전체 회귀를 보완하는 검사이며 릴리스나 실행 파일의
지원 완료를 뜻하지 않습니다.

`SIPI_NUMERICAL_MESH_OUTPUT`에 새 출력 디렉터리를 지정하면
`tests/sipi/test_crosscheck_conductor_p2.py`가 실제로 푸는 원·세분 진공 메시를
보존합니다. 이 선택적 시험 기록은 메시를 다시 만들지 않고 노드·삼각형·순서 있는
신호 이름·신호 노드 집합·접지 노드를 압축 NPZ로 저장합니다.
`numpy.load(path, allow_pickle=False)`로 읽습니다. 재계산 시
`galerkin.Mesh(nodes, triangles, {})`를 구성하고 저장된 신호·접지 집합을
`sipi.conductor.surface_current_factors`에 전달합니다. 유전체 모델은 포함하지
않습니다. 기존 파일은 덮어쓰지 않으며 JUnit 속성에 파일 SHA-256과 계산한 경계
물리량을 기록합니다. CI는 실패한 경우에도 두 그룹의 원본 XML·환경 JSON·메시를
보존합니다.

`8694e70`의 설치본 집중 검증은 동일한 reactive 상태 220건이 세 운영체제에서
모두 통과했습니다. 도체·참조 7건은 Linux·Windows에서 통과했고 macOS에는 기존
PCB 세분 실패 3건이 남았습니다. 실제 메시 재계산과 한계는
[도체 관측 기록](locales/ko/pages/packages/sipi/conductor.md)을 참고하세요.
이 결과는 선택한 시험과 정확한 해당 커밋의 근거이며 이후 커밋의 전체 회귀
상태를 뜻하지 않습니다.
