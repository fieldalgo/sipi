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
| 위 결합 마이크로스트립, 세 메시 설정 모두 절반 | R 최대변화/고운 R 최대값 <6%(2026-11-26 전에는 5%), flux <5% | 4.08%(macOS 5.01%), 고운 flux 2.22% |
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
메셔의 어느 연산에서 처음 갈라지는지까지 확인한 것은 아닙니다. 2026-11-26에 세 시험의
메시 변화 기준을 6%로 바꿨습니다(승인). P1 관측 수렴 차수가 약 0.12라 이 변화는 정확도 척도가
아니고, 유효한 다른 삼각분할만으로 약 1%p 달라지기 때문입니다. flux 기준은 5% 그대로입니다.

같은 형상의 추가 Linux 관측은 작은 메시 변화가 절대 손실 오차가 아님을
보여줍니다. 세 번째 P1 메시(edge 1.25 µm, far 50 µm, grade .025; 296525노드)의
전체 전류 계수 변화는 이전 세분 메시 대비 3.95719%, 첫 대각 항은 1519.646 /m입니다.
별도 패널 경로의 변당 64/128/256 패널은 degree14·ground modes512에서 각각
1747.183, 1745.546, 1744.857 /m입니다. 마지막 두 해상도를 degree16으로 풀어도
표시한 자릿수는 유지됩니다. 이산화 관측이며 실측 기준·인증된 오차 상한·새 수락
기준이 아닙니다. 특히 P1과 패널의 차이는 연속한 P1 메시 사이의 변화보다 훨씬 큽니다.

2026-11-22의 네 단계 측정(edge·far·grade를 매번 절반으로; Linux, 같은 형상)은 이
P1 계수가 얼마나 느리게 수렴하는지 보여줍니다. 첫 대각 항은 19610, 75158, 296525,
1182640노드에서 1404.945, 1464.699, 1519.646, 1570.054 /m입니다(마지막은 제품
메셔 한도 300000점 밖에서 실행). 연속 차이 59.75, 54.95, 50.41 /m의 관측 수렴 차수는
약 0.12입니다. 패널 경로는 1744.857 /m이고, 두 경로의 진공 C0는 5.6e-5 안에서
일치합니다. 같은 메시에서 독립 scikit-fem P2 기준은 1546.896, 1559.606,
1597.804 /m입니다. 따라서 P1 계수는 세분 시험의 두 메시에서 패널 값보다 19.5%,
16.1% 낮고, 118만 노드에서도 10.0% 낮습니다. 그동안 시험의 메시 변화는 약 4%입니다.

이 직사각 단면에서 6%(이전 5%) 메시 변화 검사는 손실 오차의 상한이 아니며, 보통의 메시에서
P1 저항은 10–20% 낮을 수 있습니다. 형상이 맞으면 [경계 패널 경로](panel_conductor.md)를
우선 쓰고, P1 결과는 이 한계를 감안해 해석하세요.
[transmission-line/8](default_line.md)은 `surface`·`surface-boundaries` 도체에 기본으로
panel 전류를 씁니다. 한 형상에 대한 관측이며 일반 오차
상한이나 실측 기준이 아닙니다. 다른 단면은 따로 비교하고 있습니다. 원래 시험·메시·
기준은 바꾸지 않았습니다.

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

[고정 반경 표면 모델 피팅](roughness_fit.md)은 명시적 복소 표면 임피던스를 입력받고 불일치 자료를 보존합니다.

[평면 다층 금속 임피던스](layered_metal.md)는 유한 기하 표면 어댑터와 별도로 반무한 바탕 위의 명시적 얇은 금속 도금층을 해석합니다.

[명시 이중 셀 전류](dual_cell_conductor.md)는 P1 경계 반력을 사용하고 독립 전계와 대조합니다. 대수적 전류 보존과 저항 정확도는 구분하며 저장 선로 기본값을 유지합니다.

[명시 정전용량 형상미분 전류](panel_shape_conductor.md)는 차분 표본을 보존하는
별도 적분 전류 추정법입니다. 차분폭 일치는 패널·외곽 수렴과 구분합니다.

