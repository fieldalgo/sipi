# 모서리 해상도가 포함된 단면 저장

`CornerCrossSectionDocument`는 기존 `CrossSectionDocument`와 미터 단위의
모서리 목표 크기를 저장합니다. 엄격한 `sipi.corner-cross-section/1`
객체의 키는 `schema`, `cross_section`, `corner_size` 세 개입니다.
내포된 단면은 기존 버전 1, 2, 3의 계약을 유지합니다.

```python
from sipi import stripline, CrossSectionDocument, CornerCrossSectionDocument
from sipi.execution import normalize_saved

section = stripline(width=.0006, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)
original = CrossSectionDocument(section, mesh=dict(
    edge_size=1e-5, far_size=.0002, grade=.15))
saved = CornerCrossSectionDocument(original, corner_size=2.5e-6)
text = saved.dumps()
assert normalize_saved(text) == text
assert CornerCrossSectionDocument.loads(text).cross_section.dumps() == original.dumps()
# parameters = saved.analyze()
```

생성·불러오기는 장 계산을 실행하지 않습니다. 크기는 불리언이 아닌
유한한 양수이며, 해석된 `edge_size`보다 클 수 없습니다. 접근자는
독립된 기하·설정 사본을 반환하고 저장 문서 자체는 불변입니다. 중복 키,
알 수 없는 필드, 미지원 버전, 비유한 숫자는 거부합니다. 계산을 재현할
때는 `saved.mesh_options`를 사용해야 합니다. 내포된 문서만 쓰면 별도로
저장된 모서리 크기가 빠집니다.

공통 저장 실행·요청·실행 기록·프로젝트 인터페이스에서 단독 단면으로
사용할 수 있습니다. 크기를 바꾸면 다른 입력이 되므로 프로젝트는 예전
기록을 보존하면서 변경된 설계의 선택 결과를 해제합니다. 실행 기록의
아티팩트 선언은 여전히 필수이며, 호스트가 선언한 값이지 자동 출처
검증이 아닙니다. 기존 단면은 메시 내부의 `corner_size`를 계속 거부하고,
기존 선로·공차·목표 문서도 이 새 문서를 자동으로 받아들이지 않습니다.

직접 제어의 네 기하 사례를 실제 계산하여 행렬의 정확한 일치를 확인합니다.
기록·프로젝트를 다시 여는 시험은 실제 결과의 명시적인 캐시를 사용하며,
추가 장 계산으로 세지 않습니다. [메시 제어의 한계](corner_mesh_control.md)를
참고하세요. 입력 저장 자체가 절대 정확도나 표면 손실 수렴을 인증하지는 않습니다.

[English](../../../../../packages/sipi/corner_document.md)
