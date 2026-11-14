# 모서리 해상도를 지정한 기하·재료 표본

`CornerImpedanceStudyDocument`는 기존 임피던스 공차 계산에 고정된
모서리 목표 크기를 적용합니다. 엄격한 `sipi.corner-impedance-study/1`
객체의 키는 `schema`, `study`, `corner_size`입니다. 내포된 공차 문서의
버전 1–4, 템플릿·계산량 제한, 표본 생성, 고정 피치·평면 간격, 재료 변수
연결 계약을 그대로 유지합니다.

```python
from sipi import CornerImpedanceStudyDocument
from sipi.study import ImpedanceStudyDocument

study = ImpedanceStudyDocument('stripline', dict(width=.0006,
    plane_spacing=.002, eps_r=4., thickness=.0004, box_width=.008),
    quantity='z0', mesh=dict(edge_size=1e-5, far_size=.0002, grade=.15),
    sampling=dict(kind='sweep', count=2,
        variables=[dict(name='width', lower=.00055, upper=.00065)]))
saved = CornerImpedanceStudyDocument(study, corner_size=2.5e-6)
assert saved.samples().shape == (2, 1)
assert CornerImpedanceStudyDocument.loads(saved.dumps()).dumps() == saved.dumps()
# result = saved.analyze(max_evaluations=2)
```

유한한 양수인 모서리 목표는 공차 문서의 해석된 명목 `edge_size`보다
클 수 없으며 표본 사이에서 고정됩니다. 생성된 각 행은
[모서리 단면 문서](corner_document.md)를 보존합니다. 재료 대체 정보는
원래 공차 문서에, 표본 재료 정보는 각 행의 재료 평가에도 남습니다.
기하만 재실행하면 재료 대체까지 재현되지는 않습니다.

원래 표본 순서는 바뀌지 않습니다. 중복 표본과 실패 뒤의 행도 모두
시도합니다. 경계 없는 정규분포에서 생긴 부적합 입력은 실패로 남기며
다시 추출하지 않습니다. 호출자의 평가 예산은 장 계산 전에 검사합니다.
통계는 모든 행이 성공했을 때만 제공되며, 명시한 유한 표본의 통계이지
생산 수율 인증이 아닙니다.

재료만 바뀐 행은 한 호출 안에서 기하·모서리 설정이 정확히 같은 메시와
진공 정전용량을 재사용할 수 있습니다. 재료는 매 행 다시 평가합니다.
기하나 모서리 목표가 바뀌면 캐시 키도 바뀝니다. 공통 실행·요청·기록·
프로젝트는 새 문서와 각 행 입력을 보존합니다. 기존 기본값이나 목표
역산 계약에 새 설정을 암묵적으로 허용하지 않습니다.

실제 폭 표본을 별도의 세분 메시 및 독립 이차 정전용량 계산과 비교합니다.
균일 재료 표본에서는 한 메시를 재사용하면서 임피던스가 유전율 제곱근의
역수에 비례하는 관계를 검증합니다. 기존 공차 회귀 결과도 보존합니다.
이는 손실 정확도나 모든 표본·템플릿의 수렴을 인증하지 않습니다. 전체
분해능을 비교할 때는 모서리·edge·far·grade 제어를 함께 세분하세요.

[English](../../../../../packages/sipi/corner_study.md)