## 보조 복원 전류(부피형 형상 미분)

`sipi.recovered_conductor.recovered_surface_current_factors(mesh, signals,
ground, *, support_fraction=0.4)`는 **보조** 전류 방법입니다.
`surface_current_factors`와 같은 유전체 전용 P1 메시와 도체 절점 집합을 받고,
같은 진공 기저를 풀며 같은 C0를 돌려줍니다. 다른 것은 표면 적분뿐입니다.
`surface_current_factors`, `volume-p1` 방법, panel 기본값과 저장된 모든
문서·결과는 바뀌지 않으며, 이 함수는 저장 문서에서 고를 수 없습니다.

법선 미분 곱의 경계 적분을 영역(Hadamard) 형식으로 바꿉니다. 이는 Wheeler의
증분 인덕턴스 규칙입니다. 각 도체 벽이 단위 법선 변위 theta만큼 물러날 때

```text
integral_Gamma dn(Va) dn(Vb) ds = integral grad(Va) . (D theta + D theta^T - div(theta) I) grad(Vb) dx
```

가 Gamma에서 상수인 조화 함수 Va, Vb와 Gamma 근처에 지지된 theta에 대해
성립합니다. 각 표면 묶음(신호마다 하나, 이어서 모든 기준 도체 함께)마다 theta는
그 묶음의 변에서 바깥 법선 성분이 1인 P1 장이고, 꼭짓점에서
`(n1+n2)/(1+n1.n2)`로 miter하며, `w = support_fraction * 서로 다른 도체 간 최소
간격`에 대한 거리의 C1 차단 함수 `1-3s^2+2s^3`를 곱하고 `w` 밖에서는 0입니다.
P1 요소 기울기는 상수라 부피 적분은 요소마다 정확합니다. 적분 전류는 같은 차단
함수를 스칼라 가중으로 씁니다. 이 일관 플럭스는 반올림 수준에서 단위 전류
목표와 같으므로 여기서 `current_error`는 해상도 부족 신호가 **아닙니다**.
`diagnostics['gradient_current_error']`가 같은 기저의 경계 기울기 플럭스
불일치, 즉 기존 어댑터의 5% 검사가 보는 양을 보고합니다. 다른 진단은
`support_fraction`, `support_width`, `minimum_spacing`(m)과 표면 묶음별
`support_triangles`입니다.

다음은 결과를 돌려주지 않고 `ValueError`로 거절합니다: (0, 0.5) 밖의
`support_fraction`(서로 다른 도체의 지지가 만나면 안 됨), 매끄러운 꺾임(10도
이하, 이산화된 곡선)이나 볼록 직각 금속 모서리가 아닌 꼭짓점(사다리꼴·예각·
오목 모서리 포함), 법선 변위 성분을 가진 채 절연(열린) 벽에 닿는 지지.
아주 좁은 간격과 macOS·Windows는 아직 확인하지 않았습니다.

내부 연구에서 같은 P1 해에 대해 이 복원은 기본 메시 다섯 단면에서 경계 panel
값과 -0.24%~-0.34% 차이였고(경계 기울기 P1 계수는 12%~20% 낮음), 관측 차수는
1.3~2.1, 복원 비용은 P1 해의 0.3~0.9배였습니다. 그 단면들에 대한 관측이며
일반 오차 한계가 아닙니다.

| 검사(`tests/sipi/test_recovered_conductor.py`) | 실행 전에 정한 기준 |
|---|---|
| 평행판, 폭 2 mm, 높이 1 mm | 각 표면 계수 1/폭, 전류 ±1, 1e-10; C0가 `surface_current_factors`와 동일 |
| 동축 a=.5 mm, b=2 mm, 요소 16x64, 32x128, 64x256 | 각 표면 관측 차수 >= 1.8; 가장 고운 상대 오차 < 1e-3 |
| 거절 | 비율 0, .5, 음수, 불리언, NaN, 문자열; 11.25도 다각형; 지지가 열린 벽에 닿는 부분 평행판 |
