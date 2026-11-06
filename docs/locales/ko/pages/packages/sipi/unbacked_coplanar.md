# 후면 접지면이 없는 coplanar 단면

`unbacked_coplanar`와 `coupled_unbacked_coplanar`는 두 유한 coplanar 접지 사이에
표면 신호선 하나 또는 두 개를 둡니다. 유한 두께 기판 위아래에 공기가 있으며
외곽은 모두 open(절연)입니다. 접지 trace 둘만 전기적 기준을 정의합니다.
기존 CrossSection 솔버와 JSON 계약을 재사용합니다.

```python
from sipi import coupled_unbacked_coplanar, CrossSectionDocument
section = coupled_unbacked_coplanar(
    width=.5e-3, gap=.3e-3, ground_gap=.2e-3, ground_width=1e-3,
    substrate_height=.5e-3, eps_r=4, thickness=35e-6, top_width=.4e-3,
    tan_delta=.01, lower_air_height=6e-3, air_height=6e-3, box_width=12e-3,
)
saved = CrossSectionDocument(section).dumps()
restored = CrossSectionDocument.loads(saved)
```

길이는 m입니다. 단일선 gap은 신호선–접지, 차동쌍 gap은 신호선 사이, ground_gap은
차동쌍 바깥쪽 신호선–접지 간격입니다. 신호선 바닥 가장자리가 기준이며 중앙 접지는
없습니다. 접지는 신호선과 두께가 같은 직사각형이고 신호선만 테이퍼를 지원합니다.
ground_width는 실제 유한 치수이며 외곽 설정이나 무한 접지 근사가 아닙니다.

층 이름은 lower_air·substrate·air입니다. 금속 바닥은 lower_air_height+substrate_height,
아래 공기 기본값은 기판 높이 10배, 위 공기 기본값은 기판 높이 10배+도체 두께입니다.
위 공기는 기판 표면부터 시작하므로 구리 위 여유가 필요합니다. 양쪽 공기·상자 폭은
별도 수렴이 필요한 수치 절단 매개변수이며 제조 치수가 아닙니다. 기판은 상자 전체
폭을 차지하며 유한 보드 측면이나 3차원 끝단을 모델링하지 않습니다.

두 이름 모두 ImpedanceStudyDocument와 ImpedanceDesignDocument에서 사용하며
단일선 z0·차동쌍 z_diff입니다. 네 샘플러는 실패를 보존합니다. 고정 피치는 신호선
중심을 고정하고 gap=pitch−width를 유도하며 접지는 각 행의 ground_gap을 유지하도록
움직입니다. 잘못된 유계 모서리는 거부하고 잘못된 정규 표본은 실패 행으로 남깁니다.
이전 판독기는 새 이름을 거부합니다. 버전과 미출시 빌드의 커밋·wheel 해시를 기록하세요.

## 독립 기준과 수락 조건

test_unbacked_coplanar.py는 두께 0·진공 도체에 자유공간 −log Green 함수의 패널
적분을 사용합니다. 총 전하 0을 강제하고 원거리 공통 전위를 미지수로 풀며 멀리
떨어진 경계를 접지하지 않습니다. 패널 해석 적분을 SciPy 수치 적분으로 확인하고
상호성·전하 중성·전위 기준/스케일 불변·80→160 패널 모드 변화 <=0.3%를 요구합니다.

신호선 [−a,a], 접지 ±[b,d]의 두 번째 기준은
`1/sqrt((z²−a²)(z²−b²)(z²−d²))`에 비례하는 복소 필드입니다. 신호선 전하와 슬롯
전위차 적분에서 `Z=K(1−k²)/(4 eps0 c0 K(k²))`,
`k=(a/b)*sqrt((d²−b²)/(d²−a²))`를 얻습니다. K 인수는 scipy.special.ellipk와 같은
타원적분 parameter입니다. 끝점 특이성을 치환한 수치 적분과 상대 <=1e-12,
160 패널과 <=0.1%를 요구합니다. 별도 큰 접지 패널은 무한 접지 극한과 1% 이내이며
무한 접지 식을 유한 접지 FEM의 수락 기준으로 대체하지 않습니다.

진공 세분 모드 오차 <=2% 및 세분 시 감소, 상자·양 공기 2배에서 변화 <=1%를
요구합니다. 유한 테이퍼 구리·eps=4 기판은 같은 메시의 scikit-fem 12.0.2 복소 P1
에너지 행렬과 상대 <=1e-9, 별도 모드 메시 변화 <=0.5%·외곽 변화 <=1%입니다.
같은 메시 일치만으로 수렴을 입증하지 않습니다. 정확 재료 면적·open 경계·JSON·
네 샘플러·고정 피치·잘못된 표본도 검사합니다. 독립 자유공간 목표의 저장형 선폭
역산은 폭 오차 <=4%, 요청·세분 메시 잔차 모두 <=1Ω입니다.

특정 형상의 수치 검증이며 실측 정확도·복사·3D 귀환 전류 전이·비아/stub 검증이
아닙니다. 기존 재료·메시·준TEM 한계는 유지합니다.

[후면 접지 차동 단면](coupled_coplanar.md) · [공차](study.md) · [역산](design.md)
