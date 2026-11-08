# 전류 구동 시작 응답 입력 저장

`NortonReactiveRLGCLadderDocument`는 [전류원 리액티브 시작 API](norton_startup.md)를
**sipi.norton-rlgc-startup/1**로 저장합니다. 전류 표본의 A 단위와 소스 병렬 저항을
명시하며 전압원의 직렬 저항과 구별합니다. 파싱은 회로 전파 없이 입력을 검증합니다.

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
```

## 필수 14개 키와 단위

키는 `schema`, `time_s`, `source_currents_a`, `R_ohm_per_m`, `L_h_per_m`,
`G_s_per_m`, `C_f_per_m`, `length_m`, `cells`, `source_shunt_resistance_ohm`,
`load_resistance_ohm`, `load_capacitance_f`, `load_branch_resistance_ohm`,
`load_branch_inductance_h`입니다. 중복/미지원 키·비유한 수·미지원 버전을 거부하며
빠진 행렬이나 단위를 추정하지 않습니다.

물리 API 검증을 공유합니다. 0에서 시작하는 2..10000개 균일 시간 행·첫 행 0인 PWL
전류·명시적 1..128셀·두 도체·유한 실수 정확 대칭 PSD 선로 R/G와 조건을 만족하는
SPD 선로 L/C를 요구합니다. 집중 C[F]/분기 R[ohm]는 영·rank-one PSD를 허용하며
분기 L[H]는 고유값 비>1e-12인 SPD여야 합니다. 집중 단위와 단위 길이당 값을 구별합니다.

소스 병렬 저항 각 원소는 유한 비음수 또는 null입니다. null은 병렬 저항 없는 이상
전류원, 0은 근단 단락입니다. 부하 저항의 개방/단락/유한 의미도 유지합니다. 공통
출력은 `source_currents_a`, 공급 전력 `Vnear*Iinj`, `source_shunt_resistor_loss`를
보존합니다. 전압 표본이나 Thevenin 직렬 손실로 바꾸지 않으며 선로·커패시터·분기
에너지를 구분합니다.

## 재실행과 예산

생성과 로딩은 중첩 입력을 복사합니다. `samples`는 실제 시간 행 수입니다.
`max_evaluations`는 정수 2..10000(기본128)이며 저장 셀·상태 수와 독립입니다.
3행·128셀은 예산3에 들어가고 3행·1셀은 예산2일 때 전파 전에 거부합니다. 시간
범위나 셀 수를 자동 변경하지 않습니다. byte 한도·진단 제한·원래 실행 예외를 유지합니다.

전체 입력·시간·전류 동일성과 노드/구간/4포트 및 커패시터/분기 배열 형상을 검사합니다.
직접 분석은 복사된 읽기 전용 내부 상태를 반환하며 공통 실행은 기본적으로 이를
생략하되 구분된 에너지·손실·보존 검사를 유지합니다. 계산 실패는 부분 성공이 아닙니다.

[전압원 저장 v4](coupled_reactive_startup_document.md)는 기존 스키마와 scope를 유지합니다.
전압/전류 키·스키마 교차 로딩을 거부하며 단위 변환이나 버전 승격을 추정하지 않습니다.
기존 [startup-port-waves/1](startup_waves_document.md)은 원래 6종 물리 스키마만 허용하고
이 Norton 형식은 거부합니다. 파동 연결은 별도 명시적 계약이 필요합니다.

6개 행렬/ramp/pulse와 6개 혼합 경계를 물리 API와 정확히 재현하고 영/rank-one 부하,
무전파 파싱, 행 예산, 엄격 입력, 읽기 전용 상태, 출력 동일성, 실행 실패를 검사합니다.
기반 LC/KCL/모드/정착 독립 검증은 그대로 필요합니다. 저장 연결이 새 물리 모델·실측
정확도·브라우저/Windows 통합을 뜻하지는 않습니다.

[전류원 API](norton_startup.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/norton_startup_document.md)
