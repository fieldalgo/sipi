# 3·4신호 Debye 시작 응답

[English](../../../../../packages/sipi/multiconductor_debye_startup.md) | **한국어**

`multiconductor_debye_rlgc_ladder_response`는 3·4신호, 양의 저항 종단,1·2개 Debye
강도를 명시한 초기0 유한 회로를 전파합니다. [상수 다신호 회로](multiconductor_startup.md)에
별도 API/결과형으로 분산 모델을 추가하며 기존 [2신호 Debye 계약](coupled_debye_startup.md)의
허용 입력과 결과를 유지합니다.

```python
import numpy as np
from sipi import multiconductor_debye_rlgc_ladder_response

n = 3
time = np.linspace(0., 12e-9, 121)
drive = np.minimum(time / 2e-9, 1.)[:, None] * [1., -.4, .2]
result = multiconductor_debye_rlgc_ladder_response(
    time, drive, signals=n, R=np.diag([20., 23., 26.]),
    L=np.diag([450., 480., 510.]) * 1e-9,
    G=np.diag([.002, .0022, .0024]),
    C_inf=np.diag([210., 220., 230.]) * 1e-12,
    delta_C=np.array([np.diag([130., 143., 156.]),
                      np.diag([50., 55., 60.])]) * 1e-12,
    relaxation_hz=[8e7, 7e8], length=.1, cells=4,
    source_resistance=[25.] * n, load_resistance=[100.] * n)
assert result.voltage.shape == (121, 6)
assert result.polarization_charge.shape == (121, 5, 2, 3)
assert result.power_balance_relative_error <= 1e-10
assert result.total_power_balance_relative_error <= 1e-10
```

exp(+jωt) 관례에서 입력 정전용량은
`C(f) = C_inf + sum(DeltaC[p] / (1 + j*f/relaxation_hz[p]))`입니다.
R[옴/m]·L[H/m]·G[S/m]·C_inf/DeltaC[F/m]는 유한한 실수이며 정확히 대칭인 N×N
행렬입니다. L/C_inf는 양의 정부호이고 R/G와 각 DeltaC는 양의 정부호 또는
정확히0이어야 합니다. 모든 비0 행렬의 정규화 고윳값 비율은1e-12보다 커야
합니다. 대칭 보정·클리핑·특이 PSD 수락은 없습니다. 강도가0인 pole도 양의
유한한 Hz를 명시합니다. 소스/부하 저항은 양의 유한한 실수 N개(옴)입니다.

`signals`는3 또는4를 명시하고 cells1..64,time2..10000,시간 간격 상대1e-10 이내
균일,시간0 시작,drive(times,N)의 첫 행0을 요구합니다. PWL 소스와 모든 회로
상태는0에서 시작합니다. 개수는 자원 상한이며 실행 시간/정확도 보장이 아닙니다.
각 셀의 직렬 R/L과 양끝 절반 C_inf/G를 사용합니다. 활성 pole은 tau=1/(2π fp)의
`tau*w'=V-w` 보조 벡터를 추가합니다. 정확히0인 강도는 내부 상태를 생략하면서
선언한 pole 순서와0 출력 열을 유지합니다. 상태 수는
N*(2*cells+1)+활성pole수*N*(cells+1), 최대1036입니다.

노드/구간 배열은(time,node_or_segment,signal), 단자는 모든 near 뒤에 모든 far
순서입니다. 양단 전류는 선로 안으로 들어가고 구간 전류는 far 방향입니다.
분극 배열은(time,node,선언pole,signal)입니다. 전하·전류는 셀 길이와 양끝 절반
가중치를 포함하여 q=dx*weight*DeltaC*w,iq=dx*weight*DeltaC*w'입니다. 순간
에너지/율과 분극 에너지/율을 구분하고 완화 손실·R/G·소스/부하 저항 손실을
포함한 선로/전체 소스 전력 수지는 각각 상대1e-10을 요구합니다. 저장 에너지와
손실은 유한하고 음수가 아니어야 합니다.

