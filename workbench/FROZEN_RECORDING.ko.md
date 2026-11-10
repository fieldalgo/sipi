# Windows 단일 EXE 후보의 계산 기록

후보의 컴파일된 host는 `saved-record`를 풀린 번들 전용 provider로 연결한다.
[설치본·브라우저 host](RECORDING.ko.md)와 같은 입력·receipt·기록·프로젝트 계약을
사용한다. 클라이언트 JSON에서 runtime 경로, 배포물 선언, provider를 지정할 수 없다.
다른 계산의 동작은 유지한다.

Windows x64, CPython 3.13.17, Nuitka 2.8.10 standalone/onefile 표시, 명시적인
`--onefile-no-dll` 빌드와 실제 실행 payload 옆의 helper가 필요하다. Windows의
임시 onefile은 기본적으로 DLL payload를 쓰며 프로세스 실행파일은 외부 launcher다.
그 모드는 이 기록 계약을 충족하지 않는다. 검토한 EXE payload 모드의 `sys.executable`은 풀린 실행파일을
가리킨다. 외부 launcher를 가리킬 수 있는 `argv[0]`, `__compiled__.containing_dir`는
사용하지 않는다. helper는 payload 안에 컴파일되므로 검사 가능한 Python 원본 파일이나
설치 wheel 목록은 요구하지 않는다.

저장 계산을 정확히 한 번 실행하기 전후에 해당 디렉터리의 모든 일반 파일을 hash한다.
실행파일, native 라이브러리, UI, 빌드 정보, 고지가 포함된다. 링크/reparse point,
일반 파일이 아닌 항목, 필수 파일 누락, snapshot 변화를 거부한다. 한도는 디렉터리
항목 20,000개, 파일 합계 512 MiB, 경로 64단계/상대 경로당 1,024글자,
빌드 정보 1 MiB, 생성 manifest 8 MiB다. 읽기 크기를 제한하고 파일별 hash 전후
파일 식별자·크기·시간을 확인한다. 목록은 정렬된 상대 경로만 사용하며 설치 경로는 넣지 않는다.

원문 `sipi.frozen-runtime/1` 환경 manifest는 `unpacked-bundle-files/1` 선택 정책,
실제 파일 크기/hash, 실행 payload 이름, runtime 버전, 내장 빌드 정보를 담는다.
빌드 정보의 source-wheel hash는 빌드 입력을 설명한다. 컴파일된 payload를 원본
wheel이라고 선언하지 않는다. 기록의 배포물 항목은 다음과 같다.

- `sipi`, kind `executable`: 실제 풀린 실행파일의 SHA-256.
- `sipi-frozen-runtime`, kind `runtime`: 기록과 함께 반환한 정확 UTF-8 환경
  manifest의 SHA-256.

이는 `host-declared` 파일 식별이다. 서명, 신뢰된 게시자 증명, 실행 메모리 인증,
원자적 filesystem snapshot이 아니다. 번들 밖의 시스템 DLL은 제외한다. 압축된
외부 EXE는 hash가 다르며 패키징 inventory와 외부 smoke 보고서에서 별도로 식별한다.
Hash 일치는 수치·실측 물리 정확도를 증명하지 않는다. 기존 기록 크기, 실패/불완전
결과, 취소, 명시적 프로젝트 선택 규칙은 유지한다. 프로젝트·기록 자동 저장은 없다.

## 수락 범위

`workbench/tests/test_frozen_recording.py`는 합성 번들의 경계, 파일 변화,
기록/프로젝트 왕복, 독립 smoke 검사를 시험한다. 합성 파일은 Windows 실행 근거가
아니다. 실제 Windows 빌드도 `workbench/packaging/smoke.py`를 통과해야 한다.
spawn 계산 worker에서 기록을 두 번 실행하여 같은 요청/receipt와 서로 다른 실행 ID,
살아 있는 추출 파일의 독립 hash 대조, 원문 프로젝트 추가/조회, 정상 종료,
추출 디렉터리 비움을 확인한다. 실패 보고서를 보존하며 해당 정확 커밋과 EXE의
시험을 통과한 뒤에만 Windows 수락으로 표시한다.

실패 시 smoke는 먼저 정상 종료를 요청하고 필요하면 자신이 시작한 프로세스 트리만
종료한다. 정리 오류가 최초 실패를 덮어쓰지 않도록 둘 다 기록한다. 나머지 검증이
성공했더라도 정리에서 오류가 나면 전체 smoke는 실패다.

검토된 패키징/runtime 버전과 고지는 유지한다. 이 기능은 별도의 native/static
재배포, Windows 10/11 대화형 실행, 망 차단, 서명 관문을 해소하지 않는다.
EXE에 브라우저 엔진을 추가하지 않는다.

[English](FROZEN_RECORDING.md)
