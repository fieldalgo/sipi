# 진행파 전파상수와 손실 기여

`rlgc_propagation(frequency, R=..., L=..., G=..., C=...)`는 `rlgc_network`와 같은
실수·상호·수동 RLGC 행렬을 받으며 주파수는 양의 Hz만 지원합니다. 단일 도체나
교환대칭 쌍만 지원합니다. 쌍의 모든 행렬은 매 주파수에서 두 대각 원소가 행렬
크기 대비 `1e-12` 이내로 같아야 합니다. 비대칭 모드는 거부하며, 메시의 근사
대칭을 임의 평균하지 않습니다. 일반 고유모드 추적 기능은 아닙니다.

```python
from sipi import rlgc_propagation

p = rlgc_propagation([1e6, 1e9], R=[[2]], L=[[400e-9]], G=[[.002]], C=[[100e-12]])
print(p.z_characteristic, p.gamma)
print(p.conductor_db_per_m, p.dielectric_db_per_m, p.attenuation_db_per_m)
```

결과는 수정할 수 없는 `(frequency, mode)` 배열입니다. 모드는 `single` 또는
`differential, common`입니다. 쌍은 Vd=V1−V2, Id=(I1−I2)/2,
Vc=(V1+V2)/2, Ic=I1+I2로 정규화합니다. 차동 R/L은 odd 고유값의 두 배,
G/C는 절반이며 공통 R/L은 even 고유값의 절반, G/C는 두 배입니다. 도체당
odd/even 임피던스가 아닌 물리적 차동/공통 임피던스를 보고합니다.
`TransmissionLineResult.propagation()` 및 `VolumeLineResult.propagation()`은
양의 주파수의 기존 추출 행렬을 재사용하며 장 해석을 추가로 하지 않습니다.
원래 추출 모델의 유효범위는 그대로 적용됩니다.

exp(+jωt), z=R+jωL, y=G+jωC에서 수동 해는 gamma=sqrt(z y),
Zc=sqrt(z/y), alpha=Re(gamma), beta=Im(gamma)입니다. 진행파 소산 전력의 정확한
분해는 다음과 같습니다.

```
alpha_conductor = R / (2 Re(Zc))
alpha_dielectric = G |Zc|² / (2 Re(Zc))
alpha_conductor + alpha_dielectric = alpha
```

단위는 Np/m이며 `*_db_per_m`은 진폭 감쇠에 20/ln(10)을 곱합니다.
`phase_velocity`는 ω/beta(m/s)이며 군속도나 정보 전달 속도가 아닙니다.
저손실 근사가 아닌 모드 전력의 정확한 분해입니다. 두 기여는 **같은 전체
손실 모드**를 사용합니다. R 또는 G를 따로 0으로 바꾸면 모드 자체가 달라집니다.
유한 길이의 `-20 log10|S21|`은 포트 부정합과 반사도 포함하므로 일반적으로
선로 자체 감쇠에 길이를 곱한 값과 다릅니다.

DC는 영곱 진행파의 불명확한 극한을 포함해 지원하지 않습니다. DC 회로는
기존 network/volume API로 계산합니다. 잘못된 행렬·미지원 모드·비유한 중간값은
거부합니다. 새 재료 fitting·거칠기 식·quasi-TEM 유효성 보장은 제공하지 않습니다.

무손실 임피던스/위상, 무왜곡 조건 R/L=G/C, 한 손실의 영값 및 고손실 전력
평형을 상대 `1e-10` 이하 기준으로 확인합니다. scikit-rf 2.2.0 DistributedCircuit의
gamma/Zc와 단일·차동/공통 모드를 최대 상대 오차 `1e-10`으로 대조하며,
`OPENPHYSICS_CROSSCHECK_DIR`로 독립 기록을 남깁니다. 표면/체적 추출 시험은
기존 RLGC 재사용과 DC 거부를 확인하며 새로운 장 해석 절대 정확도 근거는 아닙니다.

[네트워크](network.md)
