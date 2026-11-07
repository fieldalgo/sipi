# 원형 개구의 국소 정전용량

`CircularAperture`는 원형 PEC 도체와 원형 접지 경계 사이의 균질 2차원 정전계를
계산합니다. 도체가 개구 중심에서 벗어난 경우도 지원합니다. 공유 Galerkin P1 솔버와
원고리 메시 연결 구조를 사용하며 새 솔버나 런타임 의존성을 추가하지 않습니다.

```python
from sipi import CircularAperture, ApertureDocument

section = CircularAperture(
    conductor_diameter=0.28e-3,
    aperture_diameter=0.80e-3,
    offset_x=0.10e-3, offset_y=-0.07e-3,
    eps_r=3.96, tan_delta=0.03,
)
document = ApertureDocument(section, mesh={
    "radial_divisions": 64, "angular_divisions": 256,
})
saved = document.dumps()
restored = ApertureDocument.loads(saved)
capacitance = restored.analyze()       # complex F/m, C - j*C_loss
print(capacitance.real, -capacitance.imag)
refined = section.capacitance(radial_divisions=128, angular_divisions=512)
print(abs(refined / capacitance - 1))
```

두 크기 입력은 모두 **미터 단위 지름**입니다. 반지름이나 완성 홀 치수로 자동 해석하지
않습니다. 접지 원의 중심은 `(0, 0)`이며 `offset_x`, `offset_y`는 내부 도체의 중심
좌표입니다. 내부 반지름 `a`, 외부 반지름 `b`, 중심 이동 거리 `e`에 대해 `a + e < b`여야
합니다. 유한 실수만 받으며 bool은 거부합니다. 상대 유전율은 양수, 손실 탄젠트는
음이 아니어야 합니다. 시간 규약은 `exp(+j*omega*t)`, 균질 재료는
`eps_r * (1 - j*tan_delta)`입니다.
균일 스칼라 재료 계수는 조화 전위장을 바꾸지 않으므로 진공에서 푼 C에 재료 계수를
곱합니다. 차원이 있는 셀 면적을 정상 유한수로 표현할 수 없거나 정전용량의 실수부가
비유한 값·0 이하인 경우 오류를 반환합니다.

출력은 국소 **단위 길이당** 정전용량입니다. 유한 패드·배럴의 총 정전용량이나
인덕턴스·임피던스·3차원 비아 전이 모델은 아닙니다. 평면 간격, 자기 귀환 경로,
주파수 분산, 거칠기, 도체 손실, 끝단 프린징을 추정하지 않습니다. 국소 C에 가정한 L을
결합하여 비아 임피던스를 만들지 않습니다. 높이를 곱하려면 별도의 균일 압출 근사가
필요합니다.

## 메시와 입력 저장

`mesh()`는 미터 단위 Galerkin 메시와 `inner`, `outer` 경계 절점 집합을 반환합니다.
`radial_divisions` 기본값은 32(2 이상 정수), `angular_divisions` 기본값은 128(16 이상
정수)입니다. 두 방향을 모두 세분해야 하며 기본값이 정확도를 보증하지는 않습니다.
외곽은 물리적인 접지 경계이므로 지름을 바꾸면 문제 자체가 바뀝니다. 열린 영역의
절단 경계를 멀리하는 외곽 수렴 시험과 구분합니다.

원은 내접 다각형으로 근사합니다. 메시 할당 전에 내부 원판 전체가 외곽 다각형의
내접원 안에 들어가야 합니다. 외곽 지름 `D`로 정규화했을 때
`0.5*cos(pi/angular_divisions) - a/D - e/D > 32*machine_epsilon`을 요구합니다.
보수적인 조건이므로 실제 원 사이에 간격이 있어도 거부할 수 있으며, 이 경우 각도
해상도를 높입니다. 찌그러져 면적이 사라지거나 뒤집힌 셀도 거부합니다. 거의 접촉한
경우, 매우 작은 도체, 극단적인 크기는 이 검사를 통과해도 추가 수렴 검증이 필요합니다.

`ApertureDocument`는 `sipi.circular-aperture/1`, `length_unit: "m"`, 기하 값 4개,
유전 특성과 확정된 메시 분할 수를 저장합니다. 입력은 복사하며 접근자도 복사본을
반환합니다. 모르는 필드·누락 필드·지원하지 않는 단위/스키마·중복 JSON 키·비유한 값을
거부합니다. 결과는 저장 입력에 포함하지 않습니다. 기존 단면·공차·설계 스키마와
템플릿 목록은 그대로이며, 이 별도 정전용량 입력을 임피던스 공차·목표 문서에 넣을
수는 없습니다.

## 독립 검증과 한계

편심 원의 해석해는 다음과 같습니다.

`C' = 2*pi*epsilon0*eps_r / acosh((b*b + a*a - e*e)/(2*a*b))`.

`e=0`이면 분모는 `log(b/a)`입니다. 시험은 `a=0.14 mm`, `b=0.40 mm`,
`e/(b-a)=0, 0.5, 0.8`에서 두 해상도를 세분합니다. 가장 고운 메시의 해석해 오차와
반경·각도 각각의 마지막 세분 변화에 0.2% 기준을 적용합니다. `(128, 512)`의 실제
해석해 오차는 각각 약 0.00199%, 0.00273%, 0.00575%였습니다. 모든 기하에 적용되는
보편적인 오차 상한은 아닙니다.

scikit-fem 12.0.2의 독립 복소 P1 조립으로 같은 다각형 메시의 C를 상대 `1e-9` 기준에서
대조합니다. 이는 조립 검증이며 기하 수렴의 대체물이 아닙니다. 균일 크기 변환, 강체
회전, 메시 대칭에 맞춘 회전·반사, 균질 복소 재료 배율, 잘못된 입력, 다각형 간격,
저장 입력 재생도 확인합니다. 실측이나 3차원 전이 정확도를 주장하지 않습니다.

[English](../../../../../packages/sipi/circular_aperture.md)
