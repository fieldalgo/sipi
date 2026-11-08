# 저장 입력의 공통 실행

[두 변수 임피던스 목표 저장](pair_design_document.md)은 두 목표와 전체 실패 문맥을 보존합니다.

[전도율 프로파일 저장](conductivity_profile_document.md)은 외측 포트면을 보존하고 적분 전에 주파수 예산을 확인합니다.

[주기 혼합 전원 저장](periodic_mixed_circuit.md)은 두 전원 종류·시간 배열·고조파/평균 전력을 보존합니다.

[혼합 회로 저장](mixed_circuit.md)은 포트별 전압원·전류원 종류와 이상 경계·구조별 전력을 보존합니다.

[주기 전류원 저장](periodic_norton_circuit.md)은 시간 파형·개방 단자·고조파/평균 전력을 보존합니다.

[Norton 회로 저장](norton_circuit.md)은 명시 전류원·개방 단자·주파수별 전력을 보존합니다.

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
aperture-section/1, aperture-study/1, aperture-design/1, transmission-line/1–6,
volume-line/1, lumped-network/1, network-assembly/1, network-transforms/1–2,
circuit/1, capacitance-3d/1, network-band/1, line-length-design/1–2, tem-ports-3d/1, impedance-yield/1, yield-design/1–2, dielectric-fit/1, line-quantity-design/1–2 and line-quantity-study/1–2 and line-quantity-yield/1, periodic-network/1, periodic-circuit/1, norton-circuit/1, periodic-norton-circuit/1, mixed-circuit/1, periodic-mixed-circuit/1, conductivity-profile/1, pair-impedance-design/1–2, sampled-impedance-design/1, lossless-startup/1, rlgc-startup/1, coupled-rlgc-startup/1–4, startup-port-waves/1–9, norton-rlgc-startup/1, mixed-rlgc-startup/1, debye-rlgc-startup/1, coupled-debye-rlgc-startup/1, psd-coupled-debye-rlgc-startup/1, debye-capacitive-startup/1, debye-reactive-startup/1, multiconductor-rlgc-startup/1, multiconductor-debye-rlgc-startup/1, grid-plate-capacitance/1, strip-grid-capacitance/1, thick-grid-strip-capacitance/1, volume-grid-strip-capacitance/1, volume-grid-pair-capacitance/1. 각 이름에는 `sipi.` 접두사가 붙습니다. 미지원 버전·중복 키·비유한
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
| 도체별 금속 선로 | 추가 `conductor_boundaries`: 경계 이름·표피깊이·거칠기 계수·복소 표면 임피던스·경계별 R 기여; [계약](boundary_conductor.md) 참조 |
| lumped/assembly/transform | 최종 네트워크; assembly의 성분 망, transform의 원본/fixture 망도 보존 |
| 유한 3D 정전장 | 모델·도체 순서, 전체 C/에너지 C(F), 1V 구동 접지 전하(C), 메시 수·일관성 비율; [계약](capacitance3d.md) 참조 |
| 유한 3D TEM 포트 | 명시적 경계 모델·계산된 기준 저항의 네트워크·포트 노름·메시 수·전체 경계와 투영 전력 진단; [계약](ports3d.md) 참조 |
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
  수율 평가도 미판정 행을 남기고 `incomplete`로 반환하며, 실패를 제외하는 대신 명시적인 표본 비율·신뢰구간 범위를 제공합니다.
- `failed`: 목표의 bracket·예산·세분 메시 조건 실패. result는 null이며 error에 타입/메시지·값 단위·완료 이력과 원래 API가 제공하는 실패 parameter를 보존합니다.

잘못된 입력과 다른 솔버 오류는 예외로 전달하므로 transport는 실패로 표시해야
합니다. 취소/시간 제한은 호출자가 담당하며 중단을 빈 성공 결과로 바꾸지 않습니다.

두 함수의 기본 `max_input_bytes=262144`는 UTF-8 바이트 수입니다. 실행의
`max_evaluations=128`은 2–10000 정수입니다. 공차 샘플 수와 목표 입력의 평가
예산이 이 제한 안에 있어야 필드를 계산합니다. 유한 3D TEM 포트는 주파수 하나당
평가 한 번으로 세며 포트나 체적 계산 전에 검사합니다. 목표의 저장 예산을 잘라내거나
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

[고정 후보 수율 설계](yield_design.md)의 `sipi.yield-design/1`도 지원합니다. 모든 후보의 계획 표본수 합을 풀이 전에 예산 검사하며, 한 행이라도 미완이면 실행은 `incomplete`입니다. 목표에 따른 후보 선택 상태와 계산 완료 상태는 별개입니다.

