# 개발

[제품과 계산 영역의 경계](architecture.ko.md)에 책임 범위와 화면 없는 전송선
라이브러리 추출 순서를 정리했습니다. 현재 패키지/API는 바꾸지 않습니다.

원본·후보의 정확한 소스, 설치 payload와 플랫폼별 세분 기록은
[격리된 메시 후보 진단](../tools/mesh_diagnostics/README.ko.md)을 참고하세요.
해당 진단의 소스 manifest와 runtime 기준은 과거 기록으로 유지합니다.
준비 명령은 현재 제품 의존성을 선택하지 않으며 기존 수치 기준도 바꾸지 않습니다.

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

SIPI는 공유 경계 패널 해법을 공개 모듈 `galerkin.panel_electrostatics`로만 부른다.
인자는 SI이다: `box_size`는 직사각형의 (폭, 높이)(m)이고, 도체는 `ground_indices`,
`signal_indices`, `signal_index`로 고른다. `CrossSection` 길이가 이미 m이므로 SIPI는
같은 수를 변환 없이 넘기며, 결과는 내부 해법의 결과 객체와 비트 단위로 같다. 저장된
형상 panel 요청은 `width`·`height` 키를 그대로 둔다.

큰 매개변수 시험 입력에는 짧은 `ids`를 명시한다. pytest는 node ID를
`PYTEST_CURRENT_TEST`에 넣고 Windows 환경변수 값은 32767자로 제한된다.
실제 큰 입력과 거부 기준은 그대로 유지한다.

## 지속 검증

검증 워크플로는 Linux·macOS·Windows에서 소스 회귀와 설치 산출물 회귀를
별도 작업으로 실행하며 각 시험 집합을 열여섯 묶음으로 나눕니다. 각 작업의 제한은
6시간입니다. 모듈 단위로 배정하므로 모듈 fixture는 같은 묶음에 남습니다.
`tools/shards/durations.json`(완전한 CI 실행의 JUnit XML에서 모은 모듈별 초)에
있는 모듈은 큰 것부터 기록 시간이 가장 적은 묶음에 넣고, 표에 없는 모듈은
상대 경로의 SHA-256으로 배정합니다. 모든 시험을 먼저 수집한 뒤 나누며, 수치 기준을 완화하거나
다른 묶음의 시험을 skip으로 처리하지 않습니다. 준비된 PR, main 푸시, 현재
independent-repository 개발 브랜치의 푸시에서 실행하므로 PR을 만들지 않고도
병합 전 검증을 할 수 있습니다. 각 작업은 고정된 독립 참조 도구, wheel/sdist
빌드, 검증 도구 시험과 실패 보고서를 유지합니다. 설치본 시험에는 기하 계약
검증도 포함됩니다. 이 검증은 패키지·실행 파일·웹사이트를 공개 배포하지 않습니다.

검증 보고서 업로드는 숨김 폴더 `.validation`을 명시적으로 허용하고,
경로를 `.validation/*.xml`, `.validation/installed.json`,
`.validation/*-shard.json`으로 제한합니다. 플랫폼·시험 집합·분할 번호마다
별도 아티팩트를 사용합니다.
이 옵션이 없으면 시험에서 보고서를 생성해도 업로드 동작이 제외합니다.
소스 체크아웃·휠·다른 숨김 파일은 수집 경로에 포함하지 않습니다.

개발 브랜치 푸시는 진행 중인 검증을 유지하고 최신 대기 실행을 남깁니다.
커밋을 원격에 보존하면서 기존 플랫폼 검증을 취소하지 않기 위한 설정입니다.
PR 갱신은 이전 실행을 취소하고 main은 전체 대기열을 유지합니다.
이전 커밋의 검증 완료가 새 브랜치 head의 검증 완료를 뜻하지 않습니다.

`tools/pytest_shard.py`는 선택적으로 사용하는 검증 플러그인이며 런타임 의존성이
아닙니다. 기존 로컬 pytest·설치 검사 명령은 기본적으로 분할하지 않습니다.
소스 명령에 `-p tools.pytest_shard --sipi-shard-count=16 --sipi-shard-index=0
--sipi-shard-report=.validation/source-shard.json`을 덧붙여 한 묶음을 실행할 수
있습니다. 0부터 15까지 각각 새 보고서 경로로 실행하세요. 설치 검사 명령에는
`--shard-count=16 --shard-index=0`을 사용합니다. 플러그인과 시간 표도 체크아웃
밖으로 복사하며, 네 휠 대조와 PYTHONPATH 제거는 유지합니다.

