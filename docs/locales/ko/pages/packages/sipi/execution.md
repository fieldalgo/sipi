# 저장 입력의 공통 실행

`sipi.execution`은 브라우저 Worker와 로컬 프로그램이 기존 엔진 문서를 같은
진입점으로 처리하도록 합니다. 파일·네트워크·브라우저·프로세스를 조작하지
않으며 새 수치 모델을 도입하지 않습니다.

[물리 상수](constants.md)는 런타임과 독립적인 CODATA 버전을 명시합니다.

```python
import json
from sipi import LumpedNetworkDocument
from sipi.execution import normalize_saved, execute_saved, saved_schemas

document = LumpedNetworkDocument([0, 1e9], resistance=10, inductance=2e-9)
text = normalize_saved(document.dumps())
result = execute_saved(text)
assert result["status"] == "complete"
assert result["input"] == document.to_dict()
wire_text = json.dumps(result, allow_nan=False)
print(result["result"]["network"]["s"])
print(saved_schemas())
```

`normalize_saved`는 원래 스키마 버전과 확정 설정을 유지한 정규 JSON을 반환합니다.
메시나 필드 계산은 하지 않지만 일부 네트워크 검증기는 작은 대수 계산을 합니다.
`saved_schemas()`는 닫힌 목록을 반환합니다: cross-section/1–3,
impedance-study/1–4, impedance-design/1–3, circular-aperture/1,
aperture-section/1, aperture-study/1, aperture-design/1, transmission-line/1–2,
volume-line/1, lumped-network/1, network-assembly/1, network-transforms/1–2,
circuit/1, capacitance-3d/1. 각 이름에는 `sipi.` 접두사가 붙습니다. 미지원 버전·중복 키·비유한
숫자(지수 overflow 포함)·텍스트가 아닌 입력은 거부합니다.

## 결과 계약

`execute_saved`는 schema `sipi.execution/1`, 정규 `input`, `status`, `result`,
`error`를 가진 독립 사전을 반환합니다. 복소 스칼라/배열은 같은 모양의
`{"real": ..., "imag": ...}`, 실수 배열은 리스트로 표현합니다. NaN/Infinity는
출력하지 않습니다. 기하·재료·단위·유효범위 해석에는 원래 입력이 필요합니다.
개발 빌드는 버전 번호만으로 식별할 수 없으므로 앱은 정확한 엔진 커밋과
wheel/런타임 해시를 별도로 기록해야 합니다.

| 입력 | 선택 출력 |
|---|---|
| 단면 | 순서 있는 이름, C/C0/C_loss(F/m), L(H/m); 단일 신호의 z0(ohm), 유효 유전율, 지연(s/m) |
| 원형/타원 개구 | 이름과 복소 C(F/m); 원형은 스칼라, 타원은 행렬 |
| 공차 | quantity/unit, 모든 행의 index/parameters/document/value/error, 실패 개수와 summary |
| 목표 역산 | quantity/unit, parameter, 목표/결과/세분 결과, 두 잔차, 완료 이력과 결과 기하; 임피던스 재료 평가 보존 |
| transmission/volume 선로 | 도체 이름, 주파수(Hz), R/L/G/C(ohm/m, H/m, S/m, F/m), 네트워크와 선택 진단 |
| lumped/assembly/transform | 최종 네트워크; assembly의 성분 망, transform의 원본/fixture 망도 보존 |
| 유한 3D 정전장 | 모델·도체 순서, 전체 C/에너지 C(F), 1V 구동 접지 전하(C), 메시 수·일관성 비율; [계약](capacitance3d.md) 참조 |
| 회로 | 최종 망, 종단 응답, 소스/부하, 조건수/잔차와 선택 NEXT/FEXT |

네트워크는 `frequency_hz`, 순서 있는 `port_names`, `basis`, 양의 실수
`reference_ohms`, 복소 `s`를 포함합니다. S 모양은 (주파수, 출력 포트, 입력 포트)입니다.
회로 전압/전류는 V/A, 부하는 ohm, 전력파 `a/b`는 sqrt(W), `network_power`는 W,
잔차/조건수는 무차원입니다. AC는 peak phasor, DC는 기존 정적 전력 규칙입니다.
NEXT/FEXT는 복소 전압비이며 시간 영역 피크나 dB가 아닙니다. 로그를 취하지
않으므로 0도 그대로 저장합니다.

선택 출력에는 메시·필드·중첩 추출 객체가 없습니다. 이 객체는 직접 API를
사용하며 정규 입력으로 재생할 수 있습니다. 기하 행렬은 대칭 even/odd 모드나
비대칭 쌍의 유일한 임피던스를 뜻하지 않습니다. 개구 C로 총 pad C·전파 임피던스·
3D 비아 전이를 추정하지 않습니다.

## 실패와 예산

- `complete`: 기본 계산이 반환됨. 물리 정확도 인증이 아니며 선택 진단 상태는 별도입니다.
- `incomplete`: 공차에 실패 샘플이 있음. 모든 행과 오류를 순서대로 보존하고 summary는 null입니다. 재샘플이나 부분 수율을 만들지 않습니다.
- `failed`: 목표의 bracket·예산·세분 메시 조건 실패. result는 null이며 error에 타입/메시지·값 단위·완료 이력과 원래 API가 제공하는 실패 parameter를 보존합니다.

잘못된 입력과 다른 솔버 오류는 예외로 전달하므로 transport는 실패로 표시해야
합니다. 취소/시간 제한은 호출자가 담당하며 중단을 빈 성공 결과로 바꾸지 않습니다.

두 함수의 기본 `max_input_bytes=262144`는 UTF-8 바이트 수입니다. 실행의
`max_evaluations=128`은 2–10000 정수입니다. 공차 샘플 수와 목표 입력의 평가
예산이 이 제한 안에 있어야 필드를 계산합니다. 목표의 저장 예산을 잘라내거나
입력을 바꾸지 않습니다. 이 제한은 **메시·중첩 대수·메모리·실행시간·출력 크기의
상한이 아닙니다**. 앱은 별도 Worker/process 격리·취소·자원 정책이 필요하며
이 함수 자체는 임의 비신뢰 작업의 sandbox가 아닙니다.

`diagnostics=["characteristic", "modes"]`는 최상위 transmission/volume 문서에만
명시 선택합니다. 추출 RLGC를 재사용하며 추가 필드 계산은 없습니다. 각 진단에
complete/failed가 있어 DC 거부·모드 불확정이 기본 RLGC/S를 지우지 않습니다.
모드 오류가 주파수 index/Hz를 제공하면 보존합니다. 행렬/모드 배열은
[characteristic](characteristic.md)와 [mode](modes.md)의 단위·1W 정규화·퇴화/추적
거부 규칙을 따릅니다.

검증은 직접 API와 직렬화 결과의 기하·복소 국소 C·shared/volume RLGC·진단·
공차/통계·목표·회로·Touchstone·망 조합을 대조합니다. 입력 모호성·예산·실패
보존도 확인합니다. 이는 연결부 검증이며 각 엔진의 독립 수치 기준과 수렴 시험을
대체하지 않습니다.

[English](../../../../../packages/sipi/execution.md)
