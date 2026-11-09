# 명시적 경계 패널 도체 손실

이 명시적 경로는 공유 `galerkin.laplace_boundary` 커널로 진공 완전도체
전류를 계산합니다. 기존 유한요소 표면 전류 API나 저장된 선로 문서의
계산 방법을 변경하지 않습니다.

`dependencies.json`의 정확한 커밋에서 만든 휠을 사용해야 합니다. 개발용
휠은 버전이 같아도 API가 다를 수 있습니다. 이 기능이 없는 휠에서도 SIPI
모듈을 불러올 수 있지만, 패널 API를 호출하려면 명시적
`interpolation_degree`를 지원하는 공유 휠이 필요합니다. 없으면 오류를
내며 다른 솔버로 자동 전환하지 않습니다.

## 기하와 전류 계약

`panel_surface_current_factors(section, panels_per_edge=32, ground_modes=512,
interpolation_degree=10)`는 미터 단위 `CrossSection`을 받습니다. 아래는
접지, 위와 옆은 open이어야 하며 도체는 양의 두께를 갖는 엄밀한 볼록
다각형이어야 합니다. 공유 유한 직사각형 Green 함수는 아래에서 전위 0,
나머지 외곽에서 법선 미분 0을 적용합니다. 따라서 여기서 open이라는
설정도 외곽 영역 크기의 수렴 검증이 필요합니다.

명시적 접지 도체는 전위 0을 유지합니다. 부유 도체가 아닙니다. 그 표면
전류 에너지는 아래 접지와 합쳐 공통 기준 도체 항으로 만듭니다. 전체
도체 정전용량 행렬을 A, 신호 인덱스를 S라 하면 B=A[S,S],
T=A[:,S] inverse(B)입니다. 전류 항은 Tᵀ Q_b T이며 이 변환 뒤에 접지
항들을 더합니다. C0=epsilon_0 B입니다. 신호 경계의 전류 적분은 단위
행렬, 합친 기준 경계의 적분은 각 신호 기저마다 -1입니다. 접지 전위와
전류 잔차는 1e-10 이하여야 합니다.

결과는 `SurfaceCurrentFactors`를 확장하므로 `C0`, `parts`,
`current_integrals`, `L_external`, `current_error`를 그대로 제공합니다.
추가로 명시적 접지 도체 이름과 공유 계산 진단값을 기록합니다. 배열과
진단값은 읽기 전용입니다. 층의 유전율이나 국소 유전체 영역은 이 진공
전류 계산에 들어가지 않습니다. 같은 기하의 C/G를 별도로 계산할 때는
그 재료 정보가 필요합니다.

공유 커널은 도체 16개, 전체 패널 2048개로 제한합니다. 폭/높이 비는
[0.25, 4]이며 도체 집합에서 옆과 위 외곽까지의 거리는 그 집합의 가장
큰 길이 이상이어야 합니다. 다각형의 접촉·겹침·내포·외곽 접촉은 지원하지
않습니다. `panels_per_edge`는 [1, 256] 정수이고 `interpolation_degree`는
10, 12, 14, 16입니다. 구적·보간 또는 접지 급수 세분 검사를 통과하지
못하면 오류를 내며 매개변수를 자동으로 바꾸지 않습니다. 보간 차수를
명시적으로 높여도 패널 및 외곽 수렴 검증은 별도로 필요합니다. 1개와
2개 패널에서 세제곱 끝점 배치는 균일하므로, 이 첫 변화만으로 점근
수렴을 주장할 수 없습니다.

## 금속 손실과 회로

`panel_conductor_loss_by_boundary`는 각 신호의 `SurfaceMetal`, 공통 기준
금속 하나, 명시적 `ground_thickness`를 받습니다. 장 계산 전에 기존
양의 주파수·양도체·표피 깊이 조건을 검사합니다. 각 표피 깊이는 해당
도체 최소 치수의 1/5 이하여야 합니다. 기준 도체는 접지 두께와 모든
명시적 접지 도체를 검사합니다. 기존 다각형 최소 치수에는 가장 짧은
변이 포함됩니다. 따라서 전체 직경이 커도 매우 잘게 다각형으로 근사한
도체는 거부될 수 있습니다. 이 경로에서 제한을 완화하지 않습니다.

R=sum_b Re(Zs_b) Q_b, 내부 L=sum_b Im(Zs_b) Q_b / omega입니다. 기존
매끈한 표면, Hammerstad, Groiss, 인과적 Huray, cannonball Huray 법칙과
각 유효범위를 그대로 사용하며 새 재료·거칠기 모델을 추가하지 않습니다.
모든 기준 표면은 같은 금속이어야 합니다. 서로 다른 접지 도체 금속이나
동박 면별 개별 재료 지정은 지원하지 않습니다.

반환된 `BoundaryConductorLoss.network(C=..., G=..., length=...)`는 같은
패널 전류 계산의 외부 L=mu_0 epsilon_0 inverse(C0)를 손실과 조합합니다.
C와 G는 기하·도체 순서·외곽 조건이 일치해야 합니다. 관계없는 유한요소
L을 대신 사용하면 안 됩니다. 이 모델은 표면 임피던스의 일차 섭동이며
도체 내부 확산, DC, 복사 또는 비아 모델이 아닙니다.

## 검증 범위

후보는 접지 도체 전위, 전류 보존, 양의 에너지, 크기 배율과 도체 순열을
검사합니다. 수락한 2/4/8 패널 열을 별도 직접 전압 collocation 풀이와
대조했습니다. 별도 scikit-fem P2 대조는 이산화 사이의 차이로 기록하며,
전류 에너지 차이가 단조 감소하지 않아 정확도 근거로 사용하지 않습니다.
원래 1/2/4 열의 단조성 실패도 실패 연구로 보존합니다.

금속 조립은 독립 매끈한 반공간 법칙, 주파수 배율, 수동적이고 상호적인
회로로 검사합니다. 고정된 두 선로 기하를 세 패널 분해와 세 외곽 크기에서
원래 유전체 행렬·목표·수렴 기준으로 재실행합니다. 이 사례의 통과가 임의
배치·재료 데이터나 전체 역설계 탐색의 정확도를 보장하지는 않습니다.

## 최소 사용 예

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.panel_conductor import panel_conductor_loss_by_boundary

section = CrossSection(
    [Layer("uniform", .002, 4.2)],
    [Trace("left", -.0003, .0005, .0002, thickness=35e-6),
     Trace("right", .0003, .0005, .0002, thickness=35e-6)],
    .004,
)
copper = SurfaceMetal(58e6)
loss = panel_conductor_loss_by_boundary(
    section, [1e9, 2e9], conductors={"left": copper, "right": copper},
    reference=copper, ground_thickness=35e-6, panels_per_edge=16,
)
assert loss.R.shape == (2, 2, 2)
assert loss.factors.current_error <= 1e-10
```
