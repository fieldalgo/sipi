# 격리된 메시 후보 진단

원본 meshine과 scalar 길이 계산 4곳을 바꾼 후보를 비교하는 비배포 개발
진단입니다. `dependencies.json`은 그대로입니다. `manifest.json`에 정확한
상류 커밋, 패키지·시험 파일 해시, 검토용 patch, 후보 소스, 입력과 runtime
기준값을 기록합니다. 다른 커밋·변경된 바이트·기존 출력 경로는 거부하고,
검증한 파일만 복사합니다. 상류 checkout은 편집하지 않습니다.

후보는 `_treated_apices`, `_lattice_point`의 scalar 2D 길이를 `math.hypot`으로
계산합니다. 이전 관측에서 동일 벡터의 `numpy.linalg.norm` 마지막 비트 차이가
작은각 격자점과 후속 세분을 바꿨습니다. 좌표 반올림·수치 기준은 바꾸지
않습니다. 사각 동박의 macOS 도체 수렴 실패와는 별개입니다.

## 실행

manifest의 정확한 상류 커밋 checkout에서 별도의 새 사본을 준비합니다.

```sh
python tools/mesh_diagnostics/run.py prepare UPSTREAM_CHECKOUT ORIGINAL_COPY original
python tools/mesh_diagnostics/run.py prepare UPSTREAM_CHECKOUT CANDIDATE_COPY candidate
```

`COPY/packages/meshine`에서 wheel을 빌드할 때 `OPENPHYSICS_DOCS_REF`를 manifest
커밋으로, `GIT_CEILING_DIRECTORIES`를 복사 경로의 절대경로로 지정합니다.
문서 링크가 상류 패키지 경로를 사용하게 하며 Apache-2.0 LICENSE·NOTICE를
보존합니다. 다른 공유 wheel은 원본 상류에서, SIPI는 독립 저장소에서
빌드합니다. 각 변형을 별도 환경에 설치하고 `tools/verify_install.py`로 정확한
payload를 검사합니다. `PYTHONPATH`는 비우고 버전 문자열만으로 식별하지 않습니다.

복사된 `tests/meshine`의 기존 2D 시험 6개(manifest 지정)를 실행한 뒤,
해당 설치 환경으로 probe를 실행합니다. BLAS/OpenMP thread는 하나로 제한하고
출력은 새 경로를 사용합니다.

```sh
python tools/mesh_diagnostics/run.py probe original ORIGINAL_REPORT
python tools/mesh_diagnostics/run.py probe candidate CANDIDATE_REPORT
```

`Mesh candidate diagnostics` workflow는 Linux·macOS·Windows에서 원본·후보를
별도 job으로 검사합니다. SIPI commit/tree, 상류 커밋, 소스·wheel 해시와
라이브러리 버전을 기록합니다. NumPy 2.5.4, SciPy 1.18.1, Shapely 2.2.0을 사용하며
기존 wheel을 설치할 뿐 패키지·EXE·사이트를 게시하지 않습니다.
도구 회귀는 `python -m pytest -q tools/tests`입니다.

## 근거 해석

기존 저장 공차 9개 단면의 폭 표본 2개씩과 원 쌍 도체 coarse/fine까지 총
20회를 계산합니다. 완료한 사례는 다음 사례 전에 저장합니다. 오류 시 완료
목록·현재 입력·부분 trace를 남기고 기존 JSON/NPZ를 덮어쓰지 않습니다.
관측 hook은 성공·실패 모두 복원됩니다. thread-safe하지 않으므로 새 단일
프로세스에서만 사용하고 실행 중인 앱에 적용하지 않습니다.

`reference.json`은 정확한 소스 버전·환경과 함께 원래 native 임피던스 18개를
보존합니다. 각 값에 기존 runtime 상대 **1e-9**를 적용합니다. 이는 재현성
검사이지 독립 물리 정확도 기준이 아닙니다. 20회 계산 후 비교하며, 실패는
`comparison.json`·`failure.json`과 실패 종료 코드로 남깁니다. 통과를 위해
기준값을 재생성하거나 기하를 바꾸지 않습니다.

실제 Domain.build의 점·선분·영역, 첫 Delaunay 입력·삼각형, 후속 호출 해시·shape,
triangle-data 해시, 작은각 격자 단위, 최종 메시와 C/C0/C_loss/L을 기록합니다.
도체 NPZ 두 개는 실제 진공 표면전류 입력이며
`numpy.load(path, allow_pickle=False)`로 읽습니다. 행렬·도체 계수는 관측값으로,
원래의 수치·수렴 기준을 대체하지 않습니다.

동일 사례·단계를 비교합니다. 노드 해시 차이만으로 물리 오차를 판정하거나
임피던스 일치만으로 동일 메시라 하지 않습니다. 3D 세분·임의 기하·재료·도체
손실·실행파일 배포는 수락 범위 밖입니다. 원 macOS 도체 5% 기준과 미수락
브라우저 실패는 별개이며 진단 통과가 제품 pin 변경이나 UI 수락을 뜻하지 않습니다.

[English](README.md)
