# 브라우저 배포 원본을 연결한 기록

Worker는 [native 기록](RECORDING.ko.md)과 같은 `saved-record` 요청 및 원문
기록/프로젝트 전달을 지원한다. 출처는 설치 파일 snapshot 대신 Pyodide에 불러온
검사된 배포 원본을 설명한다. 자동 결과 이력 UI는 이 전달 계약과 별도다.

초기화 시 계산 runtime을 불러오기 전에 staged manifest의 모든 파일에 대해
상대 경로·크기·SHA-256을 확인한다. 최대 128개 파일, 파일당 64 MiB,
전체 128 MiB, manifest 1 MiB다. wheel과 Python helper는 검사한 byte에서
풀거나 쓴다. runtime 파일은 검사 후 일반 Pyodide loader가 staged URL에서 읽는다.
원자적인 네트워크 로드·실행 메모리 인증·서명·서버 신원 입증은 아니며 manifest는
호스트 선언이다.

검토 runtime은 수정하지 않은 Pyodide 0.29.5/Python 3.13.2, ABI
2025_0/wasm32/emscripten_4_0_9, NumPy 2.2.5, SciPy 1.14.1, Shapely 2.0.7,
array-api-compat 1.16.0이다. SIPI 0.1.0과 galerkin/meshine 0.0.2 원본 wheel은
해시와 전체 engine/shared commit으로 식별한다. 개발 버전명만으로는 부족하다.
기존 라이선스·고지·재배포 검토 범위를 유지하며 native 앱에 브라우저 엔진을 넣지 않는다.

`BrowserSourceRecorder`는 원본 manifest, 로드한 배포물 버전, 실제 helper byte를
검사한다. 로딩 호스트가 불변 provider를 만들며 사용자 작업 JSON으로 provider나
출처 선언을 주입할 수 없다. 기록에는 7개 원본 wheel 해시와 원문 manifest의
SHA-256을 `sipi-browser-runtime`/`runtime`으로 선언한다. manifest는 runtime,
helper, wheel, 고지의 해시를 연결하므로 기록을 내보낼 때 원문도 보존한다.
`host-declared`를 독립 출처 인증이나 정확도 근거로 바꾸지 않는다.

각 요청은 기존 불변 입력을 한 번 실행하고 전후 helper byte를 확인해 원문
`record_text`와 `runtime_manifest_text`를 반환한다. 같은 입력의 재실행도 새 ID로
구분한다. 입력/기록 한도, 실패·불완전 receipt, 취소, 과거 프로젝트 결과 선택
조건은 유지한다. JavaScript는 숫자를 재직렬화하지 말고 기록 원문을 보존한다.
Worker 오류 시 서버 계산으로 전환하지 않는다. EXE의 기록에는 별도 출처 경로가 필요하다.

기존 staging 명령은 canonical Python helper 4개도 포함한다. 새 stage를 사용하고
정확한 engine/shared pin과 고지 목록을 유지한다. 기존 브라우저·저장 분석 검사와
함께 다음 실제 기록 전달 검사를 실행한다.

```sh
node workbench/tests/record-browser.mjs .validation/record-native
node workbench/tests/record-browser.mjs .validation/record-worker .validation/web
```

첫 명령의 `SIPI_PYTHON`은 현재 빌드 wheel 설치본을 가리켜야 하며 호스트는 저장소
밖에서 시작한다. 정상 stage는 보존하고 별도 복사본의 helper/runtime byte나
경로를 의도적으로 바꾼 뒤 `--expect-integrity-error`를 추가하면 무결성 거부를
검사한다. 실제 브라우저 전달 검사이며 새 결과 이력 화면이 있다는 의미는 아니다.

[English](BROWSER_RECORDING.md)
