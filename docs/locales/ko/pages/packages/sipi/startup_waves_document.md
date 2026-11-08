# 포트 파형 기준을 포함한 시작 응답 입력 저장

`StartupPortWavesDocument`는 기본 **sipi.startup-port-waves/1**으로 완전한 시작 응답 문서와
[파형 진단](startup_waves.md)의 명시적 실수 기준 임피던스를 함께 저장합니다. 생성자는
지원 문서 객체·`z_ref`와 선택적인 명시적 `version=2`, `version=3` 또는 `version=4`를 받고, 이미 계산한 응답이 아닌 정규화된 입력을 복사합니다.

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

## 단위가 명시된 혼합 소스를 위한 version3

`version=3`는 **sipi.startup-port-waves/3**를 선택하고 version2의7종에
[sipi.mixed-rlgc-startup/1](mixed_startup_document.md)을 추가합니다. version1은6종,
version2는7종 그대로입니다. 생성자 기본값은version1이므로 혼합 입력에는 명시적인
version3가 필요합니다. 로딩은 root버전과 중첩 물리/소스 단위 키를 보존하며 자동 승격·
종류 변환을 하지 않습니다. root3키·기준·재귀 금지·원래 물리 예산도 그대로입니다.

```python
import numpy as np
from sipi import MixedSourceRLGCLadderDocument

time = np.linspace(0., 12e-9, 121)
sources = [dict(kind='voltage', voltage_v=np.minimum(time/2e-9, 1.),
                series_resistance_ohm=0.),
           dict(kind='current', current_a=-.008*np.minimum(time/3e-9, 1.),
                shunt_resistance_ohm=None)]
document = MixedSourceRLGCLadderDocument(time, sources,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]], C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=16, load_resistance=[91., None],
    load_capacitance=np.array([[20., -4.], [-4., 30.]])*1e-12,
    load_branch_resistance=[[13., 1.], [1., 9.]],
    load_branch_inductance=np.array([[12., 2.], [2., 8.]])*1e-9)
from sipi.execution import normalize_saved, execute_saved
text = document.dumps()
assert normalize_saved(text) == text and document.samples == 121
out = execute_saved(text, max_evaluations=121)
assert out['status'] == 'complete'
assert out['input']['schema'] == 'sipi.mixed-rlgc-startup/1'
assert out['result']['source_units'] == ['V', 'A']
response = document.analyze(max_evaluations=121)
assert response.source_kinds == ('voltage', 'current')
assert response.source_units == ('V', 'A')
np.testing.assert_array_equal(response.voltage[:, 0], sources[0]['voltage_v'])
np.testing.assert_array_equal(response.current[:, 1], sources[1]['current_a'])
assert response.total_power_balance_relative_error <= 1e-10
assert not response.to_dict()['states_included']
assert np.all(response.source_series_resistor_loss == 0.)
assert np.all(response.source_shunt_resistor_loss == 0.)

from sipi import StartupPortWavesDocument
wrapped = StartupPortWavesDocument(document, z_ref=[35., 45., 55., 65.], version=3)
assert normalize_saved(wrapped.dumps()) == wrapped.dumps()
result = execute_saved(wrapped.dumps(), max_evaluations=121)
assert result['input']['schema'] == 'sipi.startup-port-waves/3'
assert result['input']['startup']['schema'] == 'sipi.mixed-rlgc-startup/1'
assert result['result']['source_kind'] == 'MixedSourceRLGCLadderResponse'
np.testing.assert_allclose(np.array(result['result']['port_power_w'])[:, :2].sum(axis=1),
    response.source_power - response.source_series_resistor_loss
    - response.source_shunt_resistor_loss, rtol=1e-10, atol=1e-12)
```

혼합 결과는4개 단자V/I 열과 혼합 응답 클래스명을 보존합니다. 근단 파동 전력은 공급
전력에서 소스 직렬/병렬 손실 모두를 뺀 값입니다. V/A 단위가 다른 입력값을 단자
전류로 사용하지 않습니다.

version3의8종 스키마×ramp/pulse16개를 재실행합니다. 원6종은v1/v2/v3 결과가 같고
Norton은v2/v3가 같습니다. 혼합6경계와 동종 소스2한계도 정확한 파동을 유지합니다.
기본/v1/v2의 혼합 거부·엄격 버전·중첩 단위·재귀·복사·예산·출력 동일성과 전파/상쇄
실패를 검사합니다. 이전 미지원 생성자version3 시험은 미지원999로 바꾸며 새version3의
양성 동작을 별도로 검사합니다. 저장 진단 계약의 확장이며 물리 전파 모델이나
브라우저/Windows 통합의 추가를 뜻하지 않습니다.

