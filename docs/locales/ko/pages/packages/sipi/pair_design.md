# 두 변수로 쌍 임피던스 목표 맞추기

`seek_pair_impedances`는 `CrossSection`을 반환하는 `factory(p0, p1)`의 양의
두 변수를 유한 범위에서 조정합니다. 목표와 절대 허용 오차의 순서는
`(z_diff, z_common)`이며 단위는 Ω입니다. 기존 대칭 두 신호의 정의인
`2*Z_odd`, `Z_even/2`를 사용하고 신호 이름과 순서를 유지해야 합니다.
비대칭 전방 여기, 종단 임피던스, 복소 유손실 특성 임피던스는 이 API 범위 밖입니다.

변수 단위는 factory를 따릅니다. 기본 시작점은 범위 중간이며 `initial=(p0,p1)`로
닫힌 범위 안의 다른 점을 선택할 수 있습니다. 아래 예제는 독립 얇은 도체 기준해에
가까운 점에서 시작하지만 세분 메시 검사도 수행합니다. 독립 수락 시험에서 사용한
폭·간격 탐색은 `initial=(.35e-3,.45e-3)`로 실행합니다.

```python
from sipi import coupled_grounded_coplanar, seek_pair_impedances

def section(width, gap):
    return coupled_grounded_coplanar(width=width, gap=gap,
        ground_gap=.2e-3, ground_width=1e-3, substrate_height=.5e-3,
        eps_r=1., thickness=0., box_width=12e-3, air_height=6e-3)

result = seek_pair_impedances(section,
    bounds=((.3e-3, .7e-3), (.1e-3, .5e-3)),
    targets=(172.45677879183611, 65.9597000672247),
    tolerances=(1.5, .5), max_evaluations=64,
    mesh=dict(edge_size=2e-6, far_size=.125e-3, grade=.15))
assert all(abs(r) <= t for r, t in zip(result.residuals, result.tolerances))
assert all(abs(r) <= t for r, t in zip(result.refined_residuals, result.tolerances))
saved_geometry = result.document.dumps()
report = result.to_dict()
assert report['quantities'] == ['z_diff', 'z_common']
```

요청 메시와 세분 메시에서 **두 목표 모두** 각 허용 오차를 만족해야 성공합니다.
세분 검사는 선택된 기하 snapshot의 확정 `edge_size`, `far_size`, `grade`를 절반으로
줄이며 `min_angle`과 물리 입력은 유지합니다. factory를 다시 호출하지 않습니다.
외곽 상자·공기 확대와 물리적 유효성은 별도 확인해야 합니다.
허용 오차를 작게 지정하는 것만으로 실측 정확도가 확보되지는 않습니다.

## 탐색과 평가 비용

기존 SciPy `least_squares`로 변수를 [0,1]에 정규화하고 잔차를 각 허용 오차로
나눕니다. 각 변수 범위의 1% 간격으로 중앙 또는 한쪽 차분 Jacobian을 평가합니다.
종료 설정은 `xtol=ftol=1e-4`, `gtol=1e-3`이며 optimizer 성공 표시만으로 수락하지
않습니다. 정지점에서 어느 한 목표라도 놓치면 실패입니다. 실현 가능성·연속성·
유일해·전역 최적해를 보장하지 않습니다. 퇴화된 문제도 두 목표를 만족하면 성공할 수
있지만 변수의 유일성을 뜻하지 않습니다. 잘못된 기하는 잘라내거나 다시 추출하지 않습니다.

`max_evaluations`는 2..10000 정수이고 기본 64입니다. cache에 없는 factory/추출 시도는
Jacobian 탐색점과 실패를 포함해 모두 계산합니다. 같은 물리 변수 쌍은 cache를 재사용하고
마지막 세분 검사 한 번을 예약합니다. 초기점이 두 목표를 만족하면 탐색을 생략하지만
두 번째 세분 시도는 필요합니다. 따라서 SciPy `nfev`와 실제 시도 수는 다릅니다.
한 시도가 여러 장해석을 수행할 수 있어 이 예산은 시간·메모리·내부 선형해법 수를
제한하지 않습니다. 프로세스 취소는 호출자 책임입니다.

