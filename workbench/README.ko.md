# SIPI workbench 후보

[English](README.md)

독립 설치한 SIPI 엔진을 기본 브라우저의 로컬 화면 또는 브라우저 Worker에서
실행하는 소스 후보입니다. 출시된 앱은 아닙니다. Windows x64는 설치 없는
단일 EXE가 목표이며 Python·엔진·화면을 포함하고 별도 브라우저 엔진이나
원격 계산 서비스를 포함하지 않습니다. 실제 용량과 Windows 동작은 성공한
Windows 빌드·실행 보고서로 확인해야 합니다. wheel 크기는 EXE 크기가 아닙니다.

기본 화면은 단면 입력 폼 5종, 메시 설정, 목표 임피던스, 공차 샘플,
단면 JSON 저장과 선로·회로 결과를 제공합니다. **Saved analysis**에서는
[`sipi.execution`](../docs/locales/ko/pages/packages/sipi/execution.md)에 등록한
20개 버전 계약의 원문 JSON을 열고 검증·정규 저장·실행·결과 내보내기를 합니다.
실패한 공차 행과 목표 역산 이력도 보존하며 불완전한 공차 결과의 요약은
계산하지 않습니다. 선택한 특성/모드 진단이 실패해도 기본 선로 결과는 남습니다.
입력 변경·취소 시 기존 결과의 표시·내보내기를 무효화합니다. 모든 계약의
전용 입력 폼까지 구현한 것은 아닙니다.

## 소스 실행

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