## 명시적 버전 4: 단일 신호 Debye 입력

`version=4`는 **sipi.startup-port-waves/4**를 선택하고 버전 3의 8종에
**sipi.debye-rlgc-startup/1**을 추가합니다. Debye 입력은 명시적 실수 포트
기준 2개를 사용합니다. 극점 순서, 0을 포함한 강도, 완화 주파수, C_inf와
전체 시간 배열은 원래 중첩 문서에 보존합니다. 버전 1/2/3은 기존 목록을
유지하고 Debye를 거부하며 생성자 기본값도 버전 1입니다.
모든 버전에서 파동 문서의 재귀 중첩을 거부합니다.

```python
from sipi import DebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved

startup = DebyeRLGCLadderDocument([0., 1e-9, 2e-9], [0., 1., 1.],
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=8, source_resistance=25., load_resistance=100.)
document = StartupPortWavesDocument(startup, z_ref=[35., 75.], version=4)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['input']['startup'] == startup.to_dict()
assert out['result']['source_kind'] == 'DebyeRLGCLadderResponse'
assert out['result'] == document.analyze(max_evaluations=3).to_dict()
```

9종의 ramp/pulse 총 18개 재실행과 해당하는 모든 구버전의 결과 일치를
검증합니다. Debye 6종 경계·1–4극점, 실제 시간 행 예산, 중첩 단위 검증,
결과 오염 검사와 물리 예외 전달도 확인합니다. 시간을 자동 연장하거나
기하 추출·주파수 의존 모드·TDR 해석을 수행하지 않습니다.
물리 제한은 [Debye 저장 계약](debye_startup_document.md)을 따릅니다.

## 명시적 버전 5: 두 신호 Debye 입력

`version=5`는 **sipi.startup-port-waves/5**를 선택하고 버전4의 9종에
**sipi.coupled-debye-rlgc-startup/1**을 추가합니다. 이 종류는 near_0,
near_1, far_0, far_1 순서로 네 개의 유한한 양의 실수 기준 임피던스가
필요합니다. 대칭 행렬, 1–2개의 선언된 극점, 강도0, 원래 극점 순서,
유한한 양의 종단 저항과 PWL 시간 표본을 보존합니다. 물리 셀·극점 제한과
실제 시간 행 예산의 의미도 같습니다. root는 schema, startup, z_ref_ohm
세 키만 가집니다. 소스 합성·재표본화·중첩 버전 자동 승격은 없습니다.
기본 버전1과 기존 버전1..4의 등록 목록은 그대로이며 결합 Debye를 거부합니다.

```python
from sipi import CoupledDebyeRLGCLadderDocument, StartupPortWavesDocument
from sipi.execution import execute_saved
import numpy as np

startup = CoupledDebyeRLGCLadderDocument([0., 1e-9, 2e-9],
    [[0., 0.], [1., -.4], [1., -.4]], R=[[20., 3.], [3., 20.]],
    L=np.array([[500., 100.], [100., 500.]])*1e-9,
    G=[[.002, -.0003], [-.0003, .002]], C_inf=np.array([[220., -40.], [-40., 220.]])*1e-12,
    delta_C=np.array([[[150., -25.], [-25., 150.]]])*1e-12,
    relaxation_hz=[1e9], length=.1, cells=16,
    source_resistance=[25., 25.], load_resistance=[100., 100.])
document = StartupPortWavesDocument(startup, z_ref=[35., 45., 55., 65.], version=5)
out = execute_saved(document.dumps(), max_evaluations=3)
assert out['result']['source_kind'] == 'CoupledDebyeRLGCLadderResponse'
assert out['input']['startup'] == startup.to_dict()
assert len(out['result']['incident_sqrt_w'][0]) == 4
```

10종×ramp/pulse 20개와 각각 지원되는 이전 버전의 재실행 결과를 비교합니다.
대각·교환대칭·비가환 행렬, 단일/강도0/중복/순서변경 극점, 엄격한 중첩
단위·재귀, 입력 복사, 시간·셀 예산 분리, 결과 동일성과 원래 물리·파동
실패를 검사합니다. 기존 v4 시험의 미지원 버전5 상수만999로 바꾸며 양의
v5 경로를 별도로 검증합니다. 웹·Windows 연결이나 실측 정확도 검증은
아닙니다. 물리 제한은 [결합 Debye 저장](coupled_debye_startup_document.md),
기준 임피던스 의미는 [단자 파동](startup_waves.md)을 따릅니다.
