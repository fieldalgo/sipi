# 명시적인 모서리 메시 크기

`CrossSection.mesh`, `mesh_settings`, `analyze`에 선택 인자
`corner_size`를 미터 단위로 지정할 수 있습니다. 유한한 실수이며
`0 < corner_size <= edge_size`여야 합니다. `edge_size`를 생략하면
해석된 기본 크기와 비교합니다. 불리언은 거부합니다.

```python
from sipi import stripline

section = stripline(width=.0006, plane_spacing=.002, eps_r=4.,
                    thickness=.0004, box_width=.008)
settings = section.mesh_settings(edge_size=1e-5, far_size=.0002,
                                 grade=.15, corner_size=2.5e-6)
assert settings['corner_size'] == 2.5e-6
# field = section.mesh(**settings)
# parameters = field.line_parameters()
```

메시 크기 목표는 `corner_size + grade * corner_distance`,
`3 * edge_size + grade * trace_distance`, `far_size`의 최솟값입니다.
모서리는 기존 도체와 국소 유전체 영역의 꼭짓점을 포함합니다.
도체 면의 크기 목표를 유지하면서 모서리 목표를 따로 줄일 수 있습니다.
`grade=0`이면 모서리 목표가 전체 영역에 적용됩니다. 이는 생성기의
목표이며 정확한 요소 길이나 점 개수의 단조 증가를 보장하지 않습니다.

생략하거나 `None`을 주면 기존 네 키의 설정과 메시를 그대로 유지합니다.
`corner_size=edge_size`를 명시해도 크기 함수는 같습니다. 기하·재료·생성
순서·경계 표지는 바뀌지 않습니다. 전체 크기를 세분할 때는
`edge_size`, `far_size`, `grade`와 함께 `corner_size`도 절반으로 줄이고
`min_angle`은 유지합니다.

이 설정을 원래 기하와 함께 보존하려면 별도의
[모서리 단면 저장](corner_document.md) 문서를 사용하세요. 기존 단면
저장 버전 1–3과 이를 사용하는 공차·목표 저장 경로는 이 키를 계속 거부합니다.
기존 문서에 키를 삽입하거나 실험을 기록할 때 키를 누락하지 마세요.

직사각형·사다리꼴·다각형·국소 유전체 단면에서 기본 메시 동일성,
기하 면적과 재료 표지, 균일 유전체 정전용량 관계, 별도의 유한 메시·외곽
비교, 독립 이차 유한요소 정전용량 대조를 검증합니다. 이 유한 관측은
절대 정확도나 표면 손실 수렴 또는 모든 기하의 정확도를 인증하지 않습니다.
작은 상호 손실항은 별도로 각 항의 수렴을 확인해야 합니다.

[English](../../../../../packages/sipi/corner_mesh_control.md)
