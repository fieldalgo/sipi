# 두 신호 시작 응답의 혼합 경계

[명시적 용량성 부하](coupled_capacitive_startup.md)는 내부/외부 에너지를 구분하는 별도 API입니다.

[명시적 저장 v2](coupled_boundary_startup_document.md)로 혼합 종단을 JSON/공통 실행에 연결합니다.

`coupled_boundary_ladder_response`는 이상/저항 소스와 저항/개방/단락 부하를
각각 선택하는 유한 수동 두 신호 RLGC 회로입니다.
[양의 저항 회로](coupled_startup.md)와 별도 API이며 기존 API 및 저장 v1의
종단 제한은 그대로 유지합니다.

```python
import numpy as np
from sipi import coupled_boundary_ladder_response

t = np.linspace(0., 12e-9, 121)
drive = np.column_stack((np.minimum(t/2e-9, 1.), -.4*np.minimum(t/3e-9, 1.)))
r = coupled_boundary_ladder_response(t, drive,
    R=[[25., 2.], [2., 17.]], L=np.array([[510., 70.], [70., 430.]])*1e-9,
    G=[[.003, -.0002], [-.0002, .0015]],
    C=np.array([[230., -30.], [-30., 190.]])*1e-12,
    length=.1, cells=32, source_resistance=[0., 37.], load_resistance=[0., None])
np.testing.assert_array_equal(r.voltage[:, 0], drive[:, 0])
assert np.all(r.voltage[:, 2] == 0) and np.all(r.current[:, 3] == 0)
assert r.power_balance_relative_error <= 1e-10
assert r.to_dict()['input']['load_resistance_ohm'] == [0., None]
```

## 명시적 경계 계약

두 저항 인자는 각각 정확히 2개 항목입니다. 소스는 유한한 비음수 옴이며 0은
이상 전압원입니다. 각 부하는 유한 비음수 옴(0은 단락) 또는 `None`(개방)입니다.
숫자 필드 bool, 스칼라 확장, 무한대와 문자열 경계 이름은 거부합니다. 예제는
도체 0의 이상 소스/도체 1의 유한 소스, far 도체 0의 단락/도체 1의 개방입니다.

공유 두 신호 core 계약은 동일합니다. R/G는 음의 고유값 보정 없이 정확히 대칭인
실수 2x2 PSD, L/C는 정규화 고유값 비가 1e-12보다 큰 SPD, 길이는 유한 양수입니다.
명시적 1..128셀, 0에서 시작하고 엄격히 증가하는 2..10000표본을 사용하며 간격은
상대 1e-10 이내 균일해야 합니다. `(표본 수,2)` PWL 소스는 첫 행 0이고 마지막
값을 유지합니다. 초기 에너지나 커패시터 impulse를 추정하지 않습니다. 모두 SI입니다.

## 질량 행렬이 필요한 이유

각 구간은 전체 R*dx/L*dx, 각 노드는 G*dx/C*dx이며 끝은 절반 가중치입니다.
이상/단락 고정 전압을 동적 미지수에서 제거합니다. 한 전압만 고정할 때 이미
역행렬을 취한 상태 행렬의 행/열만 제거하면 상호 커패시턴스 미분 항이 사라집니다.

M*x_dot=K*x+B*u에서 자유/고정 값 xf,xp를 나누고 T=Mff^-1*Mfp,
z=xf+T*xp로 두면 z_dot=Mff^-1*Kff*z + Mff^-1*(Kfp-Kff*T)*xp + Mff^-1*Bf*u입니다.
xp는 PWL 소스 일부 또는 0이므로 기존 SciPy lsim으로 z를 전파하며 불연속 소스
기울기를 보간하지 않습니다. 이후 xf=z-T*xp와 미분을 복원합니다. 초기 값은
모두 0입니다.

