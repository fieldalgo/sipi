# 명시적 로컬 프로젝트 파일

[English](../../../../../packages/sipi/project_io.md) · [프로젝트 내용](project.md) · [실행 결과](execution_record.md)

`sipi.project_io`는 로컬 호스트에서 명시적으로 호출하는 파일 읽기·저장을
제공합니다. 순수 프로젝트와 계산 모듈은 파일에 자동 접근하지 않습니다.
읽기·저장은 계산·서버 시작·설계 업로드를 수행하지 않습니다.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from sipi import LumpedNetworkDocument
from sipi.execution_request import SavedExecutionRequest
from sipi.project import SavedProject
from sipi.project_io import read_project, save_project

request = SavedExecutionRequest(LumpedNetworkDocument([0, 1e9], resistance=10).dumps())
project = SavedProject(request, project_id='demo:project', design_id='a',
                       title='Resistor comparison', label='Baseline')
with TemporaryDirectory() as directory:
    path = Path(directory) / 'comparison.json'
    created = save_project(path, project)  # create only; never overwrite an existing file
    loaded = read_project(path)
    assert loaded.file_sha256 == created.file_sha256
    assert loaded.project.dumps() == project.dumps()
    changed = loaded.project.duplicate_design('a', 'b', 'Alternative')
    replaced = save_project(path, changed, expected_sha256=loaded.file_sha256)
    reopened = read_project(path)
    assert reopened.project.design_ids == ('a', 'b')
    assert reopened.file_sha256 == replaced.file_sha256
```

`read_project`는 `project`와 `file_sha256`을 가진 불변 `LoadedProject`를
반환합니다. 이 해시는 공백을 포함한 **파일 원바이트**를 식별하며 프로젝트
내부 내용 체크섬과 다릅니다. 교체할 때는 이전에 읽은 이 정확한 해시가
필요합니다. 기본 `expected_sha256=None`은 새 파일 생성만 허용하고 기존
파일은 거부합니다. 저장 결과는 `ProjectSaveReceipt(file_sha256,
directory_synced)`입니다.

```python
from sipi.project_io import ProjectConflictError

with TemporaryDirectory() as directory:
    path = Path(directory) / 'comparison.json'
    save_project(path, project)
    old = read_project(path)
    newer = old.project.duplicate_design('a', 'b', 'Alternative')
    save_project(path, newer, expected_sha256=old.file_sha256)
    conflict_detected = False
    try:
        save_project(path, project, expected_sha256=old.file_sha256)
    except ProjectConflictError:
        conflict_detected = True  # reload/compare; never blindly retry as an overwrite
    assert conflict_detected
    assert read_project(path).project.dumps() == newer.dumps()
