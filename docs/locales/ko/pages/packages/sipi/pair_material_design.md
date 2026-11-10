# 기하·재료를 함께 조정하는 쌍 임피던스 목표

`seek_pair_impedances`는 `factory(p0,p1)`와 `material_factory(p0,p1)`가 공유하는
양의 두 변수를 유한 범위에서 조정합니다. 첫 함수는 단면, 두 번째는 영역 이름과
유전체 모델의 매핑을 반환합니다. 0 이상인 고정 `frequency`가 필요하며 `materials`와
함께 사용할 수 없습니다. 같은 변수 쌍에서 두 함수는 일관된 결정적 입력을 반환해야
합니다. 제어 입력은 두 함수 호출 전에 검사합니다. 기존 대칭쌍·실수 정전용량·진공
인덕턴스 제약은 그대로 유지합니다.

예제의 변수는 m 단위 선폭과 무차원 Debye 강도입니다. 알려진 기준 치수에서 시작해
두 번 평가합니다. 실제 탐색은 `initial=(.35e-3,5.5)`, `max_evaluations=64`로 실행합니다.

```python
import json
from sipi import seek_pair_impedances
from sipi.templates import coupled_stripline
from sipi.dielectric import DebyeDielectric

def section(width, strength):
    return coupled_stripline(width=width, gap=.1e-3, plane_spacing=1e-3,
        eps_r=1., box_width=8e-3)

def material(width, strength):
    return {'dielectric': DebyeDielectric(2., [strength], [1e9])}

result = seek_pair_impedances(section, ((.3e-3,.7e-3),(2.,6.)),
    (69.86609070536932,30.721416289368904), tolerances=(.5,.2),
    frequency=1e9, material_factory=material, initial=(.5e-3,4.),
    max_evaluations=2, mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1))
assert len(result.history) == 2
assert all(abs(r)<=t for r,t in zip(result.refined_residuals,result.tolerances))
assert result.history[0].material_evaluation_json == result.history[1].material_evaluation_json
assert json.loads(result.material_evaluation_json)['frequency_hz'] == 1e9
```

## 입력 보존·예산·실패

목적값 cache에 없는 한 변수 쌍의 시도는 기하·재료 인코딩·장해석·진단을 포함하며
어느 단계에서 실패해도 한 번으로 셉니다. Jacobian 탐색점은 세고 같은 변수 쌍의
목적값 cache 재사용은 세지 않습니다. 새 변수 평가에서 메시를 재사용해도 시도는
한 번 소모하며 마지막 세분 검사를 위해 한 번을 예약합니다. 각 완료
`PairImpedanceEvaluation`은 `material_evaluation_json`을 보존하고 매핑이 있을 때
dict에 `material_evaluation`을 넣습니다. 순수 기하 행의 기존 dict 형식과 네 인자
생성은 유지합니다. 고정 재료도 행마다 보존합니다.

세분 검사에는 선택된 기하와 인코딩한 모델을 동결해 사용하며 두 factory 모두 다시
호출하지 않습니다. 호출자가 원래 매핑을 바꿔도 저장 입력은 바뀌지 않습니다.
결과에는 선택 모델, 각 이력에는 해당 시점의 기하·재료 쌍이 있으므로 재실행 시
반드시 그 행의 두 입력을 함께 사용합니다.

`PairImpedanceGoalError`는 완료 이력·실제 시도 수·단계·원인과 가능한 현재 기하/모델을
보존합니다. 재료 생성 자체가 실패하면 유효한 현재 모델이 없으며 이전 행의 매핑으로
대체하지 않습니다. 인코딩 후 장해석 유효성 검사에서 실패한 모델은 예외에 남습니다.
optimizer 실패 시 cache에 있는 후보의 기하·모델도 보존합니다. 함수 자체는 직렬화하지
않습니다. 저장 `pair-impedance-design/1`은 계속 고정 재료만 지원하며 새 입력 스키마는
추가하지 않습니다.

[저장 버전 2 목표](pair_material_document.md)는 함수를 직렬화하지 않고 명시적인
이름과 재료 숫자 필드 연결을 저장합니다.

## 한 탐색 안의 반복 기하

재료 평가의 전체 단면 문서가 같으면 그 탐색 안에서 메시 하나와 진공 정전용량을
재사용합니다. 기하·경계·신호 및 재료의 이름과 순서·기본 재료·명시한 메시 설정을
모두 키에 포함합니다. 문서가 바뀌면 이전 항목을 버린 뒤 새 메시를 만들고,
세분 검사는 별도의 더 촘촘한 메시를 사용합니다. 전역 또는 탐색 간 캐시나
보존하는 전계 벡터는 없습니다.

목적값 cache에 없는 변수 평가마다 현재 재료를 검증·평가하고 재료에 따른
정전용량·손실과 기존 pair 진단을 계산합니다. factory 호출, 시도 예산과 오류
문맥은 그대로입니다. 반복 변수 쌍은 기존 목적값 cache를 계속 사용하며,
새 변수 평가에서 메시를 재사용해도 시도는 소모합니다. 기하가 고정인 재료
탐색의 중복 메시를 줄이는 기능이며 유일한 변수 복원이나 일반적인 속도
향상을 보장하지 않습니다.

재사용 시험은 실제 대각 텐서 탐색, 두 탐색의 격리, 실제 세분 메시 실패,
변경 재료의 전계 실패, 재사용 기하의 잘못된 재료와 시도 예산 보존을 다룹니다.
이는 아래 물리 기준을 보완하는 제어·호환성 검사입니다.

## 독립 수락과 범위

시험은 Cohn 얇은 결합 stripline 식, 간격 .1mm·평면 간격 1mm·1GHz에서 균일한
Debye 유전율 `2+strength/(1+j)`를 사용합니다. 선폭 .5mm·강도 4의 실수 유전율 4에서
위 목표를 얻습니다. (.35mm,5.5)에서 시작해 복원한 선폭·강도 각각 기준의 2% 이내를
요구합니다. 요청 메시 `(1um,.125mm,.1)`와 절반 세분 모두 차동/공통 절대 허용 오차
(.5,.2)Ω를 만족해야 합니다. 같은 선택 기하·모델을 상자16mm와 독립 Cohn 식으로도
검사합니다. 모든 행의 모델을 확인하고 첫 행/선택 행의 실제 재실행은 상대 1e-10을
요구합니다. 별도 시험은 실패·실제 예산·모델 동일성·factory 재호출 없는 세분을 검사합니다.

명시 사례 수락이며 실측 재료 보정이나 일반 정확도 추정이 아닙니다. 단일 주파수의
두 목표로 전체 분산 모델을 식별하거나 유일해·광대역 성능·임의 유손실/모드 최적화를
보장하지 않습니다. 호출자가 물리적으로 의미 있는 변수와 식별 가능성을 정해야 합니다.

[쌍 역산](pair_design.md) · [목표 저장](pair_design_document.md) ·
[English](../../../../../packages/sipi/pair_material_design.md)
