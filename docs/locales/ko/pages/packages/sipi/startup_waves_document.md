# 포트 파형 기준을 포함한 시작 응답 입력 저장

`StartupPortWavesDocument`는 기본 **sipi.startup-port-waves/1**으로 완전한 시작 응답 문서와
[파형 진단](startup_waves.md)의 명시적 실수 기준 임피던스를 함께 저장합니다. 생성자는
지원 문서 객체·`z_ref`와 선택적인 명시적 `version=2`를 받고, 이미 계산한 응답이 아닌 정규화된 입력을 복사합니다.

```python
import numpy as np
from sipi import LosslessStartupDocument, StartupPortWavesDocument
from sipi.execution import normalize_saved, execute_saved

startup = LosslessStartupDocument(np.linspace(0., 8e-9, 801),
    source_times=[0., 1e-9], source_voltages=[0., 1.], z0_ohm=50., delay_s=1e-9,
    source_resistance=50., load_resistance=None, max_terms=100)
document = StartupPortWavesDocument(startup, z_ref=[35., 75.])
text = document.dumps()
assert normalize_saved(text) == text
# Matched source requires one forward delay term, despite 801 output rows.
out = execute_saved(text, max_evaluations=2)
assert out['status'] == 'complete' and out['input']['startup'] == startup.to_dict()
assert out['input']['startup']['max_terms'] == 100
assert len(out['result']['time_s']) == 801
waves = document.analyze(max_evaluations=2)
assert waves.power_balance_relative_error <= 1e-10
np.testing.assert_array_equal(waves.z_ref, [35., 75.])
```

## 필수 root 키 3개

root 키는 정확히 `schema`, `startup`, `z_ref_ohm`입니다. version1의 중첩 `startup`은
`sipi.lossless-startup/1`, `sipi.rlgc-startup/1`, 또는 `sipi.coupled-rlgc-startup/1`,
`/2`, `/3`, `/4` 중 하나의 완전한 원래 payload입니다. 기존 validator와 버전을 유지합니다.
다른 스키마·미지원 버전·파형 문서의 재귀 중첩은 거부합니다. 자동 승격이나 물리 입력
추정은 없습니다.

`z_ref_ohm`는 scalar 문서에는 유한 양의 실수 2개, coupled 문서에는 4개를 요구합니다.
스칼라·복소수/bool/비유한·0/음수·잘못된 길이/형상·누락/추가 키·모든 JSON 깊이의
중복 키를 거부합니다. 파싱은 상태 전파나 파형 변환 없이 전체 중첩 문서와 기준을
검증합니다. 정규화된 중첩 배열과 기준은 복사합니다.

## 원래 예산 의미 유지

호출자 정수 `max_evaluations`(2..10000, 기본128)는 원래 문서로 그대로 전달합니다.
무손실 시작 응답은 실제 필요한 forward 지연 항을 세며 저장 `max_terms` 상한과
출력 행 수는 별개입니다. 유한 RLGC 시작 응답은 실제 시간 행을 세며 명시적 셀 수·
도체·파형 배열 수와 별개입니다. 정합 무손실 소스의1001행은 예산2에 들어가고,
RLGC3행·128셀은 예산3에 들어가지만 예산2에는 실패합니다. 상한을 줄이거나 포트 수를
곱하지 않습니다. 실행 시간이나 수렴을 인증하는 제어는 아닙니다.

원래 문서가 물리 응답 동일성을 검사한 뒤 파형을 변환합니다. wrapper는 파형 응답 타입·
정확한 시간/V/I/기준/포트 이름/원응답 종류와 입사/반사/전력 형상을 확인합니다.
Python은 복사된 읽기 전용 `StartupPortWaves`를 반환합니다. 공통 실행은 전체 중첩
입력과 유한 파형 출력을 보존하며 기존 byte/진단 제약을 유지합니다. 원래 전파·척도·
파형 상쇄 실패는 예외로 남고 부분 성공이나 자동 clipping은 없습니다.

지원 중첩6버전×ramp/pulse의12개 직접/복원/공통 실행을 정확히 재현합니다. 기존 정규화
보존·무전파 파싱·중첩 복사/키·기준 검증·두 종류의 원래 예산·잘못된 출력 동일성·수치
실패 전파를 검사합니다. 독립 지연 반사/phasor/전력 기준은 파형 API와 같습니다.
물리 솔버·모드 추출·일반 TDR 역산·브라우저/Windows 연결을 추가하는 저장 계약은 아닙니다.

[포트 파형](startup_waves.md) · [무손실 저장](startup_document.md) ·
[RL 부하 저장](coupled_reactive_startup_document.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/startup_waves_document.md)

## 전류원을 위한 명시적 version2

`version=2`는 **sipi.startup-port-waves/2**를 선택합니다. 닫힌 레지스트리는 원래 6종과
[sipi.norton-rlgc-startup/1](norton_startup_document.md)을 허용합니다. root 키는 여전히
3개입니다. 기본/명시 version1은 Norton을 계속 거부합니다. 입력에 따른 자동 승격은
없으며 bool·float·문자열·미지원 생성자 버전을 거부합니다. 로딩/정규화는 root와 모든
중첩 물리 버전을 유지합니다. 이전 전압 문서를 담은 version2도 그대로 version2입니다.

```python
import numpy as np
from sipi import NortonReactiveRLGCLadderDocument
from sipi.execution import normalize_saved, execute_saved

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((.02*np.minimum(t/2e-9, 1.), -.01*np.minimum(t/3e-9, 1.)))
document = NortonReactiveRLGCLadderDocument(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_shunt_resistance=[None, 37.], load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['input']['schema'] == 'sipi.norton-rlgc-startup/1'
assert out['status'] == 'complete' and not out['result']['states_included']
response = document.analyze(max_evaluations=121)
assert np.array_equal(response.total_energy,
    response.energy + response.load_capacitor_energy + response.load_branch_energy)
assert response.total_power_balance_relative_error <= 1e-10

from sipi import StartupPortWavesDocument
wrapped = StartupPortWavesDocument(document, z_ref=[35., 45., 55., 65.], version=2)
assert normalize_saved(wrapped.dumps()) == wrapped.dumps()
result = execute_saved(wrapped.dumps(), max_evaluations=121)
assert result['input']['schema'] == 'sipi.startup-port-waves/2'
assert result['input']['startup']['schema'] == 'sipi.norton-rlgc-startup/1'
assert result['result']['source_kind'] == 'NortonReactiveRLGCLadderResponse'
np.testing.assert_allclose(np.array(result['result']['port_power_w'])[:, :2].sum(axis=1),
    response.source_power - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

Norton은 명시적 기준 4개와 실제 시간 행 예산을 사용합니다. 출력은 주입 전류 대신
단자 전류를 사용하며 Norton 응답 클래스명을 보존합니다. 근단 파동 전력은 공급 전력에서
소스 병렬 손실을 뺀 값입니다. 물리 전파·에너지와 파동 공식은 바뀌지 않으며 유한 파동
출력에 물리 응답 내부 상태를 추가로 포함하지 않습니다.

7종 중첩 스키마의 ramp/pulse 14개 재실행과 원래 6종의 v1/v2 파동 출력 동일성을
검사합니다. Norton 혼합 경계6종, 엄격한 버전/단위/재귀 거부, 무전파 파싱, 입력 복사,
원래 지연 항/시간 행 예산, 출력 동일성과 실행 실패를 검사합니다. 원version1 시험은
그대로 유지합니다. 물리 범위·소스 수렴·실측 검증·앱 통합의 확대를 뜻하지 않습니다.