모듈이 늘거나 시간이 크게 바뀌면 시간 표를 갱신합니다. 완전한 실행 하나의
`validation-ubuntu-latest-source-<i>` 아티팩트를 받아
(`gh api repos/fieldalgo/sipi/actions/runs/<id>/artifacts`) 저장소 루트에서
`python tools/pytest_shard.py --update <모든 source.xml> --source "<실행, 커밋, 날짜, 파일>"`을
실행합니다. 표에는 출처와 명령이 남습니다. `tools/tests/test_shard_durations.py`는
표 형식, 결정적 배정, 균형 상한, 어떤 모듈도 기록 전체의 1/16의 1.1배를 넘지 않음을
검사합니다.

manifest(`sipi.pytest-partition/2`)에는 전체 원본 node ID·수집 해시·정규화한
시간 표의 SHA-256·배정 ID·실행 완료 ID·종료 상태를
남깁니다. 기존 manifest를 덮어쓰지 않으며 부분 실행을 전체 통과로 인정하지
않습니다. `tools/check_shards.py`는 모든 분할 번호, 동일한 원본 수집 결과,
체크아웃의 시간 표와 그 표로 계산한 배정과의 일치, 누락·중복 없는 배정,
모든 배정 시험의 성공적인 완료를 요구합니다.
명시적인 `--collect-only` 모드는 수집만 검사하고 `executed: false`를 표시합니다.
워크플로의 마지막 검사는 여섯 플랫폼·시험 집합과 소스/설치본 공통 제품 시험의
일치를 대조합니다. 한 묶음이라도 실패하거나 중단되면 나머지가 통과해도 실패입니다.
검사 이름에 분할 번호가 추가되므로 통합 전 필수 검사 설정을 검토해야 합니다.
이 변경은 기존 수치 실패 해결이나 새 플랫폼 지원, 앞으로의 시간 제한 준수를
보증하지 않습니다. 세 묶음일 때 가장 큰 묶음의 기록된 시험 시간은 Linux에서
4.7시간이었고, 러너 속도 차이로 Linux·Windows 작업이 6시간을 넘겨 취소됐습니다.
여덟 묶음이면 같은 모듈 시간으로 묶음당 최대 2.1시간입니다. Validate 실행
45965021952에서는 Linux 소스 시험 시간이 854분, 해시로 나눈 여덟 묶음이 84–148분,
세 플랫폼 작업이 72–210분이었습니다. 같은 모듈 시간을 열여섯 묶음으로 균형 배정하면
묶음당 53분입니다. 러너 속도는 여전히 다르고 표에 없는 모듈은 균형 배정되지
않으므로 시험이 늘면 다시 확인해야 합니다.

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

### 유한 해상도 연구(수동 실행 전용)

모서리 면 유한 해상도 연구는 사례마다 완전한 선로 여섯 개(기본, 더 촘촘한 유전체 메시,
더 촘촘한 패널, 둘 다, 더 넓은 바깥 상자 두 개)를 풀며 러너 한 대에서 사례당 6–60분
걸렸습니다. 이 연구는 `SIPI_RESOLUTION_STUDIES=1`일 때만 정의되고, 검증 워크플로의 수동
실행 전용 작업 `resolution-studies`(`gh workflow run validate.yml --ref <브랜치> -f
resolution_studies=true`)가 Linux·macOS·Windows에서 실행합니다. 평소 분할 실행에서는 각
연구의 기본 선로를 풀어 `tests/sipi/reference_data/resolution_studies/finite-resolution-studies.json`에
연구와 함께 기록한 값을 행렬 상대 1e-9 이내로 재현해야 합니다. 메셔가 정확한 cocircular
동점을 플랫폼마다 다르게 삼각분할할 수 있으므로(기록된 실행에서는 macOS) 기록은 유전체
메시(절점·삼각형의 SHA-256)마다 변형 하나를 둡니다. 변형과 같은 메시는 1e-9 이내로 일치해야
하고, 새 러너 이미지의 삼각분할처럼 어느 변형과도 맞지 않는 메시는 가장 가까운 변형과 행렬
상대 1e-4 이내로 비교합니다. 이 값은 기록된 두 메시 사이 최대 차이(2.2e-5)보다 크고 연구 기준
1%보다 백 배 작습니다. 어느 경로였는지는 JUnit 속성 `resolution_study_reproduction`에 남습니다. 따라서 정확도·수렴 검사는 연구한 해상도의 재현으로 평소 시험에 남고, 연구 판정
기준 자체는 바뀌지 않습니다.