[저장 면별 선로](face_line.md)는 `conductor_boundaries`에 Q·면별/전체 도체 적분전류·기존 전류 flux 진단을 추가로 보존합니다.

[접지 면 저장](ground_face_line.md)은 line/6에서 확장된 접지 면 진단을 보존합니다.

[저장 유손실 목표](line_goal_document.md)는 호출자 예산을 field 전에 검사하며 실패 시 시도 횟수·단계·입력·완료 이력을 보존합니다.

[유손실 study](line_study.md)는 실패 표본이 있으면 모든 행을 유지하고 incomplete·summary=null로 반환합니다.

[저장 주기 응답](periodic_document.md)은 최종 기저의 모든 포트 입사파를 명시하고 시간 표본 수 N을 필드/FFT 전에 예산 검사합니다. 결과는 주기 정상상태 V/I·전력파와 선택적인 이산 임펄스이며 과도응답/인과성 인증이 아닙니다.

[저장 주기 회로](periodic_circuit.md)는 모든 포트의 Thevenin 전압·유한 부하를 명시하며 시간 응답·DC/peak 조화파 진단·각 주파수 전력과 합산 평균 전력을 보존합니다.

[전류원 시작 입력 저장](norton_startup_document.md)은 전류 A 표본과 소스 병렬 손실을 구분해 보존합니다.

[혼합 소스 시작 입력 저장](mixed_startup_document.md)은 V/A 파형과 소스 직렬/병렬 손실을 구분해 보존합니다.

[Debye 시작 응답 저장](debye_startup_document.md)

[결합 Debye 저장](coupled_debye_startup_document.md)은 행렬 극점과 유한 종단 저항을 보존합니다.

[PSD Debye 저장](psd_debye_startup_document.md)은 특이 강도를 명시적으로 보존합니다.

[외부 정전용량 입력 저장](debye_capacitive_startup_document.md)은 F와 F/m를 구분합니다.

[외부 RL 입력 저장](debye_reactive_startup_document.md)은 Ω·H·F와 선로의 단위당 길이 입력을 구분합니다.

[3·4신호 입력 저장](multiconductor_startup_document.md)은 명시 신호 수와 SI 입력·시간 행 예산을 보존합니다.

[명시적 저장 버전9](startup_waves_document.md)이3·4신호 입력과6·8개 기준 저항을 추가하며 구버전은 유지합니다.

[유한 격자판 입력 저장](grid_plate_document.md)은 SI 기하·명시 셀 수·1회 정전장 계산을 보존합니다.


[얇은 신호선·격자 입력 저장](strip_grid_document.md)은 명시 기하·유전체 영역과 실제 한 번의 장 풀이를 보존합니다.


[유한 접지 두께 입력 저장](thick_grid_strip_document.md)은 명시 두께와 한 번의 장 풀이를 보존합니다.


[유한 신호선·접지 체적 저장](volume_grid_strip_document.md)은 두 두께와 한 번의 장 풀이를 보존합니다.


[쌍 신호선·접지 체적 저장](volume_grid_pair_document.md)은 명시한 신호선 간격과 두 전압 기저를 보존합니다.


[3·4신호 Debye 입력 저장](multiconductor_debye_startup_document.md)은 명시 pole·신호 수·실제 시간 행 예산을 보존합니다.


[명시 저장 파동 버전10](startup_waves_document_v10.md)은 버전1–9를 유지하며3·4신호 Debye 입력을 추가합니다.


[다신호 PSD Debye 입력 저장](psd_multiconductor_debye_startup_document.md)은 특이 손실/강도와 원래 시간 행 예산을 보존합니다.


[명시 저장 파동 버전11](startup_waves_document_v11.md)은 버전1–10을 유지하며3·4신호 PSD Debye 입력을 추가합니다.


[다신호 커패시터 입력 저장](multiconductor_debye_capacitive_startup_document.md)은 명시 외부 저장과 실제 시간 행 예산을 보존합니다.


[명시 저장 파동 버전12](startup_waves_document_v12.md)은 버전1–11을 유지하며 다신호 Debye 외부 커패시터 입력을 추가합니다.


[다신호 직렬 RL 입력 저장](multiconductor_debye_reactive_startup_document.md)은 명시 branch 상태 의미와 실제 시간 행 예산을 보존합니다.


[명시 저장 파동 버전13](startup_waves_document_v13.md)은 v1–12를 유지하며 다신호 Debye 직렬 RL 입력을 추가합니다.


[명시 저장 파동 버전14](startup_waves_document_v14.md)는 v1–13을 유지하며 다신호 Debye 전류원 입력을 추가합니다.
