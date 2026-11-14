# 평면 다층 금속 표면 임피던스

`layered_surface_impedance`는 반무한 바탕 금속 위에 완전 접촉한 평면 금속층의
완성 외부 표면에서 E/H를 계산합니다. 이 국소 자기 준정적(MQS) 확산 모델은
각 도금층이 표피 깊이보다 두꺼워야 한다는 조건 없이 얇은 층을 해석합니다.

```python
from sipi import MetalLayer, layered_surface_impedance

result = layered_surface_impedance([1e6, 1e8, 1e10], conductivity=58e6,
    layers=[MetalLayer(.2e-6, 14e6, 3.), MetalLayer(1e-6, 40e6)])
assert result.impedance.shape == (3,)
assert result.skin_depth.shape == (3, 3)
print(result.impedance)  # ohm/square at the outer metal surface
```

층 순서는 **바깥에서 안쪽**입니다. 함수의 conductivity·relative_permeability는
반무한 바탕 금속을 지정합니다. 각 `MetalLayer`에는 두께[m], 전도도[S/m], 양의
실수 상대 투자율을 명시합니다. 두께 0은 제거된 층이며 층이 없으면 기존 균일 금속
표면 임피던스와 정확히 같습니다. 균일 층을 여러 조각으로 나누어도 같은 모델입니다.

1..1024개 증가 양주파수와 0..32개 유한 층을 지원합니다. 모든 재료는 기존
좋은 도체 조건 `sigma/(omega*eps0) >= 1000`을 만족해야 합니다. 전도도와 투자율은
양수·등방·선형·주파수 불변입니다. 결과는 복사된 읽기 전용 배열이며 표피 깊이
열은 지정 층들 다음 바탕 금속 순서입니다.

바탕에서 외부 표면으로 `eta*(Zback+eta*tanh(k*d))/(eta+Zback*tanh(k*d))`를
재귀 계산합니다. `k=(1+j)/delta`, `eta=(1+j)*sqrt(pi*f*mu/sigma)`입니다.
임피던스를 스케일링하여 전달 행렬의 overflow를 피합니다. `d/delta >= 350`에서는
tanh가 부동소수 정밀도로 1이며 뒤쪽 영향은 지수적으로 작습니다. 잘못된 입력이나
표현할 수 없는 결과는 유효 모델로 반환하지 않고 예외로 전달합니다.

기준면은 **금속의 외부 표면**이며 외부 공기 인덕턴스를 더하지 않습니다. 이 API는
평면 반무한 근사를 유한 두께·모서리·곡률이 있는 2D trace에 자동 적용하지 않습니다.
도금 기하 생성, 거칠기 결합, 접촉 저항, 복소 자기 손실·히스테리시스, 실측 피팅도
포함하지 않습니다. 유한 금속 형상은 명시 코어 기하와 체적 확산 솔버로 해석합니다.

독립 2×2 확산 행렬 지수와 깊이 정규화 ODE, sigma*|E|² 적분 및 바탕 tail 전력으로
비교합니다. 바탕 깊이를 표피 깊이의 8/12/16배로 바꾸어 반무한 극한을 확인합니다.
층 순서·균일 층 분할·0층·두꺼운 층·확산 스케일 불변식도 검사합니다. 이 국소 모델은
2D 메시·외곽 경계를 사용하지 않으며 이후 단면 연결에는 별도 검증이 필요합니다.

## 명시적 단면 표면 재료

`LayeredSurfaceMetal`은 기존 경계별·면별 표면 전류 계산에 이 국소 법칙을 연결합니다.
상속된 전도도·투자율은 바탕 금속이며 `coatings`는 바깥부터 안쪽 순서의 `MetalLayer`
튜플입니다. 완성 외곽 기하는 그대로이며 도금층은 안쪽을 차지합니다. 검증하지 않은
배율을 곱하지 않도록 거칠기 동시 지정은 거부합니다.