| 모듈 | 연구 시험(사례) | Linux CI 시간 | 판정 기준(연구 작업이 돌 때 확인) | 평소 분할 실행 |
| --- | --- | --- | --- | --- |
| `test_two_ground_harmonic_three_active_corner_face_resolution` | `test_actual_layered_three_signal_finite_comparisons` [0] | 40.0분 | 선로 여섯 개, 전류 풀이 네 번. 모든 비교에서 각 R, L_internal, L_external, C, G, C0 항목이 모든 주파수에서 큰 쪽 크기의 1% 이내 | 기본 선로가 기록을 재현(1e-9) |
| `test_two_ground_harmonic_guard_corner_face_resolution` | `test_actual_layered_two_signals_and_guard_finite_comparisons` [0] | 39.3분 | 같음 | 같음 |
| `test_two_ground_linear_corner_face_resolution` | `test_actual_layered_one_and_two_signal_finite_comparisons` [0], [1] | 5.8, 22.1분 | 같음 | 두 사례 모두 같음 |

`tests/sipi/test_resolution_study_record.py`는 전계 풀이 없이 기록이 모든 사례에 대해 세
플랫폼 모두의 승인된 결과를 담는지, 기록된 모든 사본이 메시 변형에 배정됐는지, 연구 시험이
게이트가 켜졌을 때만 있는지 확인합니다. 연구 작업 후에는 그 JUnit XML(또는 게이트를 켠
Validate 실행의 XML)로 `PYTHONPATH=src python
tests/sipi/reference_data/resolution_studies/generate_finite_resolution_studies.py --junit
<플랫폼>/<시험 집합>=<xml> ... --source "<실행>"`을 실행해 기록을 다시 만듭니다. 생성기는 각
기본 선로를 로컬에서 다시 풀어 자기 메시의 변형과 일치하는지도 요구합니다.

시간 표는 연구 사례 네 개를 뺍니다(지금 수집되는 node ID를 `--collected`로 지정). 기록 시간이
854분에서 747분, 묶음당 46.7분이 됩니다. 새 재현 시험은 아직 CI 시간이 없으며 로컬에서
스레드 하나로 모두 합쳐 9분 걸렸습니다.

여러 해상도를 비교하거나 연구를 다른 경로로 다시 실행하던 무거운 시험 다섯 개를 각각 읽고
아래처럼 정했습니다. 시간은 Validate 실행 46099046636(main `b2cbb002`)의 소스/설치본 분이며
Linux, macOS, Windows 순입니다.

