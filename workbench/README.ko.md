# SIPI workbench 후보

[English](README.md)

[프로젝트 흐름](PROJECTS.ko.md)은 기존 폼 5종의 입력 변형과 **Saved analysis**의
저장 실행 이력을 지원한다. 프로젝트와 개별 환경 파일은 사용자가 직접 내보내며
자동 원격 저장을 하지 않는다.
[실행 결과 연결](RECEIPTS.ko.md)은 저장 계산을 해당 입력 설정에 묶는다.
[설치 파일 helper](ARTIFACTS.ko.md)는 호스트 출처용 실제 배포물 파일을 수집한다.
[계산 기록](RECORDING.ko.md)은 설치 wheel 또는 staged 브라우저의 **Saved analysis → Run and keep record**에서 원문 결과 기록과 실행환경 목록을 내보낸다.
[브라우저 기록](BROWSER_RECORDING.ko.md)은 같은 기록 전달에 검사된 staged 배포 원본을 사용한다.

독립 설치한 SIPI 엔진을 기본 브라우저의 로컬 화면 또는 브라우저 Worker에서
실행하는 소스 후보입니다. 출시된 앱은 아닙니다. Windows x64는 설치 없는
단일 EXE가 목표이며 Python·엔진·화면을 포함하고 별도 브라우저 엔진이나
원격 계산 서비스를 포함하지 않습니다. 실제 용량과 Windows 동작은 성공한
Windows 빌드·실행 보고서로 확인해야 합니다. wheel 크기는 EXE 크기가 아닙니다.

기본 화면은 단면 입력 폼 5종, 저장된 메시 설정, 목표 임피던스, 공차 샘플,
단면 JSON 저장과 선로·회로 결과를 제공합니다. **Saved analysis**에서는
[`sipi.execution`](../docs/locales/ko/pages/packages/sipi/execution.md)에 등록한
고정 엔진의 등록 계약 원문 JSON을 열고 검증·정규 저장·실행·결과 내보내기를 합니다.
실패한 공차 행과 목표 역산 이력도 보존하며 불완전한 공차 결과의 요약은
계산하지 않습니다. 선택한 특성/모드 진단이 실패해도 기본 선로 결과는 남습니다.
입력 변경·취소 시 기존 결과의 표시·내보내기를 무효화합니다. 모든 계약의
전용 입력 폼까지 구현한 것은 아닙니다. 명시적인 메시를 담은 유한 영역 3D
정전용량 입력은 저장한 절연 경계·도체 순서를 유지해 전체 C(F)를 반환합니다.
기하 편집기·비아 전이 L/S·열린 공간 프린징까지 지원한다는 뜻은 아닙니다.

## 저장한 설계를 다시 편집하기

템플릿을 선택하고 치수·재료를 입력한 뒤 **Save editable design**을 누릅니다.
**Open design**으로 내려받은 JSON을 열면 입력 폼이 복원되어 수정·계산·목표 폭
역산·공차 검토를 계속할 수 있습니다.
[`sipi.template-section/1`](../docs/locales/ko/pages/packages/sipi/template_document.md)은
원래 템플릿 인수와 확정 기하·메시를 함께 보존합니다. 열 때 현재 엔진으로 같은
기하가 재생성되는지 확인하며, 불일치하거나 지원하지 않는 파일은 현재 설계를
바꾸지 않고 거부합니다.

폼은 microstrip, stripline, coupled microstrip, grounded coplanar, planar coated
microstrip 5종입니다. 나머지 엔진 템플릿은 **Saved analysis**를 이용합니다.
임의 기하에서 치수 폼을 추정하지 않습니다. **Export geometry**는 기존 단면 JSON을
내려받으며, 이 기하 파일을 다시 열면 기하·메시는 보존하지만 치수 편집은 켜지지 않습니다.

표시 단위를 바꾸어도 저장된 SI 입력을 반올림하지 않습니다. 수정하지 않은 인수와
화면에 없는 air height·box width 등은 그대로 유지합니다. 필드를 수정하면 표시된
결과를 무효화합니다. 목표 역산이 성공하면 실제 반환된 폭과 메시를 저장합니다.
다시 연 설계를 수정해도 저장된 메시가 유지되므로 바뀐 기하의 메시·외곽 수렴을
별도로 확인해야 합니다. 다른 템플릿을 선택하면 기본 설정으로 새 설계를 시작합니다.
편집 설계 파일에는 입력만 들어가며 결과·목표 범위·공차 설정·A/B 프로젝트 이력은
포함하지 않습니다.

