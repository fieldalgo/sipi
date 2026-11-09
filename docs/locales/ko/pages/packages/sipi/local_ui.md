# 설치된 로컬 작업 화면

[English](../../../../../packages/sipi/local_ui.md)

검증한 개발 SIPI wheel과 대응 의존성을 설치한 뒤 `sipi`를 실행합니다. 같은 단면
작업 화면이 기본 브라우저에 열리고 계산은 PC 안에서 수행됩니다. 소스 체크아웃,
계정·업로드·서버 프레임워크는 필요하지 않습니다. 개발 후보이며 PyPI 출시 안내가 아닙니다.

```sh
sipi
```

`sipi gui`도 같습니다. 브라우저를 자동으로 열지 않고 URL을 표시하려면 다음과 같이 실행합니다.

```sh
sipi gui --no-browser --port 0
```

포트 0은 사용 가능한 loopback 포트를 고릅니다. 명시 포트는 0..65535이며 URL의
세션 토큰이 필요합니다. 화면의 **Exit** 또는 실행한 터미널의 Ctrl+C로 로컬 서버와
계산 프로세스를 종료합니다. 브라우저 탭만 닫으면 서버가 종료되지 않습니다.
정상 종료 코드는 0, 시작 실패는 1입니다. `--help`, `--version`은 호스트를 시작하지
않습니다. `sipi run`, `sipi validate`는 [화면 없는 명령](cli.md)으로 유지됩니다.

기존 폼 5종에서 치수·재료를 입력하고 계산·목표 폭 역산·공차 검토를 수행합니다.
**Save editable design**은 템플릿 입력과 확정 메시를 저장하고 **Open design**으로
필드를 복원합니다. **Export geometry**는 기존 기하 JSON 동작을 유지합니다.
**Saved analysis**는 전용 폼이 없는 계산에도 공통 버전 입력 엔진을 사용합니다.
모델 범위·실패 행·취소·오래된 결과 무효화·내보내기는
[workbench 안내](../../../../../../workbench/README.ko.md)를 참고합니다.
입력 프로젝트에서 단면을 복제·전환하고 저장한 입력을 다시 엽니다. 이 화면은 새
결과 이력을 저장하지 않습니다. 입력 재열기가 수렴을 보증하는 것은 아닙니다.

wheel에는 빌드 때 같은 원본에서 복사한 자체 호스트·어댑터·UI와 SIPI license/notice,
의존성 사용 고지가 들어갑니다. CPython·Pyodide·브라우저 엔진·외부 native 바이너리는
포함하지 않고 Python 의존성은 별도 배포판으로 설치합니다. 패키지 import로 서버나
브라우저가 시작되지 않습니다. UI 자산을 빌드하지 않은 소스·editable 환경에서는
저장소의 `python workbench/desktop/main.py`를 사용할 수 있습니다.

loopback 한정 바인딩, Host/Origin/token 검사, 별도 계산 프로세스, 명시 취소,
5분 작업 한도를 유지합니다. 공개 웹 서버가 아닙니다. Linux 설치본 브라우저 검증이
Windows/macOS의 대화형 기본 브라우저 지원을 뜻하지 않습니다. Windows 무설치 단일 EXE는
별도 목표로 유지하며 그 사용자는 Python을 미리 설치할 필요가 없습니다.
