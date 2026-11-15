# 여러 주파수에서 같은 양면 접지 제조 표본 계산하기

[English](../../../../../packages/sipi/two_ground_sampled_pair_study.md)

`TwoGroundSampledForwardPairStudyDocument`는
`sipi.two-ground-sampled-forward-pair-study/1` 입력을 저장합니다. 같은 기하·재료
표본을 증가하는 양의 주파수 2~64개에서 계산합니다. 한 표본 안에서는 한 번의
전류 추출과 유전체 메시를 전체 주파수에 공유합니다. 주파수별 결과는 Ic=0과
Id=0의 별도 순방향 여기에서 얻은 Re(Zdd), Re(Zcc)입니다. 독립 전파 모드의
임피던스를 뜻하지 않습니다.

다음 예제는 폭 .43/.44 mm인 두 표본과 2·3.5·5 GHz의 입력을 장 계산 없이
준비합니다.

```python
from sipi.study import ImpedanceStudyDocument
from sipi.dielectric import DebyeDielectric
from sipi.two_ground_sampled_pair_study import TwoGroundSampledForwardPairStudyDocument

source = ImpedanceStudyDocument('coupled_stripline',
    dict(width=.00043, gap=.00028, plane_spacing=.002, eps_r=4.,
         thickness=.00005, box_width=.008, trace_height=.000975),
    quantity='z_diff_forward', frequency=2e9,
    materials={'dielectric': DebyeDielectric(3., (.7,), (1e9,))},
    sampling=dict(kind='corners', variables=[
        dict(name='width', lower=.00043, upper=.00044)]),
    mesh=dict(edge_size=5e-6, far_size=.0001, grade=.05))
metal = dict(conductivity=58e6, relative_permeability=1., roughness=dict(kind='smooth'))
study = TwoGroundSampledForwardPairStudyDocument(source,
    frequencies=[2e9, 3.5e9, 5e9],
    conductors=dict(positive=metal, negative=metal),
    reference=dict(kind='surfaces', bottom=metal, top=metal, sides=None, conductors={}),
    ground_thickness=35e-6, panels_per_edge=64, ground_modes=128,
    interpolation_degree=12)
assert TwoGroundSampledForwardPairStudyDocument.loads(study.dumps()).dumps() == study.dumps()
assert len(study.samples()) == 2
```

 `study.analyze(max_evaluations=2)` 또는 공통 `execute_saved` API로
실행합니다. 길이는 m, 주파수는 Hz, 결과는 Ω입니다. 원 연구의 주파수는 요청한
첫 주파수와 같아야 합니다. study/3·4의 기하·재료 값 표본, 고정 기하 제약과
상관 계약을 유지합니다. 표본의 재료 모델은 첫 주파수 값으로 고정하지 않고
전체 주파수에서 분산을 평가합니다. 도체 전체 표면과 위·아래 접지면의 금속
법칙은 표본 사이에서 고정됩니다.

평가 예산은 주파수 수가 아니라 실패를 포함한 제조 표본 행 수입니다.
2~10000을 허용하며 부족한 예산은 풀이 전에 거부합니다. 주파수 개수 상한도
별도로 적용합니다. 자동 재시도·세분은 없습니다. 입력 정규화는 장 계산 없이
명목 입력의 전체 주파수를 검사하며 모든 표본의 수치 성공을 보장하지 않습니다.
중복·누락·알 수 없는 필드와 비유한 수는 거부합니다.

한 주파수라도 실패하면 그 표본 전체를 미해결 행으로 남깁니다. 유효하지 않거나
중복·상관된 표본도 원래 순서대로 보존합니다. 해석된 재료·정확한 선로 입력·
실패 단계와 구체 원인, 이미 얻은 전류·메시 근거를 결과에 남깁니다. 일반 오류
뒤에는 다음 표본을 진행하고 중단 요청은 전파합니다. 실패가 하나라도 있으면
모든 요약 통계를 제공하지 않습니다. 저장 실행은 `incomplete`이며 요청·기록·
프로젝트를 다시 열어도 풀이하지 않습니다. 통계는 생산 수율·신뢰구간이나 연속
주파수 대역 보장이 아닙니다. 기존 단일 주파수 입력과 계산법은 유지합니다.

등록한 물리 검사는 위 두 폭 표본의 균일 Debye 재료와 기존 코팅 도체·접지
fixture를 사용합니다. 전체 주파수 계산을 각 주파수의 별도 풀이, 복소 행렬의
독립 순방향 임피던스 및 균일 재료 불변식과 비교합니다. 첫 표본의 별도 유한
해상도 검사는 유전체 메시를 절반으로, 패널을 64→128, 접지 모드를 128→256으로
늘립니다. 외곽 폭은 8→16→32 mm, 접지 모드는 512·1024로 변경합니다.
R·내부/외부 L·C·G·C0의 모든 행렬 항에서 상대 0.01·절대 0 기준을 유지합니다.
이 비교의 통과는 해당 입력의 유한 일치 근거이며 실측 정확도·임의 주파수 수렴·
모든 제조 단면의 수락을 뜻하지 않습니다. 이 균일 재료는 기존 C0 해석적 비례식을
사용하므로 유전체 메시만 바꾼 차이는 0입니다. 이를 비균일 유전체 메시 수렴의
독립 근거로 해석하지 않습니다.

`dependencies.json`의 명시 공유 개발 기능이 필요하며 대체 전류 계산법으로
우회하지 않습니다. Linux 소스·설치본, 브라우저 Worker, macOS·Windows 검증은
각각 별개입니다.