고정 엔진의 등록 입력은 109종입니다. 등록·정규화가 모든 계산의 브라우저 적합성,
작업 한도 충족 또는 독립 정확도 검증을 뜻하지 않습니다. 편집 경로는 native와
Worker의 공통 어댑터를 사용하지만 실제 고정 엔진·자산으로 플랫폼별 검증해야 합니다.
핀 변경만으로 Windows나 Worker 통과를 주장하지 않습니다.

## A/B 단면 입력을 프로젝트로 유지하기

**Duplicate design**을 누르면 현재 단면을 보존하고 복사본을 수정할 수 있습니다.
**Current design**으로 전환할 때 떠나는 설계의 변경 입력을 유지합니다.
**Design name**은 이름을 바꿉니다. 템플릿 선택이나 편집 설계 열기는 현재 변형의
단면을 바꿉니다.

**Save input project**는 `sipi-project.json`을 내려받습니다. **Open project**는
첫 설계를 복원하며 선택 목록으로 다른 설계를 엽니다. 입력 검사만 수행하고 자동
계산하지 않습니다. 표시 단위를 바꿔도 원래 SI 값·숨은 템플릿 설정·확정 메시를
유지합니다. 계산·역산은 각각 모델 및 수렴 기준을 별도로 만족해야 합니다.

프로젝트에는 단면 기하·재료·메시를 저장합니다. 목표 범위·공차 옵션·주파수 응답
설정과 화면에서 새로 계산한 결과는 추가하지 않습니다. 기존 파일에 검증된 결과
기록이 있으면 보존하지만 입력 변경 시 현재 선택을 해제하고 복제본은 빈 이력으로
시작합니다. 이전 기록을 새로 계산한 결과처럼 표시하지 않습니다.

모든 설계가 현재 편집 폼 5종 중 하나여야 합니다. 지원 외 입력·손상된 프로젝트·
200 KiB 초과 파일은 현재 프로젝트를 바꾸지 않고 거부합니다. 인코딩한 요청 한도는
256 KiB이며 초과 수정은 잘라내지 않고 거부합니다. 기하만 담은 파일은 활성 편집
프로젝트 설계를 대체하지 못합니다. 편집 설계나 별도 작업창을 사용하세요. 취소는
대기 중인 파일 읽기와 늦은 응답도 무효화합니다. 내려받기 전 프로젝트는 이 탭에만
있으며 자동 파일 저장·복구·클라우드 저장은 제공하지 않습니다. 오류 후 입력을
고쳐 재시도하거나 저장한 프로젝트를 다시 열 수 있습니다.

## 소스 실행

설치한 개발 SIPI wheel에도 이 로컬 UI와 어댑터가 들어갑니다. `sipi` 또는
`sipi gui`로 실행하고, URL만 표시하려면 `sipi gui --no-browser`를 사용합니다.
[설치 UI 안내](../docs/locales/ko/pages/packages/sipi/local_ui.md)를 참고합니다.
wheel 빌드가 같은 원본을 복사하며 브라우저·외부 런타임을 번들하지 않습니다.
소스·editable 체크아웃은 아래 직접 실행기를 계속 사용할 수 있습니다.

`packaging/engine-ref.txt`의 SIPI와 해당 엔진 `dependencies.json`에 고정한
galerkin·meshine을 설치하고 `packaging/requirements-windows.txt`의 수치 패키지를
사용합니다. 다른 editable 소스 경로가 설치본을 가리지 않도록 합니다.

```sh
python workbench/desktop/main.py
```

임의의 localhost 포트를 열어 기본 브라우저를 실행합니다. 세션 토큰은
URL fragment/세션 저장소에 보관하며 Host·Origin·API 토큰을 검사합니다.
호스팅용 서버가 아닙니다. **Exit**으로 종료하며 탭을 닫는 것만으로 서버가
종료되지는 않습니다. 자동화에서는 `--no-browser`로 로컬 URL만 출력합니다.
요청은 256 KiB, 저장 입력은 200 KiB, 공차/역산은 128회 평가, 작업은 5분으로
제한합니다. 전체 메모리·출력 크기 제한을 보장하는 것은 아닙니다. 취소하면
계산 프로세스 또는 Worker를 중단합니다.

