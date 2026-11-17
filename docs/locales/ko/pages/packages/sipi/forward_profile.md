# 다도체 선로의 명시적 진행파 전류 입력

`rlgc_forward_profile`은 기존의 전체 행렬 특성 해를 사용하여 균일한
상반 선로에서 지정한 전류 입력을 위치별로 계산합니다. 모든 도체 사이의
결합을 보존합니다. 시작점 전류가 0인 도체에도 전압이 유도되거나 진행하면서
전류가 생길 수 있습니다. 대응하는 정합 연장이 있는 순수 진행파를 계산하며,
소스·부하 반사는 종단 회로 계산에서 다룹니다.

```python
import numpy as np
from sipi.forward_profile import rlgc_forward_profile

profile = rlgc_forward_profile(
    [1e9, 3e9],
    R=np.array([[2., .2, .1], [.2, 3., .2], [.1, .2, 2.5]]),
    L=np.array([[3., .4, .2], [.4, 3.5, .3], [.2, .3, 4.]])*1e-7,
    G=np.eye(3)*.002,
    C=np.array([[1.5, -.1, -.05], [-.1, 1.8, -.1], [-.05, -.1, 2.]])*1e-10,
    launch_current=[.01, -.01, 0.],  # Peak A, explicit conductor order.
    positions=[0., .01, .02],       # Metres from the launch plane.
    names=('left', 'middle', 'right'),
)
assert profile.voltage.shape == (2, 3, 3)
assert np.array_equal(profile.current[:, 0, 2], [0., 0.])
assert np.all(profile.power[:, -1] < profile.power[:, 0])
```

주파수는 양의 Hz이며 DC는 제외합니다. `launch_current`는 모든 주파수에
공유하는 복소 피크 전류 `(N,)` 또는 명시적 `(F,N)` 배열입니다. 단위는 A이며
전류 정규화나 RMS 환산은 하지 않습니다. `positions`는 비어 있지 않은
엄격한 오름차순의 유한한 비음수 거리 배열이며 단위는 m입니다. 첫 위치가
0일 필요는 없습니다. RLGC는 `(N,N)` 또는 `(F,N,N)`이며 기존 상반성·수동성
입력 조건과 조건수 제한을 유지합니다. 주파수 표본만으로 재료 인과성을
인증하지 않습니다.

부호 규약은 exp(+j omega t)이며 전류의 양의 방향은 +z입니다.
V0=Zc I0, V(z)=exp(-Gamma_voltage z)V0, I(z)=Yc V(z)를 사용합니다.
`voltage`와 `current`는 `(F,P,N)` 모양의 V와 A입니다.
실수 `power`, `conductor_loss`, `dielectric_loss`는 `(F,P)` 모양입니다.

- P = Re(V^H I)/2: 평균 전달 전력, W.
- qR = Re(I^H R I)/2: 도체 손실, W/m.
- qG = Re(V^H G V)/2: 유전체 손실, W/m.

교차항을 모두 보존합니다. 이는 전체 전력이며 도체별 독립 손실이나 모드별
감쇠 상수가 아닙니다. 국소 보존식은 dP/dz=-(qR+qG)입니다. 전력과 손실을
잘라내지 않으므로 기존 PSD 입력 조건에서 허용한 반올림 오차는 그대로
남습니다. 영 전류 입력의 출력은 0이며 유한하지 않은 계산은 거부합니다.
배열은 입력을 복사한 읽기 전용 결과입니다. `ForwardWaveProfile`을 직접
생성하면 모양을 검사할 뿐 물리를 인증하지 않습니다.

검증은 스칼라 폐형식, 비직교 전압·전류 쌍대 좌표 변환으로 구성한 해,
3·4도체의 독립 2N 상태 고유공간, 손실 적분과 국소 전신방정식 전력 보존,
도체 순열 및 복소 진폭 배율을 포함합니다. 검증 범위는 RLGC 대수입니다.
새 전계 추출·임의 종단·단일/차동 목표·모드 추적·저장 스키마·UI를 추가하지
않으며 새 기하·전계 메시·실측 정확도·플랫폼의 수락을 뜻하지 않습니다.

[English](../../../../../packages/sipi/forward_profile.md)
