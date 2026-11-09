# 설치 런타임 파일 snapshot

`sipi._workbench.artifacts.capture_installed_artifacts()`는 실제 설치된 SIPI,
galerkin, meshine, NumPy, SciPy, Shapely, array-api-compat 파일 목록을 수집한다.
정규 `manifest_text`와 기록에 사용할 `kind=runtime`인 `artifacts` 선언을 반환한다.
계산 UI 변경·결과 연결·파일 쓰기는 하지 않는다. 브라우저와 EXE 출처는 별도
호스트 경로가 필요하며 이 helper에는 파일을 검사할 수 있는 설치본이 필요하다.

각 `sipi.installed-component/1` manifest는 component/version,
`policy=distribution-files/1`, 상대 import 경로와 정렬한 파일 목록(path, byte 수,
실제 SHA-256)을 담는다. 키를 정렬한 compact JSON을 Unicode 그대로 UTF-8로
인코딩한 SHA-256이 선언 digest다. 전체 `sipi.installed-runtime/1`에는 참고용
Python 버전·OS·machine도 있다. 이 표시는 바이너리 식별값이나 component digest가 아니다.

배포물 파일 목록에서 bytecode·`__pycache__`·dist-info의 설치 관리 파일
(`RECORD`, `INSTALLER`, `REQUESTED`, `direct_url.json`)·배포물 root 밖 경로의
script를 제외한다. 포함한 metadata·license·Python·등록된 데이터·번들 native
library의 실제 byte를 해시한다. 절대/비정상/중복 경로·누락 파일·설치본을 가린
소스 import·미등록 package module은 거부한다. package 탐색은 `.py`, `.so`,
`.pyd`, `.dll`, `.dylib`를 검사하며 모든 미등록 데이터나 외부 library를 찾는다는
의미는 아니다.

기본 한도는 제외 항목을 포함한 배포물 목록 20000개, import package당 탐색 경로
20000개, 포함 파일 전체 512 MiB다. 두 설정값은 양의 정수여야 한다. 파일을
stream으로 읽고 전후 크기·파일 식별값·timestamp를 검사한다. 관찰한 읽기 중
변경을 거부하지만 원자적 filesystem snapshot이나 메모리 실행 인증은 아니다.

실제 파일 식별값이며 **원본 wheel 해시**, 서명, 독립 출처 감사, 물리 정확도 근거,
Python/OS library 전체 목록이 아니다. 기록 출처는 `host-declared`로 유지한다.
향후 기록과 함께 원문 manifest를 보관해야 digest의 범위를 검토할 수 있다.

빌드한 wheel을 설치하고 소스 저장소 밖에서 실행한다.

```python
import json
from sipi._workbench.artifacts import capture_installed_artifacts

snapshot = capture_installed_artifacts()
manifest = json.loads(snapshot['manifest_text'])
assert len(manifest['components']) == len(snapshot['artifacts']) == 7
assert {row['kind'] for row in snapshot['artifacts']} == {'runtime'}
```

[프로젝트 기록](PROJECTS.ko.md) · [English](ARTIFACTS.md)
