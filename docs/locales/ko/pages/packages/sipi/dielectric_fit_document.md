# 고정 pole 유전체 fitting 요청 저장

[English](../../../../../packages/sipi/dielectric_fit_document.md) · [fitting 알고리즘](dielectric_fit.md) · [공통 실행](execution.md)

`DebyeFitDocument`는 기존 고정 pole Debye fitter의 전체 입력을 저장합니다.
표본 순서·명시적인 가중치·고정 relaxation pole과 최대 복소 유전율 오차 제한을
보존하며 pole을 고르거나 빠진 측정값을 추정하지 않습니다.

```python
import numpy as np
from sipi.dielectric import DebyeDielectric, dielectric_from_dict
from sipi.dielectric_fit import DebyeFitDocument
from sipi.execution import normalize_saved, execute_saved

frequency = np.geomspace(1e6, 1e12, 61)
poles = [1e8, 1e10]
samples = DebyeDielectric(2., [1., 2.], poles).permittivity(frequency)
plan = DebyeFitDocument(frequency, eps_real=samples.real, eps_loss=-samples.imag,
                       relaxation_hz=poles, max_error=1e-8)
assert plan.to_dict()['weights'] == [1.]*len(frequency)
saved = normalize_saved(plan.dumps())
assert saved == plan.dumps()
report = execute_saved(saved, max_evaluations=len(frequency))
assert report['status'] == 'complete' and report['result']['accepted']
material = dielectric_from_dict(report['result']['model'])
np.testing.assert_allclose(material.permittivity(frequency), samples, atol=1e-8, rtol=0)
```

엄격한 `sipi.dielectric-fit/1` 객체는 `schema`, `frequency_hz`, `eps_real`,
`eps_loss`, `relaxation_hz`, `weights`, `max_error`만 포함합니다. Python 생성자에서
가중치를 생략하면 명시적인 1 배열로 확정합니다. 저장 JSON에는 모든 필드와 전체
양수 가중치 배열이 필요하며 `null`은 기본값이 아닙니다. 단위·부호·크기·입력 범위는
[fitting API](dielectric_fit.md)와 같습니다. 알 수 없는 필드·중복 키·수치 자리의
boolean·비유한 숫자는 거부합니다.

요청 생성·불러오기·정규화는 입력 검증과 복사만 합니다. SVD·optimizer·필드 계산을
실행하지 않습니다. 수치 식별 가능성과 조건수 검사는 `analyze()`에서 수행한 뒤
기존 제한 fitting과 KKT 검사를 사용합니다. 정규 JSON과 사전 접근자는 분리된 값을
반환합니다.

공통 실행은 행렬이나 optimizer 계산 전에 **입력한 주파수 표본 수**를 호출자의
`max_evaluations`와 비교합니다. 61개 표본에는 최소 61의 예산이 필요하며 자동으로
줄이지 않습니다. 이것이 optimizer 61회라는 뜻은 아니며 API의 별도 반복 한도는
10*(pole 수+1)입니다. 프로세스 메모리·시간 상한을 뜻하지도 않습니다. 기존 입력
byte 제한도 적용되므로 큰 유효 요청에는 호출자가 명시적으로 더 많은 byte를
허용해야 할 수 있습니다. 선로 전용 characteristic/modes 진단은 이 요청에 허용하지 않습니다.

`execute_saved`는 정규 `input`과 직접 API와 동일한 전체 `DebyeFit.to_dict()` 결과를
반환합니다. 수치 계산이 끝나면 `status='complete'`이며 요청 오차를 만족하는지는
별도의 `result.accepted`입니다. 아래의 의도적으로 맞지 않는 합성 표본도 계산은
완료하되 수락하지 않은 후보로 보존합니다.

```python
changed = plan.to_dict()
changed['eps_real'][0] += .2
unaccepted = execute_saved(DebyeFitDocument.from_dict(changed).dumps())
assert unaccepted['status'] == 'complete'
assert not unaccepted['result']['accepted']
assert len(unaccepted['result']['residual']['real']) == len(frequency)
```

잘못된 입력·rank/조건수 거부·optimizer 실패는 기존 선로 실행처럼 원래 예외를
전달합니다. 가짜 모델이나 부분 fit을 완료 결과로 반환하지 않습니다. 결과 모델은
기존 유전체 schema이므로 선로·공차·역산의 재료 입력에 넣을 수 있습니다. 호출자는
수락 여부와 사용할 유효범위를 먼저 확인해야 합니다.

검증은 직접/저장 모델·잔차·판정의 정확한 재생, 기본값 확정·입력 분리, 수치 연산
없는 정규화, 표본 예산 경계, 원래 실패 예외와 엄격한 JSON 거부를 포함합니다.
fit한 합성 재료로 기존 저장 선로 C/G/L/S도 1e−8 이내로 재현합니다. 독립 알고리즘과
active-set 검사는 fitting API suite에 유지합니다. 표본의 수학적 계약이며 실측
재료·연속 대역·앱 pin·새 플랫폼 수락을 뜻하지 않습니다.

```sh
python -m pytest -q tests/sipi/test_dielectric_fit_document.py tests/sipi/test_dielectric_fit.py tests/sipi/test_execution.py tests/sipi/test_dielectric.py
```