```python
from sipi import microstrip, MetalLayer
from sipi.boundary_conductor import (
    SurfaceMetal, LayeredSurfaceMetal, surface_conductor_loss_by_boundary)

section = microstrip(width=.5e-3, substrate_height=1e-3,
                     thickness=50e-6, eps_r=4., box_width=6e-3, air_height=3e-3)
coated = LayeredSurfaceMetal(58e6, coatings=(MetalLayer(.2e-6, 14e6, 3.),))
loss = surface_conductor_loss_by_boundary(section, [1e9, 4e9],
    conductors={section.traces[0].name: coated}, reference=SurfaceMetal(58e6),
    ground_thickness=35e-6, edge_size=5e-6, far_size=.2e-3, grade=.1)
assert loss.R.shape == (2, 1, 1)
```

메시 생성 전에 코어 유효 최소 치수를 보수적으로
`minimum_dimension - 2*sum(coating thickness)`로 계산합니다. 이 값은 양수여야 하며
바탕과 두께가 0이 아닌 층의 최대 표피 깊이가 그 1/5 이하여야 합니다. 도금 없는
재료는 원래 기준을 유지합니다. 두께 0인 층은 치수나 최대 침투 깊이를 늘리지 않습니다.
보고하는 `skin_depth`는 재료별 표피 깊이의 최댓값이고 `roughness_factor`는 1입니다.
전체 도금 응답은 `surface_impedance`에 들어갑니다. 신호·귀환 면별로 따로 검사하며
실제 offset 코어 메시를 만드는 것은 아닙니다.

이 조건은 국소 1차 근사의 사용 범위이며 모서리나 임의 곡률의 오차 보증은 아닙니다.
새 반경 방향 기준은 바탕 원통 Bessel 해와 원통 확산 ODE를 연결하며 반경이 커지면
평면 법칙에 접근합니다. 이는 최초 구성 모델 검증에 사용한 **평면 깊이 ODE**와
별개입니다. 평행판 전력, microstrip 메시·외곽 수렴, 선로망 수동성과 도금 없는 경우의
호환성도 따로 검사합니다. 기존 transmission-line 저장 형식 1..6의 재료 계약은
그대로이며 새 버전 7에 명시 도금층을 추가합니다.

## 선로 저장 버전 7

경계·면별 재료는 정확히 네 필드 `kind='layered'`, `conductivity`,
`relative_permeability`, `coatings`로 명시합니다. 각 층에는 정확히
`thickness_m`, `conductivity`, `relative_permeability`가 필요합니다. 층 순서와
명시 빈 배열을 보존하며 이 재료에 거칠기 필드를 함께 넣을 수 없습니다. 일반 표면
재료의 기존 세 필드 형식은 유지하며 도금 재료와 섞어 사용할 수 있습니다.

```python
from sipi import CrossSectionDocument, microstrip
from sipi.line_model import TransmissionLineDocument
from sipi.execution import normalize_saved

section = microstrip(width=.5e-3, substrate_height=1e-3, thickness=50e-6, eps_r=4.)
material = dict(kind='layered', conductivity=58e6, relative_permeability=1.,
    coatings=[dict(thickness_m=.2e-6, conductivity=14e6, relative_permeability=3.)])
request = TransmissionLineDocument(CrossSectionDocument(section), [1e9, 4e9],
    materials={}, length=.03, schema='sipi.transmission-line/7',
    conductor=dict(kind='surface-boundaries',
        conductors={section.traces[0].name: material}, reference=material,
        ground_thickness=35e-6))
assert normalize_saved(request.dumps()) == request.dumps()
```

버전 7에서 이름별 신호, 신호의 각 면, 공통 귀환, 명시 접지 평면·측벽·전체 접지
trace·접지 trace의 각 면에 새 재료를 지정할 수 있습니다. 한 메시·전류 추출과
유전체 계산, 공통 실행·진단·회로·길이 해석을 재사용합니다. 읽을 때는 메시 없이
재료·코어 조건을 검사합니다. 이전 버전은 이 재료를 거부하며 생성자의 기본 버전은
계속 1입니다. 기존 목표·공차·수율 저장 문서의 line/6 계약은 자동 확장하지 않습니다.

[고정 도금층의 기하·유전체 공차](layered_study.md)는 명시 study/4와 yield/3으로 연결합니다.

[고정 도금층의 저장 단일 변수 목표](layered_goal.md)는 명시 goal/4를 사용합니다.
