# 주파수영역 Groiss RMS 보정

`sipi.roughness.GroissRMS(rms_m)`는 좋은 도체 반공간의 표면 임피던스에 적용하는
경험적 **비인과** 보정입니다. 입력은 **RMS 높이 Rq(m)**이며 Ra·Rz가 아닙니다.
다른 거칠기 척도에서 자동 변환하지 않습니다.

```python
from sipi.roughness import GroissRMS
from sipi.conductor import surface_impedance
zs = surface_impedance([1e9, 4e9, 10e9], conductivity=58e6,
                       roughness=GroissRMS(.5e-6))
```

표피 깊이 δ, 양의 Rq에서 `K=1+exp(-(δ/(2Rq))**1.6)`, `Zrough=K Zsmooth`입니다.
저항·리액턴스 모두 같은 실수 계수를 곱합니다. Rq=0이면 정확히 평활 도체 값이고
K는 1–2입니다. 극단적인 유한 입력에서는 로그 연산으로 중간 overflow를 피합니다.
`factor(skin_depth)`는 비어 있지 않은 양의 1차원 배열을 받아 순서를 보존합니다.
음수·비유한·bool·비scalar RMS는 거부합니다.

기존 `roughness_rms` Hammerstad는 저항만, `CausalHuray`는 서로 다른 인과적
저항·리액턴스 보정을 적용합니다. 각각의 의미는 유지하며 모델 객체와 비영
`roughness_rms`를 함께 지정할 수 없습니다. `ConductorLoss.roughness_factor`는
계속 저항비입니다. `surface_conductor_loss`도 같은 객체를 받고 좋은 도체·두께·
표피 깊이·메시·전류 flux 검사를 유지합니다.

상대적으로 잘 연마한 표면을 대상으로 하며 평활 임피던스의 두 배에서 포화합니다.
거친 PCB 동박의 정확성·실측 피팅·표면 미세 형상·시간영역 응답을 검증하지 않습니다.
**주파수영역 전용**이며 이 모델을 입력했다고 전체 선로가 인과적이 되는 것은
아닙니다. 평활 금속 체적 확산에는 이 계수를 적용하지 않습니다.

`TransmissionLineDocument`는 `sipi.transmission-line/2`와 surface conductor의
`roughness={"kind":"groiss", "rms_m":0.5e-6}`를 명시합니다. 이 객체에는
kind·rms_m만 허용합니다. 기존 v1 및 다른 v2 모델의 의미는 유지하며 이전 판독기는
새 kind를 거부하므로 SIPI 버전을 함께 저장하세요. 기존 공유 메시 경로를 통해
기하·재료·주파수·RLGC·S·전파 계산을 연결하고 JSON 복원에도 선택을 보존합니다.

`tests/sipi/test_groiss.py`의 검증 기준은 다음과 같습니다.

- δ/(2Rq)=0.01…10에서 독립 SciPy Weibull 생존함수 및 확률밀도 적분과 상대·절대
  <=1e-12. 지정 경험식의 수학적 검사이며 실제 거친 표면의 정확도 검사가 아닙니다.
- 정확한 평활·포화 극한, 단조성, 극단 유한 스케일, σ·μ·Rq 차원 상사,
  잘못된 입력 및 혼합 보정 거부.
- 해석적 동축 표면전류 기하와 비교: 반경 세분 64→128→256에서 R·내부L 오차가
  감소하고 최종 <1%. 각도 분할은 256입니다. 단일 microstrip의 edge/far/grade를
  절반으로 줄일 때 R·내부L 변화 <5%, 적분 전류 오차 <5%.
- 엄격 JSON·메시 한 번 생성·기존 입력 회귀·별도 표면 추출과 <=1e-10 일치,
  재현·상호성·수동성·전파 연결.

새 의존성·바이너리는 추가하지 않습니다. 기록한 Linux 시험의 수치 기준 도구는
SciPy 1.18.1(BSD-3-Clause)입니다. 수식·기하 검증을 새 OS나 실측 정확도 주장으로
확대하지 않습니다.

수식과 RMS 정의: Chen/Tian, *Micromachines* 14(2023),104, 식8–9,
DOI [10.3390/mi14010104](https://doi.org/10.3390/mi14010104).
원 모델: Groiss et al., *IEEE Transactions on Magnetics* 32(1996),894–897,
DOI [10.1109/20.497385](https://doi.org/10.1109/20.497385).
인용은 모델을 식별하며 논문의 실험 결과를 재현했다는 뜻이 아닙니다.

[다른 거칠기 모델](roughness.md) · [선로 입력](line_model.md)
