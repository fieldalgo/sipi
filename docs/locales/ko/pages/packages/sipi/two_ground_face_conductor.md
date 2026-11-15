# 두 접지면의 면별 도체 손실

[English](../../../../../packages/sipi/two_ground_face_conductor.md)

`two_ground_conductor_loss_by_face`는 각 도체의 네 직선 면에 기존 국소 금속
표면 법칙을 적용하고 아래·위 동박을 분리한다. 일반 전류 풀이는 정확히
지정한 외부 `galerkin` 패키지가 담당하며 금속·거칠기·네트워크 법칙은
SIPI에 둔다. [전체 표면 API](two_ground_conductor.md)도 별도로 유지한다.

```python
from sipi import CrossSection, Layer, Trace
from sipi.boundary_conductor import SurfaceMetal
from sipi.face_conductor import TraceFaceMetals, ReferenceSurfaceMetals
from sipi.roughness import CausalHuray
from sipi.two_ground_face_conductor import two_ground_conductor_loss_by_face

smooth = SurfaceMetal(58e6)
rough = SurfaceMetal(58e6, roughness=CausalHuray((0.2e-6,), (2.0,)))
section = CrossSection(
    [Layer("substrate", 0.002, 4.0)],
    [Trace("signal", x=0.0, width=0.0006, y=0.0007,
           thickness=0.00005, top_width=0.00055)],
    width=0.008, top="ground",
)
loss = two_ground_conductor_loss_by_face(
    section, [1e9, 3e9, 10e9],
    conductors={"signal": TraceFaceMetals(rough, smooth, smooth, smooth)},
    reference=ReferenceSurfaceMetals(smooth, rough, None, {}),
    ground_thickness=35e-6, panels_per_edge=64, interpolation_degree=16,
)
```

## 계약

좌표는 미터, 주파수는 헤르츠이다. 위·아래 기준면은 접지, 측면은 개방이어야
한다. 접지 도체를 포함한 1–16개 도체는 모두 유한 사각형·사다리꼴 `Trace`
객체여야 한다. 일반 다각형은 전체 표면 API에서 지원하며, 새 면별 API에서는
아래·위·왼쪽·오른쪽을 자동으로 추정하지 않는다. 공유 입력 허용 조건과
전체 2048 패널 예산은 유지한다.

`conductors`는 정확한 신호 이름들을 `TraceFaceMetals`로 연결한다. 네 법칙은
전체 단면 좌표의 아래·위·왼쪽·오른쪽 순서이고 사다리꼴 측면은 경사진 면을
따른다. `ReferenceSurfaceMetals`는 두 동박 법칙, 측면 `None`, 정확한 접지
도체 이름을 요구한다. 접지 도체의 `SurfaceMetal`은 네 면에 동일하게
확장하고 `TraceFaceMetals`는 별도 법칙을 유지한다. `ground_thickness`는
두 동박의 표피 깊이 검사에 공통으로 쓰는 보수적인 두께이다.

기존 주파수·코팅·잔여 코어·표피 깊이·거칠기 입력 검사는 장을 풀기 전에
수행한다. 표피 깊이는 최소 잔여 도체 치수의 1/5 이하여야 한다. 공유 모서리
기능이 없으면 `RuntimeError`이며 다른 솔버로 대체하지 않는다.

## 결과와 물리 범위

기존 `FaceConductorLoss` 형식으로 주파수별 저항·내부 인덕턴스·표면
임피던스·거칠기 인자·표피 깊이를 보존한다. `loss.factors`는
`TwoGroundFaceCurrentFactors`이고 `loss.factors.base`는 기존 전체 표면의
`TwoGroundCurrentFactors`와 진단을 보존한다. 면 순서는 다음과 같다.

1. 신호 순서대로 각 신호의 네 면.
2. 아래·위 기준면.
3. 접지 도체 순서대로 각 접지 도체의 네 면.

