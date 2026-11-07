# 명시적 외측 기준면의 Gaussian 전도율 프로파일

`GaussianConductivityProfile`은 Gaussian 전도율 전이를 지정한 비자성 도체의
1D 전체 Maxwell 표면 임피던스를 계산합니다. 임피던스와 함께 포트 위치를 반환합니다.
별도 반공간 구성 법칙 커널이며 `roughness=` 승수로 받거나 선로의 평균면 외부
인덕턴스에 직접 더하는 모델이 아닙니다.

```python
import numpy as np
from sipi import GaussianConductivityProfile

profile = GaussianConductivityProfile(conductivity=58e6, rms_m=1e-6)
result = profile.analyze([1e9, 4e9, 10e9])
assert result.reference_plane_m == -8e-6
assert np.all(result.impedance.real > 0)
assert not result.impedance.flags.writeable
assert not result.frequency.flags.writeable
assert np.all(result.skin_depth > 0)
```

## 물리·수치 계약

입력은 SI 단위입니다. 전도율은 S/m, RMS 높이 `rms_m`는 m, 주파수는 Hz이며
출력 E/H는 Ω/square입니다. `rms_m`는 Rq이며 Ra/Rz 자동 환산, 적층 가정이나
실측 재료 추정을 하지 않습니다. x=0은 통계적 평균면이며 x의 양의 방향은
**금속 안쪽**입니다. `exp(+j omega t)`, 전 영역 mu0·eps0에서 전이 내부는 다음과 같습니다.

```text
sigma(x) = sigma_bulk * Phi(x/Rq)
delta = 1/sqrt(pi*f*mu0*sigma_bulk)
Rs = sqrt(pi*f*mu0/sigma_bulk)
rho = Rq/delta, xi = omega*eps0/sigma_bulk, u = x/Rq
y = Z/Rs
dy/du = rho * ((Phi(u) + j*xi)*y*y - 2j)
y(+cutoff) = (1+j)/sqrt(1+j*xi)
```

`Phi`는 표준 정규 누적분포입니다. 양쪽 cutoff 밖의 전도율은 외측에서 0,
내측에서 sigma_bulk로 정의합니다. 이처럼 잘린 모델의 경계를 명시합니다.
`cutoff_rms` 기본값은 8, 허용범위는 [5,10]이며 출력은 평균면이 아닌
**x=-cutoff_rms*Rq**에서 평가합니다. bulk 경계는 변위전류를 포함한 전체 Maxwell
고유 임피던스입니다. RMS가 0이면 적분 없이 x=0에서 같은 매끈한 금속 임피던스를
반환합니다. 기존 표면 손실 어댑터의 양도체 근사 `(1+j)*Rs`와는 미세하게 다릅니다.

양의 전도율·비음수 RMS, 엄격히 증가하는 양의 주파수 1..1024개,
`rho<=10`, `xi<=1e-3`을 요구합니다. bool·비유한값·표현 불가능한 척도·범위 초과는
적분 전에 거부합니다. 끝값을 포함하는 경계에는 로그 연산의 부동소수점 반올림만
허용하며 실제 값을 경계에 맞춰 자르지 않습니다. 상대 1e-9만큼 범위 밖인 값도
거부합니다. 정규화 임피던스의 DOP853 고정 오차 설정은 상대 2e-11·절대 2e-12입니다.
적분 실패·비유한 출력·비양수 저항은 명시적으로 실패합니다. 입력 배열을 복사하며
출력 주파수·임피던스 배열은 읽기 전용입니다.

## 기준면과 에너지

외측면의 실수 임피던스는 안쪽으로 흐르는 소산 전력을 나타냅니다. 리액턴스는
자기·전기 저장 에너지의 차이이므로 전기적으로 긴 수치 경계 사례에서는 음수일 수
있습니다. 이를 0으로 자르거나 절댓값으로 바꾸지 않습니다. bulk 전도율이 양수라는
조건만으로 외측 포트 임피던스를 인덕턴스만의 보정이라고 간주할 수 없습니다.

cutoff를 바꾸면 포트도 이동합니다. 비교할 때는 정확한 진공 전송선 관계로 같은
외측면에 맞춥니다. `eta=sqrt(mu0/eps0)`, `k=omega*sqrt(mu0*eps0)`에서:

```text
Z_at_farther_exterior = (Z + j*eta*tan(k*d)) / (1 + j*Z/eta*tan(k*d))
```

공기 인덕턴스를 단순히 빼는 방식은 자기준정적 극한에서만 해당합니다. 일반 2D 외부장,
유한 구리·곡률·모서리·면별 전류 재분포와 결합하려면 별도 기준면·기하 계약이 필요합니다.
이 API는 저장 선로 스키마·재료 추정·실제 주파수 대역 보정·시간영역/인과성 인증·
실측 동박 정확도·브라우저/Windows 수락을 제공하지 않습니다.

## 독립 검증과 출처

Gaussian 전도율 가정은
[Gold 외, 2019, 3.3절 식 2](https://ars.copernicus.org/articles/17/51/2019/)
(CC BY 4.0)에 설명됩니다. 여기의 명시적 잘린 외측 포트는 별도 계약이며 논문의
모든 유효 재료 정식화와 같다고 추정하지 않습니다. 논문 그림·측정 데이터·외부 솔버
소스를 패키지에 복사하지 않습니다.

`tests/sipi/test_conductivity_profile.py`는 독립
[scikit-rf 2.2.0 표면 솔버](https://scikit-rf.readthedocs.io/en/latest/api/generated/skrf.tlineFunctions.surface_impedance.html)와
±5Rq 전이·bulk 경계·eps0/mu0·출력면을 일치시킵니다. BSD-3-Clause인 이 도구는
시험 전용이며 정확 v2.2.0의
[라이선스](https://raw.githubusercontent.com/scikit-rf/scikit-rf/v2.2.0/LICENSE.txt)와 설치 소스를
확인했습니다. SciPy 적분은 기존 런타임 의존성이며 새 의존성·번들 바이너리는 없습니다.

수락 기준은 다음과 같습니다.

- RMS 1/100um 각각 rho .001..10의 9점: 복소 도구 차이 <1e-6, 도구 경고 없음.
- rho [.001,.01,.1,1,3,10]와 xi [1e-9,1e-6,1e-3]의 18조합: 도구 차이 <1e-6,
  독립 **선형 E/H** 적분과 별도 소산·자기/전기 에너지 차 적분에 각각 <1e-8로 일치.
  이 무차원 격자의 극단 주파수는 수치 경계 시험이며 그 대역의 실측 금속 거동이 아닙니다.
- 일정 계수 전송층 2048→4096에서 오차가 감소하고 최종 <1e-5.
  정확 진공 이동으로 x=-10Rq에 맞춘 cutoff8→10 차이는 <1e-8,
  cutoff5→10은 <1e-4.
- RMS 0의 고유 임피던스 일치 <1e-12. 전도율·주파수를 k배, RMS를 1/k배 하면
  임피던스 유지 <1e-10. 엄격한 입력·출력 복사·해석 실패·미지원 어댑터 거부 검사로
  이 커널과 선로 추출의 경계를 유지합니다.

[표면 손실 어댑터](conductor.md) · [English](../../../../../packages/sipi/conductivity_profile.md)
