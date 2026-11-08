# 명시한 주파수 샘플의 임피던스 목표

`seek_sampled_impedance`는 양의 범위를 가진 정확히 두 변수를 조정해 2~64개의
지정 주파수에서 한 실수 준정적 임피던스량을 맞춥니다. 신호 하나는 `quantity='z0'`,
교환 대칭쌍은 `z_diff`/`z_common`을 사용합니다. 실수 정전용량과 진공 인덕턴스 및
[쌍 역산](pair_design.md)의 대칭 검사를 재사용합니다. 복소 유손실·종단·full-wave
특성 임피던스가 아닙니다.

주파수는 유한하고 0 이상이며 엄격한 오름차순이어야 합니다. 각 주파수마다 양의 유한
목표·절대 허용 오차를 Ω 단위로 지정합니다. 두 변수 단위는 기하/재료 factory를
따릅니다. `initial`은 양의 범위 안이며 기본값은 중간점입니다. 예제는 알려진 기준
치수에서 시작하므로 요청/세분 두 번으로 충분합니다. 탐색은
`initial=(.35e-3,5.5)`, `max_evaluations=64`로 실행할 수 있습니다.

```python
from sipi import seek_sampled_impedance
from sipi.templates import coupled_stripline
from sipi.dielectric import DebyeDielectric

def geometry(width, strength):
    return coupled_stripline(width=width, gap=.1e-3, plane_spacing=1e-3,
        eps_r=1., box_width=8e-3)

def material(width, strength):
    return {'dielectric':DebyeDielectric(2.,[strength],[1e9])}

result = seek_sampled_impedance(geometry,
    bounds=((.3e-3,.7e-3),(2.,6.)), frequencies=[1e8,1e10],
    targets=[57.23463009022641,97.84159316427296], tolerances=[.5,.5],
    quantity='z_diff', material_factory=material, initial=(.5e-3,4.),
    max_evaluations=2, mesh=dict(edge_size=1e-6,far_size=.125e-3,grade=.1))
assert len(result.history) == 2
assert result.frequencies == (1e8,1e10)
assert all(abs(r)<=t for r,t in zip(result.refined_residuals,result.tolerances))
assert result.history[0].material_sweep_json == result.history[1].material_sweep_json
report = result.to_dict()
assert report['quantity'] == 'z_diff'
```

## 모델·일괄 평가·입력 보존

`factory(p0,p1)`는 단면을 반환합니다. 고정 `materials` 또는 선택적
`material_factory(p0,p1)`로 지원 유전체 모델을 주며 둘을 동시에 사용할 수 없습니다.
둘 다 생략하면 빈 override로 기하의 물성 입력을 유지합니다. 두 함수는 결정적이어야
합니다. 제어 입력은 함수 호출 전에, 신호 개수/순서와 각 주파수의 재료 유효성은 메시
전에 확인합니다. 쌍 임피던스는 기울어진 횡방향 텐서를 거부하고 탐색 전체에서 신호
이름과 순서를 유지합니다.

한 변수 쌍의 일괄 평가는 기하·재료 인코딩·장해석·진단을 포함합니다.
`dispersive_line`으로 메시 하나에서 진공 정전용량과 주파수별 복소 정전용량을 구합니다.
cache에 없는 시도는 실패와 Jacobian 탐색점까지 한 번으로 세며 cache 재사용은 세지
않습니다. 이는 일괄 평가 예산으로 내부 장해석 횟수와 다릅니다. `max_evaluations`는
2~10000, 기본 64이고 최종 세분 한 번을 예약합니다. 시간·메모리·내부 solve 수는
제한하지 않으며 프로세스 취소는 호출자가 담당합니다.

완료 `SampledImpedanceEvaluation`마다 `quantity`와 `input_json`, `frequencies_hz`/인코딩한
`materials`를 가진 `material_sweep_json`을 보존합니다. 해당 행 재현에는 둘 다 필요합니다.
선택 기하와 모델을 동결해 두 factory를 다시 호출하지 않고 세분 검사합니다.
확정된 `edge_size`, `far_size`, `grade`를 절반으로 줄이고 다른 메시/물리 입력은
유지합니다. 양쪽 메시에서 모든 주파수 목표가 통과해야 합니다. 초기점이 모두 만족해도
이 세분 시도는 필요합니다.

`SampledImpedanceDesign`은 양쪽 결과·잔차, 선택 입력, 주파수/물리량과 전체 이력을
보존하며 `to_dict()`는 독립된 JSON 호환 값을 반환합니다. `SampledImpedanceGoalError`는
물리량·주파수·실제 시도 수·단계·실패 변수·원인 및 가능한 현재 입력과 완료 이력을
보존합니다. 모델 생성 실패 시 이전 행의 모델을 현재 모델로 대신하지 않습니다.
인코딩한 모델이 장해석 유효성 검사에서 실패해도 해당 입력은 남습니다. 이 API는
저장 입력 스키마나 함수 직렬화를 추가하지 않습니다.

[이름 있는 주파수 목표 저장](sampled_design_document.md)은 템플릿 변수·주파수 목록·
목표·제약·명시 재료 연결을 보존합니다.

## 수치 정책과 독립 수락

기존 두 변수 역산과 같은 정책을 공유합니다. 변수를 [0,1], 잔차를 허용 오차로
정규화하고 범위의 1% 간격 중앙/한쪽 차분 Jacobian과 bounded SciPy `least_squares`
(`xtol=ftol=1e-4`, `gtol=1e-3`)를 사용합니다. 어느 목표라도 놓치면 optimizer의 성공
표시만으로 수락하지 않습니다. 퇴화·초기점 수락·국소 수렴은 유일한 변수나 전역 최적해를
증명하지 않습니다. 잘못된 기하를 잘라내거나 다시 뽑지 않습니다.

독립 Cohn 얇은 stripline 사례는 간격 .1mm·평면 간격 1mm·폭 .5mm·균일 Debye
eps_inf=2/강도4/pole1GHz이며 .1/10GHz 차동 목표는 위 예제와 같습니다.
(.35mm,5.5)에서 시작해 복원한 선폭·강도 각각 기준의 2% 이내를 요구합니다.
요청 메시 `(1um,.125mm,.1)`, 절반 세분, 상자16mm, 선택 입력의 독립 Cohn 값이 모두
주파수별 .5Ω를 만족해야 합니다. 첫/선택 행의 일괄 재실행은 상대 1e-10을 요구합니다.
별도 scalar/common 시험은 DC를 포함해 요청/세분당 메시 하나를 확인하고 개별 주파수
계산 및 균일 진공값/sqrt(Re(eps))와 상대 1e-10으로 비교합니다.

명시한 수치 기준이며 실측 기판 정확도를 뜻하지 않습니다. 유한 주파수 목록의 지점만
제약하고 그 사이 응답은 제약하지 않습니다. 재료 분산 외삽·자동 pole·복소 유손실 목적·
연속대역 최적화는 계약 밖입니다. 모델 유효성과 식별 가능성은 호출자가 정해야 합니다.
이 엔진 검사로 브라우저·앱 엔진·Windows 수락을 주장하지 않습니다.

[쌍 목표](pair_design.md) · [재료 목표](pair_material_design.md) ·
[English](../../../../../packages/sipi/sampled_design.md)
