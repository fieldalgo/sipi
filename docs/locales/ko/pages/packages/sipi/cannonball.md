# 명시적 10점 Rz 표면 모델

`CannonballHuray`는 양수 **10점 평균 거칠기 Rz(m)**를 기존
[인과 Huray 법칙](roughness.md)에 연결합니다. 해당 통계 정의와 근사가 맞는 경우 선택합니다.
여기서 10점 Rz는 명시된 샘플 길이의 평균선 기준 최고 봉우리 5개의 평균에
가장 깊은 골 5개의 깊이 평균을 더한 값입니다.

```python
from sipi.roughness import CannonballHuray
from sipi.conductor import surface_impedance

model = CannonballHuray(rz_10point_m=3e-6)
print(model.radius_m, model.surface_ratio)
print(model.to_huray())
print(surface_impedance([1e9, 4e9, 10e9], conductivity=58e6, roughness=model))
```

불변 모델은 출판된 반올림 근사 `radius_m = 0.06*rz_10point_m`, 전체 구 면적비
`14*pi/9`를 사용합니다. 면적비를 4.9로 반올림하지 않습니다. 구 14개가
`36*r**2` 바닥을 차지하며 바닥 면적비는 1입니다. 삼각 높이 분포와 9/4/1 FCC
적층은 휴리스틱이며 실측 표면 기하가 아닙니다. Lambert (Bert) Simonovich,
*PCB Interconnect Modeling Demystified*, DesignCon 2019, pp. 12–13, 식 11–14의
[논문](https://swb.skku.edu/emc/infromation.do?articleNo=21942&attachNo=19820&mode=download)과
[저자 설명](https://blog.lamsimenterprises.com/2019/03/29/cannonball-huray-model-demystified/)을
참고했습니다. 원문 도판·코드·측정 데이터는 배포하지 않습니다.

`factor(skin_depth)`는 비어 있지 않은 양수 유한 1D 깊이를 받아 **복소 배수**를
반환하며 저항비가 아닙니다. 도체 어댑터는 안정적인 R/X 계수를 `CausalHuray`에
위임합니다. 고/저주파 배수 극한은 `1+7*pi/3`과 1입니다. 이 수학적 극한으로
DC 표면 추출을 허용하지 않습니다. `to_huray()`로 동일 불변 모집단을 확인합니다.

0·음수·비유한·bool·표현 불가능 반경을 거부합니다. 거칠기 0은
`roughness=None` 또는 저장 `kind="smooth"`를 사용합니다. Ra·Rq·다른 Rz
정의를 변환하지 않고 양면 평균·표면 처리·유전율 보정을 자동 적용하지 않습니다.
모든 표면에 한 모델을 사용합니다. 양도체·표피 깊이·두께·전류 수렴 조건은
유지되며 거칠기도 도체 치수·곡률·간격보다 물리적으로 작아야 합니다.
매끈한 유한 금속 확산은 바뀌지 않습니다. 인과 재료 법칙 하나로 전체 선로의
인과성이나 실측 동박과의 일치를 인증하지 않습니다.

## 저장 입력과 검증

`sipi.transmission-line/2`의 표면 도체에서 다음을 선택합니다.

```json
{"kind": "cannonball-huray", "rz_10point_m": 0.000003}
```

전도도·상대 투자율·접지 두께도 필요합니다. Rz는 명시적으로 저장합니다.
미지/누락 필드·중복 키·버전 1 혼합은 메시 전에 거부합니다. 공유 메시
RLGC/네트워크 계산에서 같은 모델을 사용합니다. smooth·Hammerstad·Groiss·명시
Huray의 정의/직렬화는 유지하며 양수 `roughness_rms`와 동시에 사용할 수 없습니다.

독립 구 중심 좌표와 삼각 높이 적분의 반경/Rz는 0.05978657793452507입니다.
출판된 0.06과 차이는 0.357%로 선등록 반올림 한계 0.5% 이내이며 **물리 정확도가
아닙니다**. 양의 relaxation 적분과 복소 법칙을 `1e-10`으로, 스케일·실수 손실
항등식을 `1e-12`로 확인합니다. radial 64/128/256·angular 256의 동축 해석
추출은 R/내부 L 오차 감소·최종 1% 미만을 요구합니다. microstrip 쌍의
edge/far/grade를 절반으로 줄여 변화 5% 미만·전류 오차 5% 미만을 요구합니다.
저장 재생/동일 구 모집단은 RLGC `1e-12`, S `1e-10`이 기준입니다.
극단/거부 입력·수동성·상반성도 별도 확인합니다. 원문의 실측 쿠폰 재현은
아닙니다. 독립 시험 적분은 SciPy를 쓰고 런타임 의존성은 추가하지 않습니다.

[English](../../../../../packages/sipi/cannonball.md)
