# 전도율 프로파일 입력 저장

`ConductivityProfileDocument`는 제한된 [Gaussian 반공간 커널](conductivity_profile.md)의
입력과 외측 기준면 cutoff를 저장합니다. 이 법칙을 전송선 도체에 추가하지 않습니다.
새 입력 스키마는 `sipi.conductivity-profile/1`입니다.

```python
import json
from sipi import GaussianConductivityProfile, ConductivityProfileDocument
from sipi.execution import normalize_saved, execute_saved

doc = ConductivityProfileDocument(
    GaussianConductivityProfile(conductivity=58e6, rms_m=1e-6),
    [1e9, 4e9, 10e9], cutoff_rms=8)
text = normalize_saved(doc.dumps())
assert text == doc.dumps()
output = execute_saved(text, max_evaluations=3)
assert output['status'] == 'complete'
assert output['input'] == doc.to_dict()
assert output['result']['reference_plane_m'] == -doc.cutoff_rms*doc.profile.rms_m
assert output['result']['frequency_hz'] == [1e9, 4e9, 10e9]
json.dumps(output, allow_nan=False)
```

최상위 필드는 정확히 `schema`, `model`, `frequency_hz`, `cutoff_rms`입니다.
`model`에는 다음 필드만 필수로 받습니다.

```json
{"kind": "gaussian-conductivity", "conductivity_s_per_m": 58000000.0, "rms_m": 1e-6}
```

물리 단위와 수치 한도는 커널 계약을 따릅니다. Python 생성자의 cutoff 기본값은 8이지만
저장 JSON에는 명시해야 합니다. RMS 0은 같은 전체 Maxwell 평활 극한을 선택합니다.
암묵적 대체 모델·단위 환산·미지 필드 수락·자동 마이그레이션은 없습니다.
누락/중복 키·비유한 수·물리값의 bool·미지원 버전/종류·범위 초과는 parsing에서 실패합니다.
호출자의 dict나 반환한 입력 dict를 바꿔도 저장 요청은 바뀌지 않습니다.
`frequency`는 새 배열이며 `profile`은 불변 모델입니다.

parsing과 `normalize_saved`는 적분 없이 검증합니다. `analyze`와 `execute_saved`는
주파수당 한 번을 평가 수로 세고 `max_evaluations` 초과를 **적분 전에** 거부합니다.
공통 예산은 정수 2..10000, 기본값 128이며 커널의 별도 1024주파수 한도도 유지됩니다.
주파수 한 개 요청도 예산이 2 이상이면 유효합니다. 예산은 실행 시간이나 취소를 보장하지
않으며 호출자가 실행 격리를 담당합니다. 미지원 선로 진단은 프로파일 해석 전에 거부합니다.
적분 실패는 전파하며 부분 결과를 성공한 계산으로 반환하지 않습니다.

공통 출력은 기존 `sipi.execution/1` envelope와 정확한 정규 입력을 보존합니다.
`result`는 다음을 포함합니다.

| 필드 | 의미 |
|---|---|
| `frequency_hz` | 원래의 증가하는 주파수 표본 |
| `surface_impedance_ohms` | 외측 E/H의 별도 `real`·`imag` 배열 |
| `skin_depth_m` | 제한 모델을 정의하는 bulk 양도체 delta |
| `cutoff_rms` | 명시적 전이 절단 배수 |
| `reference_plane_m` | `-cutoff_rms*rms_m`; x는 금속 안쪽이 양수이고 평균면은 x=0 |

문서는 결과의 모델·주파수·cutoff가 저장 입력과 같은지 확인합니다. 음수 외측 리액턴스를
그대로 보존합니다. 이 출력의 기준면을 선로 평균면으로 바꾸거나 내부 인덕턴스 보정으로
사용해도 된다는 뜻이 아닙니다. 이전 reader는 새 스키마를 거부하며 기존 웹/EXE 후보의
엔진 고정값도 이번 추가로 바뀌지 않습니다.

시험은 직접 커널과 정확한 재실행·유한 JSON 직렬화, 같은 ±5Rq 면의 독립
scikit-rf 2.2.0과 <1e-6 일치, RMS 0의 해석적 고유 임피던스와 <1e-12 일치를 요구합니다.
엄격한 입력·적분 전 예산·입력 격리·메타데이터 불일치 거부·해석 실패 전파도 확인합니다.
공통 registry 검사에는 이 스키마의 실제 문서를 넣습니다. 커널 계약을 넘어선 새로운
물리·실측·브라우저·Windows 수락을 뜻하지 않습니다.

[공통 실행](execution.md) · [English](../../../../../packages/sipi/conductivity_profile_document.md)
