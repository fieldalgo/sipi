# 텐서 피팅 요청 저장

[English](../../../../../packages/sipi/tensor_dielectric_fit_document.md) · [직접 피팅](tensor_dielectric_fit.md) · [공통 실행](execution.md)

`TensorDebyeFitDocument`는 극점·방향을 고정한 텐서 피팅 입력을
`sipi.tensor-dielectric-fit/1`로 저장합니다. 직접 피팅의 수치 구현과 표본·극점·방향·
상반성·수동성·오차 제한을 그대로 사용합니다. 읽을 때는 표본별 작은 2×2 고유값
검사까지 입력 검증을 수행하지만 SVD·최적화·전계 메시 계산은 하지 않습니다.
식별 가능성과 수치 최적성은 실제 분석 단계에서 검사합니다.

```python
import numpy as np
from sipi.dielectric import TensorDebyeDielectric
from sipi.tensor_dielectric_fit_document import TensorDebyeFitDocument
from sipi.execution import normalize_saved, execute_saved
from sipi.execution_request import SavedExecutionRequest

frequency = np.geomspace(1e6, 1e12, 17)
model = TensorDebyeDielectric([2, 3], [[4, .5], [.25, 3]],
    [1e8, 1e10], [0, .7], .31)
samples = model.permittivity(frequency)  # synthetic demonstration
request_input = TensorDebyeFitDocument(frequency,
    eps_real=samples.real, eps_loss=-samples.imag,
    relaxation_hz=model.relaxation_hz, angles_rad=model.angles_rad,
    eps_inf_angle_rad=model.eps_inf_angle_rad, max_error=1e-8)
saved = request_input.dumps()
assert normalize_saved(saved) == saved
assert TensorDebyeFitDocument.loads(saved).dumps() == saved
request = SavedExecutionRequest(saved, max_evaluations=len(frequency))
receipt = request.run()
assert receipt['execution']['status'] == 'complete'
assert receipt['execution']['result']['accepted']
assert receipt['execution']['result'] == request_input.analyze().to_dict()
```

문서는 `schema`, `frequency_hz`, `eps_real`, `eps_loss`, `relaxation_hz`,
`angles_rad`, `eps_inf_angle_rad`, `weights`, `max_error`의 정확히 아홉 키를 가집니다.
생성자 기본값은 주파수마다 가중치 1, 고주파 각도 0으로 명시하여 저장합니다.
저장 요청에는 null 가중치나 누락 필드를 쓸 수 없습니다. 추가·중복 키, JSON의
NaN/Infinity, 불리언, 잘못된 모양·물리 입력은 거부합니다. 배열을 별도 JSON 데이터로
복사하며 구버전 판독기는 새 스키마를 거부합니다.

`execute_saved`와 불변 저장 요청은 기존 UTF-8 입력 바이트 제한을 사용합니다.
SVD·최적화 전에 주파수 표본 수가 `max_evaluations` 이하여야 하며 같은 값은
허용합니다. 이는 표본 수 입장 조건이며 시간·메모리·호스트 취소 보증은 아닙니다.
직접 `analyze()`는 피팅의 2–10000 표본·1–16 극점 제한을 사용합니다. 두 경로 모두
전계 계산은 하지 않습니다. 식별 불가능한 설계와 최적화 실패는 원래 예외를 유지하고
만들어낸 후보를 반환하지 않습니다.

```python
raw = request_input.to_dict()
raw['eps_loss'] = (-samples.imag + .01*np.eye(2)).tolist()
raw['max_error'] = 1e-5
unmatched = TensorDebyeFitDocument.from_dict(raw)
output = execute_saved(unmatched.dumps(), max_evaluations=len(frequency))
assert output['status'] == 'complete'
assert not output['result']['accepted']
assert output['result']['eps_loss'] == raw['eps_loss']
assert len(output['result']['residual']['real']) == len(frequency)
```

실행 완료와 표본 오차 수락은 별도입니다. 한계를 넘는 피팅도 원입력·예측·잔차와
수동 텐서 후보를 전부 보존합니다. `result['model']`은 기존 중첩
`sipi.dielectric/3` 재료 문서이므로 `dielectric_from_dict`로 읽어 저장 선로에 넣을 수
있습니다. 데이터가 실측인지, 실제 재료가 존재하는지, 표본 사이 주파수에서도 오차
조건을 만족하는지를 인증하지 않습니다. 피팅 결과 사전과 실행 영수증은 출력이며
추가 저장 입력 스키마가 아닙니다. 요청 식별자는 정규화 입력·실행 조건을 포함하지만
실행 산출물의 진위와 호스트 실행 수명 관리는 별도입니다.

```sh
python -m pytest -q tests/sipi/test_tensor_dielectric_fit_document.py tests/sipi/test_tensor_dielectric_fit.py tests/sipi/test_dielectric_fit_document.py tests/sipi/test_execution.py tests/sipi/test_execution_request.py
```

수락·미수락 저장 결과를 직접 피팅과 정확히 대조하고 엄격한 왕복 저장, 최적화 없는
준비, 표본/바이트 한계의 경계값, 수치 실패 보존을 검사합니다. 기존 스칼라 피팅과
저장 입력은 같은 계약을 유지합니다. 이 실행 연결은 새로운 물리 정확도·브라우저
연결·플랫폼 지원을 뜻하지 않습니다.