배열은 스냅샷이며 면 계수와 기반 계수는 불변이다. 부호 전류와 에너지
Gram은 별도로 보존한다. 접지 도체는 원래 전체 커패시턴스 계에서 전위가
0이며, 부유 도체로 취급해 Schur 보완으로 제거하지 않는다. 실제 끝점과
소유 도체가 각 면과 유일하게 대응해야 한다. 네 면의 합은 대각 분모 하한
없이 원소별 상대 `1e-10`에서 원래 경계와 일치해야 한다. 부호 합은 절대
`1e-10`이며 유한값·상호성·크기로 정규화한 양의 준정부호도 검사한다.

공유 풀이 한 번에서 전체 및 모서리 계수를 얻는다. 진공 전류 분포에는
유전체 메타데이터가 들어가지 않는다. 균일한 외부 자기 영역의 1차 표면
섭동 모델이며, 적층 금속은 기존 국소 평면 코팅 법칙을 유지한다. 코팅
모서리·유한 금속 확산·동박 실측 보정은 풀지 않는다. 한 면의 법칙을 바꾸면
그 면의 가중 기여만 변한다. 동일한 법칙은 원래 분할 수치 검사 범위에서
기존 전체 표면 손실을 재현한다. 기존 `network`에는 같은 기하·이름의
물리 커패시턴스·컨덕턴스를 독립적으로 공급해야 한다.

## 검증과 한계

필요한 면별 양에 맞춰 패널·보간 차수·접지 모드·유한 외곽을 세분해야 한다.
내부 일관성은 정확도 한도가 아니다. 사전 등록한 사다리꼴 두 신호·접지
가드 사례에서 차수14는 공유 행렬 검사를 통과했지만 엄격한 `1e-10` 면별
상하 반사 비교는 약 `2e-10`으로 실패했다. 차수16을 별도로 모서리당
16·32·64 패널에서 검사했으며 원실패를 보존했다. API 기본값은 자동으로
바꾸지 않았고, 명시적 차수16 예제가 다른 입력을 자동 인증하지 않는다.

시험은 동일 금속의 전체 법칙 재현·독립 매끈한 표면 전력 가중치·코팅과
거칠기의 면별 적용·0전위 접지 축소·물리 변환·수동 네트워크·풀이 전 거부를
다룬다. 물리 수락에는 독립 패널·메시·유한 외곽의 면별 검증이 추가로
필요하다. 전체 경계의 일치만으로 대체할 수 없다. 이 직접 Python API는
기존 저장 JSON·실행 기본값·브라우저 폼을 변경하지 않는다.

## 선택한 독립 면별·손실 검사

등록한 편심 단일·비대칭 쌍·근접 쌍 직사각 단면은 64/128/256 패널,
독립 P2 체적 에너지 메시 두 단계, 내부 확장 두 종류와 8/16/32 mm 유한
외곽 비교를 보존합니다. 면 원소별 독립 대조는 독립값 자체를 분모로
상대 2%, 정전용량은 0.05%이며 분모 하한은 없습니다. 마지막 패널·메시
변화와 연속 두 외곽 변화는 원소별 1%입니다. 이 직사각 사례만으로 임의
테이퍼 단면을 자동으로 인증하지 않습니다.

독립 평활 금속 손실 검사는 1·3·10 GHz를 씁니다. 첫 신호의 아래/위/왼쪽/
오른쪽 전도도는 58/35/21/45 MS/m, 둘째는 역순, 두 접지박은 45 MS/m이며
상대 투자율은 모두 1입니다. 독립 제곱근 표면 임피던스로 저장 P2 면별·
합산 접지 에너지를 가중합니다. 저항·내부 인덕턴스의 각 원소에도 독립
대조 2%, 세분 변화 1%를 적용합니다. 저장 참조 재생은 독립 솔버 재실행이나
실측 재료 보정이 아닙니다. 기존 전체 경계 기준과 원래 해상도 미달 관측은
변경하지 않습니다.
