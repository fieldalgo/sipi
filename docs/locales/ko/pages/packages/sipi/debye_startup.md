# 수동 Debye 시작 응답

`debye_rlgc_ladder_response`는 초기 저장 에너지가 0인 명시적 단일 신호
유한 선로 회로를 계산합니다. 상수 R/L/G와 순간 정전용량에 유전체 완화
상태를 추가하며, 모든 극점은 사용자가 입력합니다.

C*(f) = C_inf + sum(delta_C / (1 + j f / relaxation_hz)).

`R`은 0 이상 ohm/m, `L`은 양수 H/m, `G`는 0 이상 S/m, `C_inf`는
양수 F/m입니다. `delta_C`는 0 이상인 F/m 값 1–4개, `relaxation_hz`는
동일 개수의 양수 Hz 값입니다. 순서·같은 완화 주파수·0 강도를 보존합니다.
재료·기하·유전율·주파수 표로부터 입력을 자동 추정하지 않습니다.

```python
import numpy as np
from sipi import debye_rlgc_ladder_response

t = np.linspace(0., 12e-9, 241)
a = debye_rlgc_ladder_response(t, np.minimum(t/2e-9, 1.),
    R=20., L=500e-9, G=.002, C_inf=200e-12,
    delta_C=[150e-12, 50e-12], relaxation_hz=[1e9, 1e8],
    length=.1, cells=32, source_resistance=25., load_resistance=100.)
assert a.voltage.shape == (241, 2)
assert a.polarization_charge.shape == (241, 33, 2)
assert a.total_power_balance_relative_error <= 1e-10
result = a.to_dict()
assert not result['states_included']
```

셀 수는 1–128, 시간은 0부터 시작하는 균일 간격 표본 2–10000개입니다.
실수 전압 입력은 시간과 같은 길이이며 첫 값은 0입니다. 표본 사이를
직선으로 연결하고 마지막 값은 유지하며 마지막 기울기는 0으로 정의합니다.
소스·부하 저항은 유한한 0 이상 값입니다. 소스 0은 이상 전압원,
부하 0은 단락, 부하 `None`은 개방입니다. 두 포트 전류 모두 선로 안으로
들어가는 방향이며 구간 전류는 부하 방향입니다. 자원 제한은 정확도나
실행 시간 보장이 아닙니다.

셀마다 직렬 R/L과 병렬 G/C_inf를 두며 양끝 병렬 소자는 절반 가중치입니다.
활성 극점마다 tau = 1/(2 pi relaxation_hz), tau dw/dt = V - w입니다.
`energy`/`energy_rate`는 C_inf/L만 포함합니다. `polarization_energy`는
sum(C_pole w²)/2, `polarization_energy_rate`는 그 변화율,
`relaxation_loss`는 sum(C_pole (V-w)²/tau)입니다.
`total_energy`/`total_energy_rate`는 두 저장 항을 합한 값입니다.
모두 선로 전체의 J/W 단위이며 선로 포트 및 소스 공급 전력 보존을 각각
상대 오차 1e-10 이내로 검사합니다. 양종단 저항 손실도 포함하며,
반환 에너지를 인위적으로 잘라내지 않습니다.

분극 전압·전하·전류 배열은 (시간, 노드, 선언한 극점) 순서이고 단위는
V/C/A입니다. 전하는 노드별 집중 정전용량과 양끝 절반 가중치를 포함합니다.
0 강도 열은 0으로 보존하되 내부 동적 상태에서는 제외합니다. 배열은 복사된
유한 읽기 전용 값이며 `inputs`는 새 복사본입니다.
`to_dict(include_states=True)`는 단위가 명시된 내부 상태도 포함합니다.
이 결과 직렬화는 실행 가능한 버전 저장 요청이 아닙니다. 기존 상수 RLGC 및
파동 어댑터의 입력 계약과는 구분합니다.

## 독립 검증과 제한

1셀 이상 전압원·단락의 ramp/hold에서 인덕터와 Debye 전하 해석해를
검증했습니다. 강도 0은 기존 상수 RLGC와 일치합니다. 별도 전하 상태를
사용하는 노드 KCL·SciPy DOP853 계산은 1/2극점, 이상/유한/개방/단락
사례에서 1e-8 V/1e-9 A 이내로 일치합니다. 극점 분할·순열,
전압/시간/임피던스 배율, 6종 경계와 에너지 검사를 함께 사용합니다.
입력을 일관되게 지정하면 정전용량 함수가
`C0 * DebyeDielectric.permittivity(f)`와 일치합니다.

연속 scikit-rf ABCD 비교는 32/64/128셀과 마지막 4주기 phasor를 사용합니다.
100 MHz에서 8주기·주기당 1024표본의 전압 오차는
23.0454/5.40911/2.10120 microvolt입니다. 500 MHz와 1 GHz에서는
20주기·주기당 256표본으로 각각 1.49601/.377782/.101349 mV,
5.42325/1.35706/.343489 mV입니다. 모두 셀 증가에 따라 감소하며
128셀에서 1 mV 이하입니다. 100 MHz 독립 유한 회로 주파수해 대비 오차는
256/512/1024표본에서 40.9758/10.1580/2.53950 microvolt로 감소합니다.
7/8/9주기 phasor 차이는 1e-8 V 이내입니다.

최초 100 MHz·256표본 시험은 시간 입력의 직선 근사 오차가 지배하여
공간 오차 감소 조건을 실패했습니다. 6주기 정착 시험도 1e-8 V를 넘었습니다.
별도로 지정해 통과한 설정을 이 실패 설정의 수락 근거로 사용하지 않습니다.
API는 사용자의 시간 간격이나 관측 길이를 자동 변경하지 않습니다.
각 용도에서 입력·시간·공간 수렴을 확인해야 합니다.

범위는 유한 수동 회로입니다. 일반 분산장 추출, 주파수 의존 도체 손실,
결합 Debye 행렬, 임의 부하, TDR 해석이나 실측 기판 정확도를 뜻하지 않습니다.
새 의존성은 없으며 SciPy 1.18.1과 시험 전용 scikit-rf 2.2.0은 기존
라이선스·고지 검토를 따릅니다. 웹·Windows 연결은 별도입니다.
[명시적 단자 파동](startup_waves.md)은 분극 전력 보존을 유지합니다.

[상수 RLGC](rlgc_startup.md) · [주파수 유전체](dielectrics.md) ·
[English](../../../../../packages/sipi/debye_startup.md)

[입력 저장](debye_startup_document.md)은 별도의 실행 가능한 요청 계약입니다.