잘못된 제어 입력은 factory 전에 `ValueError`/`TypeError`로 거부합니다. 이후 실패는
`PairImpedanceGoalError`에 완료 `history`, `attempts`, `stage`, `failed_parameters`,
가능한 `input_json`, `cause_type`과 원인 예외를 보존합니다. 실패한 시도에는 완료 행이
없습니다. 고정 재료의 `material_evaluation_json`도 예외에 보존하므로 실패 도중 호출자가
원래 재료 매핑을 바꿔도 입력을 잃지 않습니다.
`PairImpedanceDesign`과 행은 동결되며 문서 접근자는 새 snapshot을 반환합니다.
`to_dict()`에는 양쪽 메시 입력·잔차·이력이 포함됩니다. callable 자체를 직렬화하지
않으며 이 API는 저장 입력 스키마를 추가하지 않습니다.

## 고정 재료

`frequency`(Hz)와 `materials`를 함께 주면 고정 scalar 또는 주축 유전체 모델을
재사용합니다. 임피던스는 `Re(C_complex)`와 진공 L을 사용하며 도체 R이나 복소 유손실
전파가 아닙니다. 기울어진 횡방향 이방성은 기존 대칭쌍 재료 계약에 따라 거부합니다.
재실행에는 기하와 함께 `material_evaluation_json`이 필요하며 탐색·세분 사이에서
같은 값을 유지합니다. 또는 고정 `frequency`와 `material_factory(p0,p1)`를 주고
`materials`는 생략합니다. 각 완료 행은 자신의 재료 snapshot을 보존하며 세분 검사는
선택 기하와 모델을 재사용하고 두 factory 모두 다시 호출하지 않습니다.
[기하·재료 목표](pair_material_design.md)에 계약·실패 문맥·독립 수락을 설명합니다.
저장 `pair-impedance-design/1` 문서는 여전히 고정 재료 매핑만 받습니다.

## 독립 수락

위 두께 0·전체 진공 사례는 명시적 네 신호/접지 유한 구간과 .5mm 아래 접지면의
독립 image-Green 패널 적분을 사용합니다. 폭 .5mm·간격 .3mm의 160패널 목표는
172.45677879183611Ω과 65.9597000672247Ω입니다. 초기 (.35,.45)mm에서
요청 메시 `(2um,.125mm,.15)`와 절반 세분 모두 1.5Ω/.5Ω 허용 오차를 요구합니다.
같은 최종 기하를 상자24/공기12mm 및 독립160패널로 계산해 같은 목표를 검사하고,
복원한 두 치수는 각각 기준 치수의 2% 이내여야 합니다. 기존 패널 시험은 패널 세분과
독립 정전 불변식도 확인합니다.

별도 시험은 변수 단위 변경을 포함한 결합 affine 목적, 끝점·초기점 해, 불가능·퇴화
목적, 실제 차분 시도 예산, factory/장해석 실패, 신호 동일성, 동결 세분과 세분 실패를
검사합니다. 균일 유전체는 양쪽 모드가 진공 값/sqrt(Re(eps_r))와 1e-10 이내로
일치해야 합니다. 명시 사례의 수락 기준이며 일반 오차 추정, 실측 기판 검증,
브라우저 동등성 또는 Windows 수락이 아닙니다.

[단일 변수 역산](design.md) · [재료](material_impedance.md) ·
[English](../../../../../packages/sipi/pair_design.md)

[이름 있는 템플릿 목표 저장](pair_design_document.md)은 두 목표·순서 있는 변수·제약·고정 재료를 엄격한 JSON에 보존합니다.
