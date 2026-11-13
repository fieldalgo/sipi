# 고주파 도체 표면 손실

[English](https://github.com/fieldalgo/sipi/blob/main/docs/packages/sipi/conductor.md) | **한국어**

[단면](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/overview.md) · [균일 전송선 네트워크](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/network.md)

`sipi.conductor.surface_conductor_loss`는 유한 두께 단면의 **신호·접지** 표면에서
도체 R과 고주파 내부 L을 구합니다. 완전도체 장에 표면 임피던스를 적용하는 1차 섭동 모델이며,
금속 내부의 전류 확산을 풀지는 않습니다. 기존 `CrossSection.analyze()`는 외부 L과
유전체 C/G를 계속 반환하고 도체 손실을 암묵적으로 더하지 않습니다.

```python
import numpy as np
from sipi import coupled_microstrip
from sipi.conductor import surface_conductor_loss

section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3,
                            thickness=50e-6, eps_r=4)
mesh = dict(edge_size=2.5e-6, far_size=.1e-3, grade=.05)
f = np.array([1e9, 4e9, 10e9])
loss = surface_conductor_loss(section, f, conductivity=58e6,
                             ground_thickness=35e-6, **mesh)
dielectric = section.analyze(**mesh)
network = loss.network(C=dielectric.C, G=np.zeros((2, 2)), length=.03)
loss.R, loss.L_internal, loss.skin_depth, loss.factors.current_error
```

매끈한 금속과 무손실·주파수 불변 유전체의 예입니다. 모든 단위는 SI입니다.
실행 예제: [`conductor_loss.py`](https://github.com/fieldalgo/sipi/blob/main/examples/sipi/conductor_loss.py).

## 계약과 유효 범위

- 주파수는 비어 있지 않고 엄격히 증가하는 1차원 Hz 배열이며 **f > 0**이어야 합니다.
  전도도(S/m), 상대 투자율, 접지 두께 `ground_thickness`(m)는 양의 유한 실수이며 bool은 거부합니다.
  구리 재료나 접지 두께를 암묵적으로 선택하지 않습니다.
- 모든 신호·접지는 같은 금속을 사용합니다. 외부는 비자성이고 `relative_permeability`는 금속에만 적용합니다.
- 모든 trace는 양의 두께가 필요합니다. 최대 표피 깊이는 각 trace의 두께·위/아래 폭,
  접지 두께·상자 폭의 1/5 이하여야 합니다. `sigma/(omega*eps0) >= 1000`도 요구합니다.
  이는 필요조건으로 곡률·근접·섭동·상자·이산화 오차를 제한하지 않습니다. 날카로운 모서리는
  이 조건을 만족해도 메시 세분이 필요합니다.
- 기본 `roughness_rms=0`입니다. 양수이면 Hammerstad 경험식
  `1 + (2/pi)*atan(1.4*(Rq/delta)**2)`를 **R에만** 곱하며 매끈한 금속의 리액턴스는 유지합니다.
  인과적 광대역 거칠기 모델, 실측 표면 보정 또는 형상 변경이 아닙니다.
  [인과적 Huray](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/roughness.md)는 명시 구 반지름·면적비를 받아 R과 내부 L을 함께
  보정합니다. `roughness=CausalHuray(...)`로 선택합니다. 별도 [Groiss RMS](groiss.md)는
  전체 임피던스에 실수인 비인과적 주파수영역 계수를 곱합니다.
  [Cannonball Huray](cannonball.md)는 명시적 10점 Rz를 인과적 구형 법칙에 연결합니다.
  이 표면 어댑터는 Gradient 거칠기를 지원하지 않습니다.
  별도 [Gaussian 전도율 프로파일 커널](conductivity_profile.md)은 명시적 기준면의
  1D 외측 포트 임피던스를 반환하며 이 어댑터의 승수나 선로 인덕턴스 보정이 아닙니다.
- 잘못된 재료·표피 깊이 입력은 메시 전에 거부합니다. 적분한 단위 전류 행렬의 최대 차이가
  0.05를 넘으면 세분을 요구하는 `ValueError`를 냅니다. **저항 오차 5% 보장이 아닙니다.**
  R 자체의 세분 변화와 상자 크기 영향은 별도로 확인해야 합니다.

`ConductorLoss`의 주파수·`skin_depth`(m)·`roughness_factor`(실수 저항비)·`R`(Ω/m)·
`L_internal`(H/m)은 복사한 읽기 전용 배열입니다. R/L은 `(F,N,N)`이며 비대각 성분을 보존합니다.
`.factors`는 C0, `(N+1,N,N)` 표면 적분, `(N+1,N)` 적분 전류를 제공합니다.
표면 순서는 `.names`의 신호 순서 다음에 **모든 접지를 합한 그룹**입니다.
직접 만든 결과 객체는 모양과 유한성만 확인하므로 실제 해석 수행이나 물리 유효성을 증명하지 않습니다.

`.network(C=..., G=..., length=..., z_ref=50)`는 이 R 및 `L_external + L_internal`을
기존 RLGC 솔버에 넘깁니다. 호출자가 **같은 형상·도체 순서·주파수**의 C/G를 공급해야 하며,
배열 모양만으로 일치를 확인할 수 없습니다. 측정 불러오기·형상 JSON 변경·웹 화면·실행파일 포장은 포함하지 않습니다.

## 계산

exp(+j omega t)에서 매끈한 반공간 도체는 다음과 같습니다.

```text
delta = 1 / sqrt(pi f mu sigma)
Zs = (1+j) sqrt(pi f mu / sigma)
```

진공 정전 전위 basis V와 에너지 C0를 풉니다. 단위 종방향 신호 전류 i에 대해 전기·자기 쌍대성으로
`K = eps0 d_n(V) inv(C0) i`를 얻습니다. n은 유전체에서 금속으로 향합니다.
자기장은 유전체 가중 장이 아닌 진공 형상을 따릅니다. **모든 신호·귀환** 표면을 적분합니다.

```text
A_ij = integral K_i K_j ds
R(f) = Re(Zs(f)) A
L_internal(f) = Im(Zs(f)) A / (2 pi f)
L_external = mu0 eps0 inv(C0)
```

Gram 형태는 상호적 양의 준정부호 손실을 보존하고 완전도체 기준의 귀환·근접 분포를 포함합니다.
유한 전도도 때문에 달라지는 전류 분포는 풀지 않습니다. 유전체 경계 변에서 P1 요소 기울기를 사용하고
내부의 두께 0 strip은 거부합니다. 하위 `surface_current_factors(mesh, signals, ground)`는
동축 같은 사용자 유전체 메시를 받으며 flux 차이를 보고하되 상위 API의 5% 제한은 강제하지 않습니다.
전기적 열린 경계는 이 쌍대 문제에서 절연 경계이며 무한 공간이 아닙니다.

## 검증과 한계

`tests/sipi/test_conductor.py`, Linux, Python 3.12.14, NumPy 2.5.4,
SciPy 1.18.1, 2026-10-30. 기준은 시험 전에 정했습니다.

| 검사 | 기준 | 결과 |
|---|---|---|
| 폭 2 mm·높이 1 mm 평행판 | 각 표면 factor 1/width, 전류 ±1, 1e-10 | 통과, 총 factor 1000 /m |
| 동축 a=.5 mm·b=2 mm, 반경 64/128/256·각도 256분할 | `(1/a+1/b)/(2pi)`로 오차 감소, 최종 <1% | 3.3833%→1.7224%→0.8681% |
| 위 결합 마이크로스트립, 세 메시 설정 모두 절반 | R 최대변화/고운 R 최대값 <5%, flux <5% | 4.08%, 고운 flux 2.22% |
| 거친 결합 메시 10 µm/.4 mm/.2 | flux >5%이면 거부 | 5.83%, 거부 |
| 매끈한 Rs·표피 깊이 vs scikit-rf 2.2.0 | 상대차 <1e-12 | 2.00e-15, 2.22e-15 |
| R/L 상호성·준정부호, S 상호성·수동성 | 1e-10 | 통과 |

scikit-rf 검사는 **반공간 법칙** 비교로 PCB 장해석이나 거칠기 비교가 아닙니다.
기존 BSD-3-Clause 목록의 도구를 시험에서만 쓰고 런타임 의존성·외부 바이너리는 추가하지 않습니다.
평행판·동축은 형상 적분을 독립적으로 확인합니다. PCB 사례는 해당 형상의 메시 변화이며
실측 손실 정확도나 보편적 오차 한계가 아닙니다.

`8694e70`의 설치 wheel 집중 검증(2026-11-13)은 기존 저항 변화 5% 기준을
유지했습니다. 도체·참조 7건은 Linux·Windows에서 모두 통과했고, macOS ARM64는
4건 통과·관련 PCB 세분 검사 3건 실패입니다. 같은 매끈한 금속 형상의 변화는
Linux·Windows 4.07962%, macOS 5.01444%였습니다. 원·세분 메시 노드 수는 각각
19610/75158과 19582/75157입니다. 실제 macOS 메시를 Linux에서 다시 풀면 기록된
P1 배열의 최대 크기로 정규화한 차이가 7.47e-13 이내이며 저항 변화 실패도 재현됩니다.
이번 실패를 같은 메시의 풀이 차이가 아닌 생성 메시 차이로 분리한 결과이며,
메셔의 어느 연산에서 처음 갈라지는지까지 확인한 것은 아닙니다. 실패 시험은
실패 상태로 유지합니다.

같은 형상의 추가 Linux 관측은 작은 메시 변화가 절대 손실 오차가 아님을
보여줍니다. 세 번째 P1 메시(edge 1.25 µm, far 50 µm, grade .025; 296525노드)의
전체 전류 계수 변화는 이전 세분 메시 대비 3.95719%, 첫 대각 항은 1519.646 /m입니다.
별도 패널 경로의 변당 64/128/256 패널은 degree14·ground modes512에서 각각
1747.183, 1745.546, 1744.857 /m입니다. 마지막 두 해상도를 degree16으로 풀어도
표시한 자릿수는 유지됩니다. 이산화 관측이며 실측 기준·인증된 오차 상한·새 수락
기준이 아닙니다. 특히 P1과 패널의 차이는 연속한 P1 메시 사이의 변화보다 훨씬 큽니다.

이 공통 금속 어댑터는 DC/저주파 전이와 내부 표피·근접 확산을 모델링하지 않습니다.
그 기능은 별도의 [유한 금속 확산 모델](conductor_diffusion.md)에서 다룹니다.
서로 다른 금속·거칠기는 별도 [신호 경계](boundary_conductor.md),
[신호 면](face_conductor.md), [기준 표면](reference_surfaces.md),
[접지 면](ground_faces.md) 할당을 사용하며 표면 섭동 가정은 유지합니다.
유한 전도도의 기준 전류 재분포·실측 쿠폰 보정·전파와 복사는 이 모델의 범위 밖입니다.
DC로 외삽하거나 교류 PDN 솔버로 대체하지 마세요.

참고: E. Hammerstad and Ø. Jensen, “Accurate models for microstrip computer-aided design,”
IEEE MTT-S Digest, 1980(거칠기 경험식); 표준 양도체 표면 임피던스와 준TEM 전기·자기 쌍대성은
위 평행판·동축 극한으로 확인합니다.

test extra를 설치한 환경에서 관련 검증을 실행합니다:

```sh
OPENPHYSICS_REQUIRE_CROSSCHECK=1 python -m pytest -q tests/sipi/test_conductor.py
```

[공유 메시의 주파수 선로 입력](https://github.com/fieldalgo/sipi/blob/main/docs/locales/ko/pages/packages/sipi/line_model.md)은 이 추출과 재료/도체 모델을 연결하고 전체 입력을 JSON으로 저장합니다.

[명시적 경계 패널 전류와 금속별 손실](panel_conductor.md)은 고정 전위 접지 도체를 다루는 선택적 공유 커널 경로이며 패널·외곽 수렴을 별도로 검증합니다.

## 독립 이차 요소 전계 대조

`test_crosscheck_conductor_p2.py`는 같은 진공 기하와 도체 전위를 scikit-fem
12.0.2 이차 삼각 요소로 풉니다. 자체 에너지 정전용량 행렬을 계산하고 4차
경계 구적법으로 법선 미분을 적분합니다. 평행판과 원형 동축 해석 극한으로
기준 계산을 확인합니다. PCB 대조는 원·세분 메시의 경계별 행렬, 상호 항과
전류 적분을 그대로 기록합니다. 이 비교는 보고용입니다. 두 이차 메시의
작은 변화가 정확도를 보증하거나 기존 P1 플럭스·저항·외곽 검사를 대체하지
않습니다. 이차 요소 도구는 시험 의존성이며 제품에서 선택하는 솔버가 아닙니다.