## 로컬 Worker 준비·검증

엔진·공유 패키지의 정확한 고정 커밋에서 깨끗한 체크아웃을 준비하고
setuptools/wheel을 설치합니다. 준비 단계는 공식 자산 다운로드가 필요합니다.
archive/lock 해시, 자체 wheel, 고지·출처·런타임 목록을 보존하며 새 출력 폴더를
사용합니다.

Git attributes로 Windows에서도 원본 고지의 바이트를 보존합니다. 고지 원문이나
해시 검사 기준을 바꿔 불일치를 감추지 않습니다.

```sh
python workbench/packaging/browser.py --engine ENGINE_CHECKOUT --shared SHARED_CHECKOUT --output .validation/web
python -m pytest -q workbench/tests
node --test workbench/tests/*.test.mjs
node workbench/tests/browser.mjs .validation/basic-native
node workbench/tests/saved-browser.mjs .validation/saved-native
node workbench/tests/browser.mjs .validation/basic-worker .validation/web
node workbench/tests/saved-browser.mjs .validation/saved-worker .validation/web
```

실제 브라우저 시험에는 Chromium/Chrome과 WebSocket을 지원하는 Node가 필요합니다.
`SIPI_PYTHON`·`CHROME`으로 실행 파일을 선택할 수 있습니다. 준비 후 시험에서는
계산 자산을 로컬에서 읽습니다. 재배포 검토가 끝나기 전에는 준비된 제3자 바이너리를
공개 호스팅에 복사하지 않습니다. 이 후보에는 호스팅·라우팅 변경이 없습니다.

화면 동작 수락과 수치 일치는 별개입니다. Native와 Worker의 SciPy·Shapely·GEOS가
다릅니다. 타원 쌍 사례에서 native 메시 996점/1754삼각형, Worker 995점/1752삼각형으로
C0 norm 차이가 약 1.03e-5였습니다. CODATA 2022 고정 이후 동일 메시를 재사용한
검증 사례의 정전용량·표면 응답 상대 차이는 1.14e-15 이내였습니다. 모든 재메시·결과의
점별 일치를 뜻하지 않으며 기존 허용 오차는 유지합니다. 엔진의 물리 모델 범위도
유지합니다. 국소 개구 정전용량은 완전한 3D 전이 모델이 아닙니다.

## Windows 후보 검증

topic 전용 `workbench-candidate.yml`은 정확한 자체 wheel 설치·adapter 검증·설치 파일
대조 후 CPython 3.13.17/Nuitka 2.8.10/설치된 Visual Studio 2022로 빌드합니다.
보고서·고지만 업로드하고 EXE·제3자 런타임 바이너리는 업로드하지 않습니다.
독립 및 SciPy 내부의 NumPy 호환 계층은 FFT·선형대수 모듈을 동적으로 불러옵니다.
고정 빌드는 이 4개 모듈을 명시적으로 포함하고 설치본 동작과 완료된 컴파일 보고서의
실제 포함 여부를 검사합니다. 포함 검사만으로 EXE 실행을 통과했다고 판단하지 않습니다.
같은 준비를 마친 Windows 환경의 명령은 다음과 같습니다.

```sh
python workbench/packaging/windows.py
python workbench/packaging/smoke.py .validation/sipi-windows/FieldAlgo-SIPI.exe
```

`inventory.json`에는 정확 버전·컴파일러·wheel 해시·native 파일·실제 EXE 용량/해시가
기록됩니다. `build-info.json`은 내장되어 계산 결과에도 들어갑니다. `smoke.json`은
한글·공백 경로의 첫 실행·계산·종료·임시파일 정리를 측정하고 실패 시 실패 보고서를
남깁니다.
로컬 URL을 출력하기 전에 종료되어도 stdout/stderr를 크기 제한·세션 토큰 가림과
함께 보존합니다.
`--no-browser` 시험이므로 Windows 10/11의 대화형 기본 브라우저 실행,
망 차단 검증, 서명과 전체 native/static 재배포 검토는 별도 관문입니다.
단일 EXE 목표를 ZIP·온라인 런처로 대체하지 않습니다.

[의존성 버전·조건](THIRD_PARTY.ko.md)을 참고하세요.