```python
import json
saved_result = result.to_dict(include_states=True)
json.dumps(saved_result, allow_nan=False)
assert result.port_names == ('near_0', 'near_1', 'near_2',
                             'far_0', 'far_1', 'far_2')
assert not result.voltage.flags.writeable
np.testing.assert_allclose(result.total_energy,
                           result.energy + result.polarization_energy,
                           rtol=0., atol=0.)
```

결과 `MulticonductorDebyeRLGCLadderResponse`는 복사된 읽기 전용 배열입니다.
`to_dict`는 결과 내보내기이며 버전 있는 저장 요청/실행 스키마가 아닙니다.
[명시한6·8단자 파동 변환](multiconductor_debye_startup_waves.md)은 호출자가
제공한 양의 실수 기준 저항과 함께 이 결과형을 수락합니다. 명시한
[버전 저장 입력](multiconductor_debye_startup_document.md)은 이 API 계약을 보존합니다. 입력과 내보낸
사전은 독립적이며 비유한 전파·잘못된 초기 상태·전력 수지 실패는 오류입니다.

대각/직교 모드와 scalar Debye,2+1/2+2 블록과 기존 scalar/2신호 식을 절대
V1e-10/I1e-12에서 대조합니다. 별도 charge-state KCL DOP853은 비가환3/4신호
행렬을 V1e-8/I1e-9에서 검사했고 연구 최대 전압 차이는1.14e-14V였습니다.
0강도 상수 회로 한계·시간/임피던스/소스 크기 scale·신호/pole 순열·집중 전하
단위를 검사합니다. 별도 느린 pole10k/1k/100Hz는 상수 C_inf 응답으로, 빠른
pole10/100/1000GHz는 C_inf+sum(DeltaC) 응답으로 접근하며 명시한 유한 회로에서
전압 차이 감소와 최종1e-3V 미만을 요구합니다. 공유 helper의 기본2신호 차원 변경 전 strict/PSD/외부C/외부RL
2신호 결과 내보내기48개의 정확한 해시를 유지합니다.

명시한 모드 모델에서 scikit-rf2.2.0 독립 분포 선로 ABCD 기준과100/500MHz의
16/32/64셀 전압 차이가 감소합니다.64셀에서3/4신호 최대 차이는 각각9.43e-6V와
2.68e-4V로 원래1e-3V 기준 이내입니다. 동일 유한 회로 주파수 기준에 대한
주기당128/256/512 시간 샘플은 보간 오차 감소를 별도로 확인합니다.8/9/10주기
중 마지막4주기 phasor 차이는 최대1.51e-10V로1e-8V 이내입니다. 이 기준은
시험 입력에 한정되며 다른 입력은 시간/소스/공간을 다시 세분해야 합니다.
scikit-rf는 기존 BSD-3-Clause 고지를 유지한 시험 전용, SciPy는 기존 전파
의존성입니다. 새 런타임 의존성은 없습니다.
새3/4신호 경로는 빠른 pole의 상쇄를 줄이도록 인수 형태의 완화식과 노드/구간
보존식으로 미분값을 복원합니다. 최초 빠른 pole 점별 전력 검사는 최대1.9e-14W
차이로 실패했으며 수정 후 원래 rtol1e-10/atol1e-15를 그대로 통과합니다.
수정 전후6개 사례의 전파 상태와 저장/손실 에너지는 정확히 같고 기존2신호
계산 순서는 유지합니다. 원래 실패 근거도 보존합니다.

집중 회로이며 Maxwell FDTD/장 추출이 아닙니다. 일반 특이 PSD강도/R/G·이상적/
개방/단락/전류원/리액티브 종단·임의 분산/피팅·실측 기판 정확도·앱/플랫폼 지원·
자동 파동/저장 연결은 이 계약에 포함하지 않습니다.
