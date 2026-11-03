# 개발

SIPI는 외부 설치된 galerkin·meshine을 사용합니다. 공동 개발 시 dependencies.json의
커밋으로 만든 휠을 설치하고 `python -m pip install --no-deps .`로 SIPI를 설치합니다.
이 커밋은 개발 기준선이며 PyPI 게시 완료를 의미하지 않습니다.

`python -m pytest -q`로 소스 시험을 실행합니다. 휠을 만들어 별도 환경에 설치한 뒤
시험을 체크아웃 밖으로 복사해 동일한 전체 시험을 실행합니다. 독립 네트워크 비교에는
scikit-rf 2.2.0이 필요합니다. 기하 계약은 해당 simcase reader와 함께
`integration/test_geometry_adapters.py`를 명시적으로 실행합니다.

provenance.json은 이전한 파일과 원본 SHA-256을 기록합니다. 수치 구현·기준값은
변경하지 않았습니다. 원본 이력은 기록된 상류 커밋에 남으며 새 저장소는 출처가 있는
스냅샷으로 시작합니다. 이번 이전은 웹 배포·Windows EXE 생성·새 플랫폼 지원을 뜻하지 않습니다.
