# 유한 주파수 전체에 적용하는 두 임피던스 제조 표본

[English](../../../../../packages/sipi/sampled_panel_pair_study.md) ·
[단일 주파수 두 양 표본](panel_pair_study.md) · [다주파수 목표](sampled_panel_pair_goal_document.md)

`SampledPanelForwardPairStudyDocument`는 같은 제조 기하·재료 표본을 요청한 모든
주파수에서 평가합니다. 한 행은 전체 복소 패널 전류 선로에서 두 혼합 특성행렬
대각의 실수부 `Re(Zdd)`, `Re(Zcc)`를 구합니다. 주파수 지점을 독립 제조 표본으로
세거나 주파수마다 다른 기하·재료를 다시 뽑지 않습니다.

엄격한 `sipi.sampled-panel-forward-pair-study/1` 키는 `schema`, `study`,
`conductor`, `panel`, `frequency_hz`입니다. 중첩 paired `z_diff_forward`의 study/3
또는 /4는 기존 기하·재료 변수, sweep/corners/uniform/상관 정규분포 방식 및 고정
피치·평면 간격 규칙을 유지합니다. 재료 기준 주파수는 요청 배열의 첫 주파수와
정확히 같아야 합니다. 배열은 엄격히 증가하는 양의 Hz 2..64개입니다. 패널 설정과
기하·재료·자원·표피 깊이 제한도 그대로 적용합니다.

명목 전체 주파수 입력 정규화는 장 계산을 하지 않습니다. 분석 전에 모든 표본
벡터를 생성하고 개수가 `max_evaluations`(정수 2..10000) 이내인지 검사합니다.
그 뒤 각 원래 표본을 전체 주파수 선로 묶음으로 한 번씩 시도합니다. 실패 행도 세며,
주파수 수나 내부 장 계산 횟수·시간·메모리 상한이 아닙니다. 중복 표본과 순서를
유지하고 실패 이후 행도 계속 계산합니다. 자르기·제외·재추출·가중치 변경은 없습니다.

불변 행에는 순번, 순서대로의 표본 값, 가능한 기하 매개변수·기준 재료 입력·전체
주파수 선로 입력·추출 결과가 남습니다. 성공 `values`는 주파수 우선 `(N, 2)`이며
두 열은 차동·공통입니다. 신호 이름, 주파수 좌표, single-ended/mixed 기준, 전체
유한 복소행렬과 양의 실수 대각을 검사합니다. 어느 주파수든 실패하면 행 전체를
미해결로 남기고 부분 값 배열을 만들지 않습니다. 원래 단계·예외 종류·메시지를
보존하며 빈 오류 메시지도 실패로 처리합니다.

모든 행이 성공해야 기술통계를 제공합니다. 각 양의 이름은 주파수별 최소·최대·평균·
표본 표준편차·보간 p05/p95 배열에 대응합니다. 중첩 통계는 불변이며 같은 원래
표본 수를 사용합니다. 신뢰구간이나 생산 수율 추정이 아닙니다. 명목 메시 크기와
패널 설정은 고정되지만 필요하면 기하 메시를 다시 만들며, 행마다 자동 세분·외곽
수렴 인증을 실행하지 않습니다.

`execute_saved()`는 전 행 성공이면 `complete`, 아니면 `incomplete`를 반환합니다.
모든 행을 보존하며 미해결 행이 있으면 통계는 없습니다. 잘못된 입력이나 전체
표본 생성·예산 실패는 장 계산 전에 예외를 냅니다. diagnostic 옵션은 기존처럼
최상위 선로에 한정하며 이전 저장 형식과 단일 주파수 방법은 바꾸지 않습니다.

## 재현 가능한 상관 재료 예제

예시 분포의 네 행은 각 제조 표본 안에서 두 지역의 Debye strength를 같게 유지하고
세 주파수에서 그 표본을 평가합니다. 실측으로 추정한 제조 분포나 수율 근거가 아닙니다.

```python
from sipi.dielectric import DebyeDielectric
from sipi.study import ImpedanceStudyDocument
from sipi.sampled_panel_pair_study import SampledPanelForwardPairStudyDocument
from sipi.execution import normalize_saved, execute_saved

frequencies = [0.5e9, 1e9, 2e9]
material = DebyeDielectric(3.0, (0.7,), (1e9,))
study = ImpedanceStudyDocument("coupled_microstrip",
    dict(width=0.3e-3, gap=0.2e-3, substrate_height=0.5e-3, eps_r=4,
         thickness=35e-6, air_height=2e-3, box_width=6e-3),
    quantity="z_diff_forward", frequency=frequencies[0],
    materials=dict(substrate=material, air=material),
    mesh=dict(edge_size=10e-6, far_size=0.2e-3, grade=0.1),
    material_variables={
        "strength_substrate": dict(region="substrate", path=["strengths", 0]),
        "strength_air": dict(region="air", path=["strengths", 0])},
    sampling=dict(kind="normal", count=4, seed=3,
        correlation=[[1.0, 1.0], [1.0, 1.0]], variables=[
            dict(name="strength_substrate", mean=0.7, std=0.05),
            dict(name="strength_air", mean=0.7, std=0.05)]))
request = SampledPanelForwardPairStudyDocument(study,
    conductor=dict(kind="perfect"), frequencies=frequencies)
text = request.dumps()
assert normalize_saved(text) == text
output = execute_saved(text, max_evaluations=4)
assert output["status"] == "complete"
assert output["result"]["count"] == 4
assert output["result"]["frequencies_hz"] == frequencies
assert len(output["result"]["summary"]["differential_forward_impedance_real"]) == 3
```

## 검증과 유효 범위

독립 주파수 모드 해석식, 실제 scikit-rf 모드 선로 및 스칼라 통계로 각 주파수·행을
대조합니다. 네 행 예산의 64주파수, 중복·상관 표본, 모든 실패 단계, 중간 주파수의
잘못된 진단, 불변 기록, 엄격한 전송 제한과 후속 행 보존을 검사합니다. 실제 비균질
네 꼭짓점 기하는 balanced 2N 특성 고유공간과 1e-10 이내에서 일치합니다. 첫·마지막
꼭짓점의 체적·패널·동시 세분, 상대 변화 0.005 이하 및 세 외곽 영역에서 여섯 양의
연속 절대 변화 감소를 별도로 확인합니다. 공차 범위 전체나 임의 요청을 자동
보증하는 검사는 아닙니다.

균일 상관 Debye 표본은 전체 복소 재료 구성식 1e-10, C/G·통계 1e-12, R=0으로
검증합니다. 이 불변식은 기하의 진공 정전용량을 공유하므로 독립 기하·실측 근거가
아닙니다. 유한 주파수는 연속 대역을 보증하지 않습니다. Worker·브라우저·데스크톱
패키징·시간 제한·취소 동작 또는 플랫폼 지원을 추가한다는 뜻도 아닙니다.