| 시험 | 검증 내용 | 시간(분) | 결정 | 지금 평소 시험 |
| --- | --- | --- | --- | --- |
| `test_two_ground_linear_corner_face_line_study.py::test_actual_scalar_sweep_refinement_and_complex_closed_forms` | 변당 패널 32개에서 실제 세 표본 스윕, 표본마다 패널 64·128개에서 R·L·C0를 다시 풀어 이웃 단계가 상대 1% 이내, 모든 단계의 닫힌 형태 특성 임피던스·전파 상수(상대 1e-12), 행 값이 Z0와 같음 | 20/35, 22/21, 45/35 | 나눔. 패널 64·128 세분은 해상도 연구이므로 바꾸지 않은 시험을 `SIPI_RESOLUTION_STUDIES=1`일 때만 실행 | `test_actual_scalar_sweep_closed_forms_and_recorded_base`: 패널 32개에서 같은 스윕·닫힌 형태·값 검사, 그리고 연구와 함께 기록한 표본별 R·L·C0·Z0 재현(`linear-line-study-base.json`, 로컬 86초) |
| `test_two_ground_harmonic_three_active_corner_face_resolution_document.py::test_actual_saved_finite_resolution_receipt` | 기록된 three-active 연구의 선로 여섯 개(같은 입력, 같은 1% 기준)를 `SavedExecutionRequest`로 실행해 완료·승인된 receipt 요구 | 39/29, 33/32, 59/51 | 연구를 한 번 더 실행하는 것이므로 수동 실행 전용. 저장 경로의 완료·실패·불일치·중단·CLI·기록 동작은 같은 모듈에서 전계 없이 이미 검사 | `test_saved_document_runs_the_recorded_study`(전계 없음): 저장 문서의 기본 선로가 기록된 연구의 기본 입력이고 바깥 선로·세분 패널·예산이 연구와 같음. 그 기본 선로는 해상도 모듈이 재현 |
| `test_two_ground_harmonic_guard_corner_face_resolution_document.py::test_actual_saved_finite_resolution_receipt` | guard 연구에 대해 같음 | 25/25, 34/37, 46/30 | 같음 | 같음 |
| `test_two_ground_harmonic_guard_corner_conductor.py::test_real_physical_faces_and_whole_currents_refine_without_floor[0]` | 패널 32·48개에서 물리 면·전체 전류 인자(C0, 면별·전체 부분)가 1% 이내, 모듈 자체 32개 경로가 공유 풀이와 정확히 같음 | 9/15, 12/12, 23/18 | 남김. 이 모듈들의 전류 경로를 실제 전계로 검사하는 유일한 시험(다른 시험은 stub로 공유 풀이를 재사용)이고 재현할 기록이 없음 | 그대로. 시간 검토: 32개 호출이 모듈 fixture의 풀이를 반복하지만 그 반복이 공유 풀이의 정확한 일치 검사이고, 48개 단계가 판정 기준이므로 검사 내용을 바꾸지 않고는 줄일 수 없음 |
| `test_two_ground_harmonic_three_active_corner_conductor.py::test_real_physical_faces_and_whole_currents_refine_without_floor[0]` | 능동 도체 셋에 대해 같음 | 7/10, 30/21, 12/23 | 위와 같이 남김 | 위와 같이 그대로 |

선로 연구 기록은 표본마다 기본 단계를 유전체 메시당 한 번 남깁니다. Linux와 Windows가 한
메시, macOS가 다른 메시입니다(R·L·C0는 경계 패널에서 나오므로 여섯 사본 모두 1.4e-14 이내로
같음). 재현은 모서리 면 연구와 같은 정확(1e-9)·가장 가까운 변형(1e-4) 경로를 따르고
`resolution_study_reproduction`을 기록합니다. 연구 실행 뒤 `PYTHONPATH=src python
tests/sipi/reference_data/resolution_studies/generate_linear_line_study_base.py --junit
<플랫폼>/<시험 집합>=<xml> ... --source "<실행>"`으로 다시 만들며, 생성기는 기본 스윕을 로컬에서
풀어 자기 메시의 변형과 일치하는지도 요구합니다. `resolution-studies` 작업은 저장 문서
receipt 두 개와 선로 연구 세분도 실행합니다.

## 명시적 양면 접지 개발 기능

`dependencies.json`의 공유 리비전은 범용 양면 Laplace 경계 기능을 제공합니다.
금속 법칙·유전체 추출·[저장 선로](locales/ko/pages/packages/sipi/two_ground_panel_line.md)·
[쌍 역산](locales/ko/pages/packages/sipi/two_ground_pair_goal_document.md)·
[제조 공차](locales/ko/pages/packages/sipi/two_ground_pair_study.md)는 SIPI가 소유합니다.
현재 개발 리비전은 로컬 공동 개발 브랜치에만 있을 수 있으므로 해당 패키지 wheel을
명시적으로 빌드합니다. 공유 브랜치가 공개되기 전에는 공개 CI가 이를 가져올 수 있다고
가정하지 않습니다. 기존 계산이 이 방법으로 자동 전환되지 않습니다. 소스·설치본 검증은
명시한 조건과 플랫폼만을 다룹니다.

## 스칼라 메시 길이와 의존 산출물 식별

`dependencies.json`의 개발 기준선은 작은 각도 격자 연산 네 곳에서
스칼라 `math.hypot` 길이를 사용합니다. 해당 연산에서 BLAS의 CPU 경로별
축약 차이를 피하며 기존 좌표, 후보 순서 계약, 메시 설정과 수치 기준은
유지합니다. 두 접지 경계 기능은 외부 galerkin API이고 SIPI는 공유 개별
패키지 wheel을 사용하는 독립 제품입니다.