이상 소스 전류는 C_end*V_dot+G_end*V+첫 구간 전류, 단락 부하 전류는
C_end*V_dot+G_end*V−마지막 구간 전류입니다. 다른 도체 전압 미분도 포함한 전체
행렬 곱입니다. 유한 소스는 (drive−V)/Rs, 유한 부하는 −V/Rl, 개방 전류는 0입니다.
미분은 오른쪽 PWL 기울기이며 마지막 표본은 0입니다. 다른 소스가 유한 저항일 때
부분 이상 소스가 시작 순간 보는 용량은 단순 C00*dx/2가 아닌
(C00−C01*C10/C11)*dx/2의 Schur 커패시턴스입니다.

## 결과와 수락

`MixedBoundaryRLGCLadderResponse`는 두 신호 응답 저장/직렬화를 재사용하면서
혼합 경계 scope와 null 부하를 명시합니다. 포트 순서는 near_0,near_1,far_0,far_1,
모든 전류는 선로 안 방향입니다. 노드/구간은 도체 축을 유지하고 배열은 읽기 전용
복사입니다. `to_dict(include_states=True)`로 내부 상태를 선택적으로 포함합니다.
에너지/전력은 두 도체 합계이며 음의 귀환 전력을 유지합니다. 전체 이차 에너지,
회로 우변 에너지율과 내부 R/G 손실에 비음수/유한성 및 상대 전력 잔차 1e-10 이하
기준을 적용합니다. 소스/부하 저항 손실은 별도이고 이상/단락/개방은 저항 손실이
없습니다. 자유 질량 행렬이 수치적으로 특이하거나 계수/상태가 표현 범위를 벗어나면
오류입니다.

독립 1셀 결합 RL ramp 해석식으로 구간 전류와 전체 끝 커패시터 소스 전류를
검사합니다. 부분 이상 소스의 초기 전류는 위 Schur 식으로 검사합니다. 양의 유한
종단은 기존 32셀 회로와 1e-10 V/1e-12 A 이내로 일치합니다. 결합 0이면 단일
혼합 경계 API로 환원되며 순열·시간/임피던스 스케일·0 입력·펄스 귀환 전력·엄격
입력도 검사합니다.

양의 저항 API 예제의 교환 대칭 행렬, R=G=0, 길이 .1 m, 첫 도체 0..2 ns의
1 V ramp/둘째 0, 0..12 ns의 1201표본에서 정확 공통/차동 지연 해를 물리 좌표로
복원해 비교합니다. Rs=0/25옴과 Rl=0/개방/100옴의 6조합을 32/64/128셀로 세분하면
오차가 감소하고 128셀에서 .02 V/.0005 A 기준을 통과합니다. 최종 최대 전압 오차는
.007831 V(이상/개방), 전류는 .000231 A(이상/단락)입니다. 모든 소스·선로·시간에
128셀이 충분하다는 의미는 아닙니다.

별도 노드별 KCL/DOP853으로 코드 예제의 비대칭 행렬·혼합 종단을 16셀에서
대조합니다. rtol1e-10/atol1e-12, 최대 step은 최소 모드 지연/(5*cells)이며 최대
차이는 1e-8 V/1e-9 A 이하입니다. 고정 전압의 미분을 자유 노드 방정식에 명시합니다.
같은 유한 회로의 다른 전파 알고리즘이며 별도 공간 이산화가 아닙니다.
SciPy1.18.1은 기존 BSD-3-Clause 의존성입니다.

상수 두 신호 유한 회로이며 리액티브 외부 부하, 임의 재료 분산, 추가 도체,
일반 TDR/eye/BER, 실측 기판 정확도나 자동 수렴은 포함하지 않습니다. 새 의존성은
없습니다. 저장 입력 연결 및 브라우저/Windows 지원은 별도 검증이 필요합니다.

[양의 저항 회로](coupled_startup.md) · [단일 혼합 종단](rlgc_startup.md) ·
[English](../../../../../packages/sipi/coupled_boundary_startup.md)
