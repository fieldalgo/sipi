# 직선면별 형상전류 에너지

`panel_shape_face_current_factors`는 각 직선 도체 면에서 Ki*Kj 적분을
명시적으로 계산합니다. 바닥 접지·위/옆 열린 경계에 접지 패턴을 포함한
1~4개의 유한 직사각형 또는 사다리꼴 `Trace`를 지원합니다. 임의
`PolygonTrace`는 이 API에서 허용하지 않습니다. [전체 둘레 형상전류
방식](panel_shape_conductor.md)을 재사용하며 기존 기본값·저장 스키마·
재료 모델은 바꾸지 않습니다.

연속적인 꼭짓점 변위가 선택한 면에 단위 안쪽 법선 속도를 주고 다른 면에는
법선 속도 0을 줍니다. 정전용량 형상 미분을 기존 전체 둘레 계산과 같은
단위 신호전류 좌표로 변환하며 접지 패턴의 전위는 0입니다. 이는 에너지
행렬이며 부호 있는 면별 전류 적분이 아닙니다. 에너지에서 면별 전류를
추정하거나 유한 전도도 내부·코팅 모서리를 해석하지 않습니다.

첫 계산 전에 모든 기하와 두 이동폭을 사전 검사합니다. 실제 추출에는
기존 공유 솔버의 패널·영역 검사가 적용됩니다. 전체 도체 n개에서 원래
4*n+5개 전체 둘레 표본을 보존하고 16*n개 면별 풀이를 추가하므로
20*n+5개(최대 85개)입니다. `panels_per_edge`, `ground_modes`,
`interpolation_degree`, `step_fraction`은 기존 한도를 유지합니다.
숨은 세분·대체 계산·자동 방식 전환은 없으며 풀이 횟수가 개별 계산의
메모리나 시간을 제한하지는 않습니다.

`PanelShapeFaceCurrentFactors`는 불변 `step_parts`, `samples`,
`diagnostics`, `trace_names`, `trace_ground`를 보존합니다. `parts`는 작은
이동폭 결과입니다. 기하 순서의 각 도체에서 bottom/top/left/right 순서로
배열하고 마지막에 바닥 접지판을 둡니다. 경사면도 left/right 이름을 유지합니다.
`labels`는 `signal:<name>:<face>`, `reference:ground:<name>:<face>`,
`reference:bottom`을 구분합니다. 신호와 접지 패턴이 기하 순서에 섞일 수
있으므로 재료 가중치에 이름을 사용해야 합니다. `total`은 전체 면의 합,
`whole_boundary_step_parts`는 도체별 재합산입니다. `names`, `C0`,
`L_external`은 원 신호 좌표를 유지합니다. `base`에는 모든 원 전체전류
근거가 있고, 합산된 `current_integrals`와 전류 보존 진단은 에너지 행렬과
구분됩니다.

두 면별 이동폭·총합·면별 합과 전체 둘레의 비교는 모든 항에서 분모 바닥값
없는 상대 1e-4를 요구합니다. 상반성·PSD는 1e-10, 총 에너지는 양의 정부호를
요구하며 비유한 결과를 거부합니다. PSD 투영이나 전류 보존 재가중은 없습니다.
원 전체전류 실패는 원 예외와 근거를 유지합니다. 이후
`PanelShapeFaceCurrentError`에는 `base`, 완료한 면별 `samples`, 실패한
`request`, 가능한 경우 전체 `step_parts`가 남습니다. 중단 예외는 전파합니다.

아래는 사다리꼴 접지 패턴의 준비 예제입니다. 주석의 호출은 장 계산을
시작합니다. 치수는 m, 전류 에너지 인자는 1/m입니다.

```python
from sipi import CrossSection, Layer, Trace, panel_shape_face_current_factors

section = CrossSection([Layer('uniform', .01105, 4.)], [
    Trace('a', -.0005, .0003, .001, 50e-6, top_width=.00022),
    Trace('guard', 0., .0002, .001, 50e-6, ground=True, top_width=.00012),
    Trace('b', .0005, .0004, .001, 60e-6, top_width=.00055),
], .02)
options = dict(panels_per_edge=32, ground_modes=4096,
               interpolation_degree=16, step_fraction=.001)
# factors = panel_shape_face_current_factors(section, **options)
# print(factors.labels, factors.parts)  # Starts actual field solves.
```

정확한 법선 이동·합 불변식, 저장된 직사각형 선로 전위의 독립 P2 체적 에너지
적분, 명시 직사각형·사다리꼴 면별 관측을 검사합니다. 별도 영상해 연구에서
원형 사분면 적분과 다각형·패널·유한 외곽 세분을 나누어 확인하지만, 이 API에
원형 도체 지원을 추가한 것은 아닙니다. 직사각형의 P2 법선 gradient 직접
적분은 충분히 수렴하지 않아 수락 기준으로 사용하지 않았으며 원 실패를
그대로 보존했습니다.

이동폭 일치·선택한 유한 외곽 변화·전체 둘레 일치는 절대 오차나 작은
상호항의 오차 한계가 아닙니다. 실제 기하에서 패널과 외곽을 독립적으로
세분해야 하며 미해결 입력은 실패할 수 있습니다. 이번 에너지 API 단위에는
재료 손실 가중·새 저장 입력·브라우저 연결·교차 플랫폼 수락이 없습니다.

[명시 면별 표면 재료 적용](shape_face_conductor.md).
