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

개발 도구에는 `threadpoolctl==3.6.0`을 설치합니다. BSD-3-Clause 조건에 따라
재배포할 때 저작권·조건·면책문을 보존하고 저작권자의 보증·추천을 주장하지
않습니다. 확인한 패키지에는 번들 native library가 없고 설치 wheel의 라이선스를
보존합니다. 진단·CI 의존성이며 SIPI runtime·EXE 의존성은 아닙니다.
`environment.json`에 NumPy CPU 기능과 실제 BLAS 라이브러리·버전·선택된
아키텍처·thread 수를 기록합니다. 관측기는 CPU 선택·부동소수점 모드·thread
제한을 설정하지 않습니다.

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

첫 triangle-data 호출의 점·삼각형 인덱스·출력 배열 4개와 Delaunay 반복 번호도
보존합니다. 이 배열 그대로 `_triangle_data`를 재생하면 삼각형 차이와 연산
차이를 분리할 수 있습니다. 관측기는 세분에 반환하는 배열을 바꾸지 않습니다.
다음 Delaunay 호출 두 번과 두 번째 triangle-data 호출까지 `snapshot` 배열도
기록하며 원래 행의 해시를 유지합니다. `compare.py`의
`delaunay_snapshot(record, index)` 또는 `triangle_snapshot(record, index)`로
검증해 읽습니다. 옛 기록에 배열이 없으면 `None`을 반환하며 빈 비교를 성공으로
처리하지 않습니다.

전계 풀이를 반복하지 않고 내려받은 두 probe 경로를 비교합니다.

```sh
python tools/mesh_diagnostics/compare.py LEFT_PROBE RIGHT_PROBE NEW_REPORT.json
```

저장 배열의 해시를 확인하고 삼각형 순서와 연결성 차이를 구분합니다. 달라진
내부 변은 기록된 binary64 좌표를 정확한 유리수로 바꿔 방향·incircle 술어를
계산합니다. incircle 행렬식 0은 네 점이 정확히 같은 원 위에 있다는 뜻이며,
전체 삼각분할의 유효성이나 최종 오차 한계를 보장하지 않습니다. 좌표가 다르면
동일 노드 인덱스로 간주하지 않습니다. 양쪽에 첫 triangle-data 배열이 있고
전체 입력 배열이 같을 때만 출력 차이를 측정합니다. 옛 기록에는 배열 부재를
명시하고 기존 보고서는 덮어쓰지 않습니다.

`21624a9`의 진단 run `43549799850`에서 6개 job 모두 기존 메시 시험 265개를
통과했습니다. 임피던스 18개 비교는 Windows 원본·후보와 Linux 후보가 통과했고,
Linux 원본은 1개, macOS 원본·후보는 각각 18개가 기존 1e-9 기준에서 실패했습니다.
후보 Linux/macOS의 20개 초기 좌표는 모두 같았습니다. 첫 연결성이 다른 6개
사례에서 양쪽의 달라진 내부 변 32개는 모두 정확한 incircle 행렬식이 0이었습니다.
나머지 14개는 초기 연결성이 같았고 후속 분기 원인은 아직 분리되지 않았습니다.
이 관측만으로 후보를 수락하거나 후속 차이 전체를 설명하지 않습니다.

원도체의 첫 삼각형만 macOS 기록으로 바꾸고 Linux에서 이어 계산한 실험에서는
두 메시 크기 모두 최종 메시와 도체 값이 원래 Linux와 정확히 같았습니다.
따라서 첫 대각선 선택만으로 최종 플랫폼 차이를 설명할 수 없습니다. macOS의
첫 triangle-data 입력 20개를 Linux에서 재생하면 중심·반지름·무게중심은 같고,
각도만 최대 4.44e-16 rad 달랐습니다. 원 28도 분류는 모두 같았습니다.
후속 세분 분기는 아직 해결되지 않았습니다.

NumPy 2.5.4·OpenBLAS 0.3.34.106.0에서 CPU 계산 경로만 바꾸는 별도 실험으로
scalar 길이 차이를 재현했습니다. 같은 Linux 설치의 SkylakeX·Haswell 경로는
기존 비대칭 unbacked 표본에서 98.87655849123043·98.87641768741268Ω을 반환했고,
격리 후보는 98.87655849123043·98.87655849123048Ω을 반환했습니다.
이는 제어 실험 결과이며 이전 CI의 실제 CPU 경로를 확정하거나 macOS 도체
기준 실패를 해결한 근거가 아닙니다.

동일 사례·단계를 비교합니다. 노드 해시 차이만으로 물리 오차를 판정하거나
임피던스 일치만으로 동일 메시라 하지 않습니다. 3D 세분·임의 기하·재료·도체
손실·실행파일 배포는 수락 범위 밖입니다. 원 macOS 도체 5% 기준과 미수락
브라우저 실패는 별개이며 진단 통과가 제품 pin 변경이나 UI 수락을 뜻하지 않습니다.

[English](README.md)

## 정확한 공원점 연결 실험

`ties.canonical_ties(points, triangles)`는 이미 유효한 비제약 삼각분할을
입력으로 받는 비배포 진단입니다. 정렬된 CCW 삼각형과 flip 수를 반환하며
좌표는 바꾸지 않습니다. 꼭짓점의 좌표 쌍으로 순위를 정하고, 네 binary64 점이
**정확히** 같은 원 위에 있고 사각형이 볼록할 때만 순위가 작은 대각선으로
바꿉니다. Fraction 판정에는 근접 허용값이 없습니다. 매 flip은 순위화된 변의
다중집합을 줄이므로 순환하지 않습니다. 전체 영역 유효성 검사, 내부 제약선
보존, 잘못된 Delaunay 연결 복구는 하지 않습니다. 제품 메셔에서 호출하지
않으며 기존 `legacy`·`stable` 후보 순서 계약도 바꾸지 않습니다.

시험은 사각형의 순서·스케일·이동 288가지, 반지름 5인 정확한 원 위 정수좌표
12점의 fan 60가지, 동률로 취급하면 안 되는 인접 binary64 반례, 멱등성,
외곽·면적 보존과 잘못된 기록 거부를 확인합니다. 일반 삼각분할 정확도나
플랫폼 수렴을 보장하는 검증은 아닙니다.

보존된 `0a7395d` Linux/macOS 후보의 첫 세 단계 60쌍 중 58쌍은 점 집합이
같습니다. 그중 14쌍의 연결이 정규화 전에 달랐고, 실험 후에는 58쌍 모두
정렬된 삼각형이 같습니다. 나머지 두 쌍은 좌표가 달라 동일 입력 비교에서
제외했습니다.

전체 메시 실험은 별도로 실패했습니다. 축정렬 직각삼각형 원중심만 바꾸면
도체 coarse/fine 변화가 0.050451984547489746이며 기존 runtime 비교 18개 중
17개도 실패합니다. 정확 공원점 연결·순서만 Linux의 스칼라 길이 후보에
적용하면 coarse/fine 노드는 19,598/75,121개, 도체 변화는
0.05765770656716615입니다. 둘 다 원래 0.05 기준을 넘습니다. 두 번째 실험의
두 메시 계산은 해당 호스트에서 약 123초였으며 이식 가능한 성능 보증이
아닙니다. 어느 쪽도 제품 수정 수락이나 기존 실패·fixture·기준 교체 근거가
아닙니다.
