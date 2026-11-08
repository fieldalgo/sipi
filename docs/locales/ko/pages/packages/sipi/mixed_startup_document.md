# 단위를 보존하는 혼합 소스 시작 입력 저장

`MixedSourceRLGCLadderDocument`는 [혼합 전압원/전류원 API](mixed_startup.md)를
**sipi.mixed-rlgc-startup/1**로 저장합니다. 각 소스의 종류·파형 단위·직렬/병렬 저항
의미를 보존하고 파싱은 회로 전파 없이 검증합니다. 이전 동종 소스 스키마를 바꾸지 않습니다.

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
```

## root 키13개와 소스 종류

필수 키는 `schema`, `time_s`, `sources`, `R_ohm_per_m`, `L_h_per_m`, `G_s_per_m`,
`C_f_per_m`, `length_m`, `cells`, `load_resistance_ohm`, `load_capacitance_f`,
`load_branch_resistance_ohm`, `load_branch_inductance_h`입니다. 추가/누락/중복 키·미지원
버전·비유한 JSON 수를 거부합니다. `sources`는 명시적 dictionary2개를 담습니다.

| kind | 필수 파형 | 필수 저항 |
|---|---|---|
| voltage | `voltage_v`, V | `series_resistance_ohm`, 유한 비음수 |
| current | `current_a`, A | `shunt_resistance_ohm`, 유한 비음수 또는 null |

소스별 키는 정확히3개입니다. 다른 종류의 키를 변환하지 않고 거부합니다. 전압원0ohm은
근단V 지정,전류원0ohm은 근단 단락,null은 병렬 저항 제거입니다. 동종/혼합 순서 모두
이 스키마에서 그대로 보존합니다.

물리 검증을 공유합니다. 첫 값0이며 시간 길이에 맞는1차원 파형·0부터 시작하는
2..10000개 균일 시간 행·명시1..128셀·양의 길이·정확 대칭 PSD 선로R/G와 조건을
만족하는 SPD 선로L/C·PSD 외부C/Rbranch·조건을 만족하는 SPD Lbranch를 요구합니다.
영/rank-one 부하C/R을 보정 없이 보존합니다. 집중F/H와 선로F/m/H/m를 구분하며 행렬을
추정하지 않습니다.

## 재실행·출력·예산

생성/로딩은 중첩 입력을 복사하며 `samples`는 실제 시간 행 수입니다. 정수
`max_evaluations`(2..10000,기본128)는 셀·소스 종류·상태 수와 독립입니다.3행·128셀은
예산3에 들어가고3행·1셀은 예산2일 때 전파 전에 거부합니다. 시간 범위·격자·소스 종류·
버전을 바꾸지 않습니다. 원래 byte/진단 제한과 수치 실행 예외를 유지합니다.

분석은 응답 타입·전체 정규화 입력·시간·source_values/kinds/units·노드/구간/4포트 형상,
두 소스 손실 형상과 외부 커패시터/분기 전류/에너지/변화율/손실 형상을 검사합니다.
직접 응답은 복사된 읽기 전용 내부 상태를 유지합니다. 공통 실행은 기본적으로 내부
선로 상태를 생략하되 단위별 입력·V/A 메타데이터·분리된 소스 손실과 원래 선로/외부
에너지 진단을 보존합니다. 실패한 계산은 부분 성공이 아닙니다.

원래 전압원·Norton 스키마는 자신의 scope를 유지하고 교차 로딩을 거부합니다.
[파동 저장 wrapper](startup_waves_document.md)의version1/2 모두 이 새 혼합 스키마를
계속 거부합니다. [직접 파동 진단](startup_waves.md)은 분석한 혼합 응답을 지원합니다. 저장 파동 연결은
[StartupPortWavesDocument](startup_waves_document.md)의 명시적 `version=3`를 요구합니다.

행렬/ramp/pulse6개 전체 상태,소스/경계8개,모든 필수 키,엄격한 중첩 단위·중복·무전파
파싱·복사·예산·출력 오염·영/rank-one 부하·읽기 전용·원래 실행 실패를 검사합니다.
물리 해석/KCL/연속 선로 기준은 API와 같습니다. 명시 상수 유한 회로를 넘어 새 물리
모델·실측 검증·브라우저/Windows 통합을 추가하지 않습니다.

[혼합 소스 API](mixed_startup.md) · [공통 실행](execution.md) ·
[English](../../../../../packages/sipi/mixed_startup_document.md)
