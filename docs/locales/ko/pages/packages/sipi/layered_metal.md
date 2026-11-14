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
