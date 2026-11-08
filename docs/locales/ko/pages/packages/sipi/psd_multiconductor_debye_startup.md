# 다신호 PSD Debye 시작 응답

[English](../../../../../packages/sipi/psd_multiconductor_debye_startup.md) | **한국어**

`psd_multiconductor_debye_rlgc_ladder_response`는3·4신호 영 초기 상태
유한 회로의 별도 `PSDMulticonductorDebyeRLGCLadderResponse`를 반환합니다.
특이 양의 준정부호 R/G와 Debye 강도 행렬을 수락합니다.
[기존 strict 강도 API](multiconductor_debye_startup.md)와 해당 저장/파동 계약의
허용 범위는 유지합니다.

```python
import numpy as np
from sipi import psd_multiconductor_debye_rlgc_ladder_response

t = np.linspace(0., 4e-9, 41)
r = psd_multiconductor_debye_rlgc_ladder_response(
    t, np.minimum(t/1e-9, 1.)[:, None]*[1., -.4, .2], signals=3,
    R=np.diag([20., 0., 26.]), L=np.diag([450., 480., 510.])*1e-9,
    G=np.diag([.002, .0022, 0.]), C_inf=np.diag([210., 220., 230.])*1e-12,
    delta_C=np.array([np.diag([150., 0., 0.]), np.zeros((3,3))])*1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.]*3, load_resistance=[100.]*3)
assert r.voltage.shape == r.current.shape == (41, 6)
assert r.polarization_voltage.shape == (41, 5, 2, 3)
assert np.any(r.polarization_voltage[:, :, 0, 1:])
assert not np.any(r.polarization_charge[:, :, 0, 1:])
assert not np.any(r.polarization_voltage[:, :, 1])
assert r.inputs['signals'] == 3
```

입력은 명시한 실수·정확 대칭 N×N 행렬입니다. R[ohm/m]·G[S/m]와1–2개의
DeltaC[F/m]는 PSD이며 L[H/m]·C_inf[F/m]는 정규화 고유값 비율이1e-12보다
큰 SPD여야 합니다. 양의 완화 주파수는 Hz이고 식은
`C(f)=C_inf+sum(DeltaC/(1+j*f/fp))`입니다. 대칭 복구·음의 고유값 클리핑·
rank 임계값을 사용하지 않습니다. 특이 행렬 근처 수치 부호 모호성을 포함해
계산된 정규화 고유값이 하나라도 음수면 거부합니다. 수학적으로 PSD인 모든
부동소수점 표현을 수락한다고 보장하지 않는 보수적 규칙입니다. 작지만 양인
대각 강도는0으로 바꾸지 않습니다.

명시한 `signals`는3 또는4, `cells`는1–64입니다. 균일한 시간2–10000행은
0에서 시작하고 drive(time,N)의 첫 행은0입니다. 양단 소스/부하 저항 벡터는
각각 N개의 양의 유한 값을 요구합니다. 길이 단위는 m입니다. 스칼라 저항
자동 확장·ideal/open/short/리액티브/전류 종단을 추론하지 않습니다. 개수 제한은
자원 상한이며 정확도·실행 시간 보장이 아닙니다.

유한 pi 회로는 양 끝 병렬 C/G에 절반 가중치를 사용합니다. 각 비영 강도는
DeltaC 역행렬 없이 정규 보조 전압 `tau*w'=V-w`를 따릅니다. null 방향 w는
관측할 수 없는 저역 통과 상태이며 측정된 분극 좌표가 아닙니다. 그 방향은
분극 전하·전류·에너지·완화 손실에 기여하지 않습니다. 정확히0인 강도는
상태를 생략하고 출력0열과 선언한 pole 순서를 보존합니다. 배열 축은
(time,node,pole,signal)이며 전하/전류는 절반 끝점 가중치를 포함한 노드 집중
C/A입니다. 상태 수는 N*(2*cells+1)+active_poles*N*(cells+1)입니다.
SciPy lsim이 기존 정규 PSD 커널로 영 초기 상태 PWL 보간 입력을 전파합니다.
기존2신호·strict 다신호 경로는 변경하지 않습니다. 다신호 도함수의 인수분해
계산은 큰 완화 행렬 곱의 상쇄를 피하면서 원래 전력 검사를 유지합니다.

```python
np.testing.assert_allclose(
    r.total_energy_rate,
    r.line_power - r.series_loss - r.shunt_loss - r.relaxation_loss,
    rtol=1e-10, atol=1e-15)
assert max(r.power_balance_relative_error,
           r.total_power_balance_relative_error) <= 1e-10
assert not r.polarization_charge.flags.writeable
assert r.port_names == ('near_0', 'near_1', 'near_2', 'far_0', 'far_1', 'far_2')
assert r.to_dict()['scope'] == 'finite-passive-psd-multiconductor-debye-ladder-startup'
```

단자는 near N개 뒤 far N개이고 양단 전류는 선로 안으로 들어갑니다.
순간/분극 에너지와 변화율을 구분합니다. 직렬·병렬·완화·소스 저항·부하 저항
손실은 비음수이며 선로/소스 전력 수지에 각각 상대1e-10 기준을 유지합니다.
비유한·표현 불가·음의 진단값은 클리핑하지 않고 거부합니다. 내보내기는 독립
읽기 전용이며 `to_dict(include_states=True)`가 노드·분극 상태를 포함합니다.

독립 검증은 대각/블록 scalar Debye 모드와2+1/2+2 PSD 회로 한계를 절대
V1e-10/I1e-12로, 별도의 비가환 전하 상태 node KCL DOP853을 V1e-8/I1e-9로
비교합니다. scikit-rf2.2.0 독립 분포 선로 scalar ABCD 대조는100/500MHz에서
16/32/64cell 오차 감소와 최종<=1e-3V를 요구합니다.128/256/512샘플과8/9/10주기
검사는 PWL/정착 오차를 따로 확인합니다. 지정 fixture의 기준이며 임의 대역이나
보드 정확도 보장이 아닙니다. null/근영 강도·양의 강도 일치·pole/신호 순열·
선형/시간/임피던스 스케일·느린/빠른 pole 한계·기존 strict API 거부·읽기 전용
복사·원래 실패 검사를 포함합니다. 기존 전체 상태 응답64건은 소스/설치본에서
정확한 해시를 유지합니다.

아직 저장 문서·단자 파동 변환에 연결하지 않습니다. 별도 결과형으로 상속에
따른 암묵적 수락을 피합니다. 장 추출·분산 피팅·임의 종단·FFT/TDR·플랫폼
연결·실측 정확도를 추가하지 않습니다. [2신호 PSD 계약](psd_debye_startup.md)을
참고하세요. SciPy/scikit-rf는 기존 의존성/시험 기준과 고지를 유지하며 새
의존성은 추가하지 않습니다.
