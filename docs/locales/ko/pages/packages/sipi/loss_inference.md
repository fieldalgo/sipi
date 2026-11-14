# 유효 shunt 손실 역산

`infer_shunt_loss`는 알려진 단일 선로 R [ohm/m], L [H/m], C [F/m]와
**진행파 진폭 감쇠** alpha [Np/m]에서 음이 아닌 shunt 전도도 G [S/m]를 구합니다.
각 주파수에서 `alpha = Re sqrt((R+j*omega*L)*(G+j*omega*C))`를 풉니다.
삽입 손실에서 근사 구리 손실을 빼는 계산이 아닙니다.

```python
import numpy as np
from sipi import infer_shunt_loss

frequency = np.array([1e8, 1e9])
# Explicit propagation attenuation supplied by the caller.
result = infer_shunt_loss(frequency, alpha=[0.2, 2.0], R=2.,
                         L=400e-9, C=150e-12, max_error_np_per_m=1e-9)
assert result.accepted
assert np.all(result.conductance >= 0)
print(result.effective_loss_tangent)
record = result.to_dict()
```

주파수는 1..10000개의 엄격히 증가하는 양수이며 alpha는 같은 길이의 음이 아닌
배열입니다. R은 0 이상, L/C는 양수입니다. 각 계수는 스칼라 또는 주파수별 배열입니다.
양의 허용오차를 Np/m 단위로 명시해야 합니다. 입력은 복사하며 결과 배열은 읽기
전용입니다. 원래 RLC/alpha, G, G=0 기준 감쇠, 예측 alpha/beta, 부호 있는 잔차,
정확한 도체·유전체 전력 손실 분해와 근 평가 횟수를 보존합니다.

alpha가 G=0 기준보다 작으면 비음수 제약의 최적 후보 G=0과 원래 입력·양의 잔차를
보존합니다. `accepted`는 모든 입력 표본의 절대 잔차가 명시 허용오차 이하라는 뜻입니다.
큰 허용오차로 기준 이하의 불일치를 수락해도 물리적 원인이 검증되는 것은 아닙니다.
탐색 구간은 omega*C에서 시작해 최대 64번 4배 확대합니다. 정규화 Brent 풀이의
반복 한도는 128이며 재시도하지 않습니다. 수치 표현 불가·구간 탐색·근 풀이 실패는
성공 결과로 바꾸지 않고 예외로 전달합니다.

`G/(omega*C)`는 **유효 shunt 손실 탄젠트**입니다. 실제 재료 tan(delta)로 해석하려면
호출자의 균일 유전체 모델이 그 관계를 정당화해야 합니다. 다중 재료 손실 분리,
fixture 보정, 임의 S21의 전파 감쇠 자동 변환, 측정 불확실성 추정이나 연속 대역
정확도를 제공하지 않습니다. 전계·메시를 새로 풀지 않으므로 입력 RLC의 메시·외곽
수렴 및 물리적 검증은 별도로 필요합니다.

독립 R=0 해석해, 2×2 전송 방정식 행렬 지수의 고유값 크기에서 얻은 감쇠,
저손실·고손실 RLGC 재생, 정확 전력 보존 및 기준 이하 자료 보존으로 검증합니다.
이는 역산 계약의 검증이며 실측 적층 재료 정확도의 근거는 아닙니다.
