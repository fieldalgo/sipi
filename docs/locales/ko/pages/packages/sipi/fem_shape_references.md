# FEM 형상 에너지의 독립 기준 관측값

3·4신호 세분 사례에서 성공했던 독립 이차 전위(P2) 관측값을
`tests/sipi/reference_values/scikit_fem/three_signal_fem_shape.json`과
`four_signal_fem_shape.json`에 보존합니다. 두 기록은 공통
`openphysics.reference-values/1` 형식입니다. reader는 공유 저장소
`625d9f74ca253538f172a42272c869b66d144eed`의 Apache-2.0 구현을 바이트 그대로
사용합니다. 기록에 기준 도구의 코드나 바이너리를 넣지 않습니다.

각 시험은 여전히 제품 P1 전류·두 내부 연장·모든 커패시턴스 유한차분을 실제로
계산합니다. 비용이 큰 독립 P2 풀이만 보존한 관측값과 대조합니다. 원 전체 경계
비교 한계 .01, C0 비교 .001, 기준 자체 검사 1e-10을 유지합니다. 작은 plate/coax/
닫힌 쌍의 5개 live 기준 시험도 그대로입니다. 이전 거친 3신호 C0 실패와 거친/절반
메시 4신호 PSD 실패를 삭제·재분류하거나 수락 fixture로 사용하지 않습니다.

기록을 만들기 전에 비교 전용 계산으로 모든 P2 배열과 자체 검사값이 성공 관측과
완전히 같은지 확인했습니다. 해당 Linux 실행에서 기준 계산은 3신호 16.54초,
4신호 157.15초였습니다. 이는 관측이며 시간 보장이 아닙니다. 4신호는 live 기준 계산
비용 한계를 넘습니다. 과거 기준 생성 비용은 현재 시험 실행과 분리해 저장하고,
저장값을 쓴 시험은 기준 도구를 이번에 실행하지 않았다고 표시합니다.

제품 P1과 기준 P2는 전위 차수가 다릅니다. scikit-fem 12.0.2(BSD-3-Clause)로 P2
전계를 독립 조립·풀이하고 전하/에너지·적분 차수 검사를 수행했습니다. 속도와 메시
입력은 제품 계약에서 오므로 속도 구성법의 독립 검증은 아닙니다. 기하·메시 설정을
명시하고 당시 배열을 메시 hash로 식별합니다. 다른 플랫폼의 재메시는 달라질 수
있습니다. 유지한 비교 기준은 절대 정확도·약한 상호항·외곽 수렴·실측 검증을 보장하지
않습니다.

기록은 기하 입력·경계 순서·정확한 기준 도구와 수치 라이브러리 버전·출처·비용·값과
해시를 포함합니다. 기존 환경에 보존하지 않은 설치 lock·archive는 사유와 함께
미상으로 표시합니다. `provenance_status`는 `reconstructed`이며 배포 전체의 완전한
재현성으로 설명하면 안 됩니다. 값은 유한하고 작으며 읽기 전용으로 로드합니다.
소비자는 값·입력·해시 손상, 중복 키, 비유한 값, 미상 항목 사유 누락을 거절합니다.

기존 고정 공유 의존성과 명시한 시험 버전을 설치한 체크아웃에서 소스를 PYTHONPATH에
두고 수동 재생할 수 있습니다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python tests/sipi/reference_values/scikit_fem/compare_multisignal.py --signals 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python tests/sipi/reference_values/scikit_fem/compare_multisignal.py --signals 4
```

Windows에서는 현재 셸의 문법으로 환경변수를 설정한 뒤 같은 Python 스크립트를
실행합니다. 수동 재생에는 상당한 시간·메모리가 필요할 수 있습니다. 기본이자 유일한
동작은 모든 P2 출력의 바이트 비교입니다. 차이가 있으면 실패 코드로 끝나며 기준값을
덮어쓰지 않습니다. 다른 플랫폼/런타임의 차이는 검토해야 합니다. 이 재생은 제품
커패시턴스 유한차분을 다시 수행하지 않으며 일반 제품 시험이 별도로 그 검사를
유지합니다. 원 비공개 비교 driver와 공개 재생 스크립트는 서로 다른 hash를 기록합니다.
Linux 기록으로 새 Windows/macOS·배포 지원을 주장하지 않습니다.

[English](../../../../../packages/sipi/fem_shape_references.md)