```

## 파일 공개와 충돌 경계

부모 디렉터리는 이미 존재해야 합니다. 해석한 부모 경로와 정규화한 파일
이름으로 같은 디렉터리의 배타 잠금을 정합니다. 잠금이 있으면
`ProjectBusyError`를 내며 `lock_path`로 호스트가 잠금 위치를 확인할 수
있습니다. 기다리거나 잠금을 강탈하거나 다른 작성자의 잠금을 지우지 않습니다.
최종 대상은 일반 파일이어야 하며 심볼릭 링크·디렉터리·특수 파일을 허용하지
않습니다. UTF-8 디코딩과 프로젝트 검증 전에 읽을 바이트 수를 제한합니다.

쓰기에 앞서 후보를 검증합니다. 같은 디렉터리에 고유한 임시 파일을 만들고
완전한 정규 UTF-8 내용을 쓰고 flush·파일 fsync를 수행한 뒤 공개합니다.
생성은 기존 대상을 덮어쓸 수 없는 hard link를 쓰며, 교체는 협력 잠금 아래
원바이트 해시를 확인하고 `os.replace`를 호출합니다. 이후 자기 임시 파일과
잠금만 정리합니다. 파일시스템이 이 연산을 지원하지 않아도 기존 파일을
잘라내거나 그 자리에 직접 쓰는 방식으로 바꾸지 않습니다.

동일하게 해석한 경로를 쓰는 협력 작성자를 직렬화합니다. 잠금을 무시하는
다른 프로그램에 대한 원자적 compare-and-swap은 아닙니다. 파일시스템 별칭,
다른 주체의 디렉터리 변경, 읽기·교체 중 외부 쓰기는 보장 밖입니다. 같은 내용
해시는 증가하는 편집 revision도 서명도 아닙니다. 열린 파일의 소유권·현재
실행·충돌 시 사용자 선택은 호스트가 관리해야 합니다.

POSIX에서는 공개·정리 후 부모 디렉터리도 sync하고
`directory_synced=True`를 반환합니다. 다른 시스템은 `False`를 반환하며,
이는 파일 fsync 실패를 뜻하거나 디렉터리 내구성을 보증하는 값이 아닙니다.
생성·교체 파일은 임시 파일의 비공개 권한, **POSIX에서 0600**을 사용합니다.
이전 권한·ACL·확장 속성은 복사하지 않습니다. 저장 내용은 정규 프로젝트
JSON이므로 이전 파일의 공백 표기는 유지하지 않습니다.

## 실패와 복구

- `FileExistsError`: 생성 전용 모드에서 기존 파일이나 경합 중 외부 생성 파일을
  발견했습니다. 덮어쓰지 않았습니다.
- `FileNotFoundError`: 필요한 부모나 교체 대상이 없습니다.
- `ProjectConflictError`: 교체하려는 원바이트가 이전에 읽은 버전과 다릅니다.
  메모리·디스크 버전을 모두 보존하고 다시 읽어 비교한 뒤 결정해야 합니다.
- `ProjectBusyError`: 협력 잠금이 있습니다. 활성 잠금을 지우면 안 됩니다.
  충돌 종료 뒤에도 먼저 실행 중 작성자가 없음을 확인해야 합니다.
- `ProjectSaveError`: `published`를 확인합니다. `False`면 이번 호출이 후보를
  공개하지 않았습니다. `True`면 완전한 후보 공개 후 sync·정리에서 실패한
  것이므로 **대상을 다시 열어** `file_sha256`과 비교해야 합니다. 이전 내용이
  남았다고 가정하거나 자동으로 되돌리면 안 됩니다. `cleanup_errors`에는 정리
  실패가, 예외 원인에는 I/O 오류가 남습니다.

프로세스 강제 종료나 시스템 충돌은 임시 파일·오래된 잠금을 남길 수 있습니다.
API는 임시 파일을 승격하거나 잠금을 자동 제거하거나 백업을 순환시키거나
자동 복구하지 않습니다. 호스트는 후보·원본을 보존하고 명시적으로 확인해야
합니다. sync 성공은 하드웨어 고장·전원 손실·원격 파일시스템 내구성의 증명이
아닙니다.

읽기 기본 cap은 16 MiB이고 `max_project_bytes`로 1바이트부터 64 MiB까지
지정할 수 있습니다. 교체 비교에서도 이전 원바이트를 64 MiB로 제한합니다.
미지원 버전·손상된 체크섬·비 UTF-8·잘못된 구조는 원파일을 다시 쓰지 않고
거부합니다. 후보는 프로젝트 스냅샷 자체의 cap을 유지합니다.

```sh
python -m pytest -q tests/sipi/test_project_io.py tests/sipi/test_project.py tests/sipi/test_execution_record.py
```

현재 검증 범위는 **Linux 로컬 파일시스템**입니다. Unicode 경로, 정확한
저장·복원, 두 프로세스 경합, 원바이트 충돌, 덮어쓰기 없는 생성, 공개 전
실패, 공개 후 sync·정리 실패, 완전한 재열기를 확인합니다. Windows/macOS,
브라우저 다운로드, 네트워크 파일시스템, 실제 사용자 충돌 복구는 수락하지
않았습니다. 새 서드파티 런타임 의존성은 없습니다.
