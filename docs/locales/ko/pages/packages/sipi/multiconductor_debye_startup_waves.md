# 다신호 Debye 단자 파동

[English](../../../../../packages/sipi/multiconductor_debye_startup_waves.md) | **한국어**

기존 `startup_port_waves(response, *, z_ref)`가
[3·4신호 Debye 회로](multiconductor_debye_startup.md)의
`MulticonductorDebyeRLGCLadderResponse`를 명시적으로 수락합니다.6·8단자의
전압/전류 샘플을 한 번 변환하며 회로를 다시 전파하거나 물리 모델을 바꾸지 않습니다.

```python
import numpy as np
from sipi import multiconductor_debye_rlgc_ladder_response, startup_port_waves

t = np.linspace(0., 4e-9, 41)
response = multiconductor_debye_rlgc_ladder_response(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 23., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, .0024]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([130., 143., 156.])])*1e-12,
    relaxation_hz=[8e7], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
waves = startup_port_waves(response, z_ref=[35., 45., 55., 65., 75., 85.])
assert waves.incident.shape == waves.reflected.shape == (41, 6)
assert waves.source_kind == 'MulticonductorDebyeRLGCLadderResponse'
np.testing.assert_array_equal(waves.voltage, response.voltage)
np.testing.assert_array_equal(waves.current, response.current)
```

기준 저항은 시간에 따라 변하지 않는 길이2N의 양의 유한한 실수 벡터입니다.
스칼라 자동 확장·복소 기준·모드 임피던스 추론은 허용하지 않습니다. 단자는
near N개 뒤 far N개이며 양단 전류는 선로 안으로 들어갑니다. 내부 노드/구간/
소스 배열로 단자 전류를 대신할 수 없습니다. 기존 결과형의 허용 포트 수는
유지합니다.

원래 식과 상대1e-10 복원/전력 기준을 유지합니다:
`a=(V/sqrt(Z)+I*sqrt(Z))/2`, `b=(V/sqrt(Z)-I*sqrt(Z))/2`, 단위sqrt(W).
V/I 복원은 각 포트의 원래 최대 신호 크기를, 전력은 상쇄 근처 순전력 대신
최대 파동 전력 크기를 기준으로 검사합니다. 표현할 수 없는 값이나 복원 실패는
클리핑하지 않고 거부합니다.

```python
np.testing.assert_allclose(
    waves.port_power.sum(axis=1),
    response.total_energy_rate + response.series_loss
    + response.shunt_loss + response.relaxation_loss,
    rtol=1e-10, atol=1e-12)
changed = startup_port_waves(response, z_ref=2*waves.z_ref)
np.testing.assert_array_equal(changed.port_power, waves.port_power)
assert max(waves.voltage_reconstruction_relative_error,
           waves.current_reconstruction_relative_error,
           waves.power_balance_relative_error) <= 1e-10
```

전체 단자 전력은 순간/분극 에너지 변화율과 직렬·병렬·완화 손실을 포함합니다.
near 전력은 소스 전력에서 소스 저항 손실을 뺀 값이고 far 전력은 부하 저항
손실의 음수입니다. 외부 소스 손실은 선로 파동 전력 수지에 포함하지 않습니다.
기준 저항을 바꾸면 파동은 달라져도 물리 V/I와 단자 전력은 유지합니다. 배열과
내보낸 값은 독립 읽기 전용이며 시간·이름·명시한 source_kind를 보존합니다.

검증은3/4신호의 결합/대각/RG0·ramp/pulse12개,독립 scalar Debye 모드 합성,
신호/pole 순열·one/zero강도·필드 보존·기준 저항·유한 범위·재전파 방지를
포함합니다. scikit-rf2.2.0 power Z-to-S 독립 비교2개는 합성6/8포트 정현파
V/I fixture에서 절대 파동 오차1e-10을 유지합니다. 이는 변환 대수 검사이며
전파된 선로/시작 응답 대조라고 표현하지 않습니다. 수정 전15소스 종류×2파형×
2기준의 파동 내보내기60개 해시는 소스/설치본에서 정확히 유지합니다.
scikit-rf는 기존 BSD-3-Clause 고지를 유지한 시험 전용입니다.

전파 모드·TDR 역산·b/a 또는 V/I 비율·지연 정렬·게이팅·FFT·주파수 의존
기준 저항을 추론하지 않습니다. [회로 입력 저장](multiconductor_debye_startup_document.md)은
가능하며 [명시 저장 파동 버전10](startup_waves_document_v10.md)이 이 종류를
수락합니다. 기존v1–9는 계속 거부합니다. 파동 변환은 수치 솔버·런타임
의존성·앱·플랫폼 지원을 추가하지 않습니다.
[일반 파동 계약](startup_waves.md)을 함께 참고하세요.