모든 플랫폼에서 같은 메시를 보장하거나 같은 원 위 삼각분할 문제 및 기존
macOS 도체 사례의 수렴을 해결하는 변경은 아닙니다. 각 소비자는 정확한
의존 산출물을 다시 검증해야 합니다. 선택된 CPU 경로나 브라우저 대조는
전체 회귀나 물리 기준을 대신하지 않습니다. 기록된 커밋으로 공유 wheel을
빌드하고 버전 문자열이 같아도 각 해시를 보존하세요. 로컬 개발 커밋은
패키지 게시나 원격 빌드 가능성의 근거가 아닙니다. 이 의존성 갱신은 기존
메시 fixture, runtime 기준값과 수치 수락 한도를 다시 생성하지 않습니다.

## 고정한 의존 패키지의 짧은 패널 산술

공동 개발 기준은 길이가 다른 패널의 로그 적분에서 이미 수락한 값을 그대로
보존합니다. 기존 32/64점 적분 검사를 실패한 항은 국소 좌표로 다시 계산하며
같은 `1e-12` 기준을 통과해야 합니다. 큰 좌표 원점에서 매우 짧은 타깃의
이동량이 반올림으로 사라지는 일을 피합니다. 기존 솔버 설정, 보간 차수,
패널 분할 방식과 저장 문서 계약은 유지됩니다. 공유 패키지의 독립 검증은
짧은 패널과 긴 패널 한 쌍의 두 소스 순서, 60/80자리 기준 적분 및 기하
불변식을 다룹니다. 이 산술 수정은 새로운 물리 모델, 임의 단면 정확도 또는
추가 플랫폼을 수락하는 근거가 아닙니다.

## 고정한 의존 패키지의 벽 거리 패널 상자

고정한 공유 리비전은 옆·윗벽에 자신의 크기보다 가까운 패널 도체 군집을 더는 거부하지 않는다.
아래 접지·두 접지 해법 모두 이런 군집은 벽·평면 영상까지의 거리보다 넓지 않은 상자에서 같은 1e-10
검사로 보간하고, 상자가 256개를 넘으면 필드 계산 전에 거부한다. 전에 허용되던 군집은 결과가 비트
단위로 같다. 패널 진단은 상자를 쓴 경우에만 `smooth_interpolation_boxes`를 더한다. 시험의 벽 근접
실행 선로에서 panel C0와 독립 P2 부피 해의 차이는 저장된 731노드 메시에서 4.4e-4, 3076노드 기본
메시에서 5.8e-5였다.

## 고정한 의존 패키지의 두 접지 보간 상자

고정한 공유 리비전은 두 접지 패널 해법의 단일 상자 보간 검사가 실패하면 같은 설정과 1e-10
한도로 평면 거리 기준 상자에서 한 번 다시 검사한다. 전에 통과하던 입력은 결과가 비트 단위로
같고, 거절되던 결합·적층·broadside stripline이 계산된다. SIPI 두 접지 전류 진단은 이 재검사를
쓴 경우에만 `smooth_interpolation_boxes`와 `single_box_matrix_error`를 더하므로 이전 출력의
키는 그대로다.

## 고정한 의존 패키지의 단위·이름 변경

고정한 공유 리비전은 기존 공유 개발 브랜치에 단위·이름 배치 L2·L3가 들어간
OpenPhysics main을 병합한 것이다. 이전 공유 커밋과 SIPI의 이전 고정 커밋은 모두
조상으로 남는다. SIPI는 조립·풀이 커널(`assemble_stiffness`, `assemble_mass`,
`assemble_load`, `solve_dirichlet`, 3D 강성·모서리 행렬)을 `galerkin.kernels`에서
가져온다. IR drop 풀이는 SI 인자 이름을 쓰고 각 싱크를 들어오는 전류 밀도, 즉 이전
나가는 값의 정확한 부호 반전으로 넘긴다. galerkin 커패시턴스 교차 검사는
`relative_permittivity`를 넘긴다. SIPI 계산 공개 이름·입력·결과는 바뀌지 않는다. 형상 어댑터 `to_geometry_v1`만 고정한 simcase가 읽는 형식 0.3 부분을 쓴다([개요](packages/sipi/overview.md)).

이전·새 고정 wheel에서 예제 스크립트 16개의 출력은 바이트 단위로 같았고 시험 수집
node ID도 같았다. 저장된 scikit-fem 비교 스크립트는 기록된 해시를 유지하며 기록된
제품 커밋에서 실행한다. 이 의존 갱신은 새 물리 모델·플랫폼·게시 패키지를 수락하는
근거가 아니다.
