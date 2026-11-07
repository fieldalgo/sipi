# 물리 상수와 런타임 재현성

SIPI는 전기·자기·표면전류·유한 금속 추출에 **CODATA 2022의 공개 표기값**을
일관되게 사용합니다. `sipi.constants`에 정의하며 SciPy의 상수표에 의존하지 않습니다.

| 기호 / Python 이름 | 값 | 단위 | 표준 불확도 |
|---|---|---|---|
| ε₀ / `epsilon_0` | 8.8541878188e−12 | F/m | 1.4e−21 F/m |
| μ₀ / `mu_0` | 1.25663706127e−6 | H/m | 2.0e−16 H/m |
| c / `SPEED_OF_LIGHT` | 299792458 | m/s | 정확 |

출처: [NIST, 2022 CODATA 전체 표](https://physics.nist.gov/cuu/Constants/Table/allascii.txt),
2026-11-07 확인. `CODATA_REVISION`은 2022입니다. 공개 기준 숫자를 직접 기록했으며
다른 라이브러리 소스 코드를 복사하지 않았습니다.

```python
from sipi.constants import CODATA_REVISION, epsilon_0, mu_0, SPEED_OF_LIGHT

print(CODATA_REVISION, epsilon_0, mu_0, SPEED_OF_LIGHT)
assert abs(epsilon_0*mu_0*SPEED_OF_LIGHT**2-1) < 2e-12
```

c만 정확한 상수입니다. 두 측정 상수의 표기값을 각각 보존하면 표 반올림 때문에
`epsilon_0*mu_0*c**2 - 1 ≈ 1.19e-12`입니다. 곱을 정확히 1로 만들려고 어느 값을
조정하지 않습니다. 이 반올림은 공개 측정 불확도보다 작으며 솔버 오차 추정이 아닙니다.

이전 SIPI는 SciPy의 상수표를 사용했습니다. CODATA 2018 런타임에서는
ε₀=8.8541878128e−12 F/m, μ₀=1.25663706212e−6 H/m이므로 같은 메시·수치 알고리즘도
2022 기준과 정전용량이 약 6.78e−10 상대 차이를 냅니다. 명시 버전으로 의존성에
따른 암묵적 변화를 막습니다. 검증한 SciPy 1.18.1 환경의 값은 그대로이며 오래된
런타임의 상수 선택은 의도적으로 변경됩니다. 기하·재료 저장 스키마는 불변입니다.
과거 결과 재생에는 원래 엔진과 정확한 의존성 산출물이 필요합니다.

상수 고정이 OS별 동일 메시·라이브러리 반올림·부동소수점 결과를 보장하지는
않습니다. 엔진/wheel 해시·런타임 버전·메시 설정을 기록하고, 메시 생성과 솔버
차이를 분리할 때는 같은 메시를 대조합니다. 엄격한 대수 비교의 독립 기준 도구도
같은 물리 상수를 써야 합니다. 기존 필드 수렴과 모델 유효범위는 계속 적용됩니다.

시험은 별도 인터프리터에서 엔진 import 전에 SciPy의 상수에 과거값/다른값을
넣고, 선형 평행판 P1 해와 해석적 good-conductor 표면 법칙을 확인합니다. 제품이
공유 galerkin/meshine 구현이나 독립 기준 도구의 상수를 수정하지는 않습니다.

[English](../../../../../packages/sipi/constants.md)
