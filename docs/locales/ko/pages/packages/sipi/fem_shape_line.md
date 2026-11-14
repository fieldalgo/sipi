# FEM 형상 에너지 전송선 저장

`FEMShapeTransmissionLineDocument`는 검산된 진공 FEM 형상 에너지 전류와
전체 경계별 표면 금속을 명시적으로 선택합니다. 스키마는
`sipi.fem-shape-transmission-line/1`이며 기존 저장 선로 방식은 바뀌지 않습니다.

최상위 키는 `schema`, `cross_section`, `frequency_hz`, `materials`, `conductors`,
`reference`, `ground_thickness_m`, `length_m`, `reference_ohms`의 9개입니다.
길이는 m, 주파수는 Hz입니다. `cross_section`은 기존 버전 있는 기하와 선택적인
메시 옵션을 유지합니다. 신호별 금속과 하나의 공통 reference 금속은 기존
transmission-line/7의 벌크·거칠기 또는 명시적인 바깥쪽부터의 코팅 기록을
사용합니다. 개별 면이나 서로 다른 접지 재료는 이 스키마에서 받지 않습니다.
신호는 1~4개이며 `ground`라는 신호 이름은 공유 정전용량 API의 예약어입니다.

```python
from sipi import CrossSectionDocument, FEMShapeTransmissionLineDocument
from sipi.templates import coupled_stripline

def metal(sigma):
    return dict(conductivity=sigma, relative_permeability=1.,
                roughness={'kind': 'smooth'})

section = coupled_stripline(width=.0004, gap=.0003, plane_spacing=.002,
                            thickness=.00005, eps_r=4., box_width=.008)
document = FEMShapeTransmissionLineDocument(
    CrossSectionDocument(section, mesh=dict(edge_size=2.5e-6,
        far_size=.0001, grade=.05)),
    [2e9, 5e9], materials={},
    conductors={'positive': metal(58e6), 'negative': metal(35e6)},
    reference=metal(58e6), ground_thickness=35e-6, length=.02)
assert FEMShapeTransmissionLineDocument.loads(document.dumps()).dumps() == document.dumps()
```

`document.analyze()`를 호출하면 계산합니다. 정규화 과정은 메시 생성이나 전계
풀이 없이 재료·코어·표피 깊이를 검사합니다. 실제 계산에서는 하나의 메시를
진공 전류 기저와 주파수별 유전체 C/G에 공유합니다. 동일 C0로 외부 L을 구하고,
경계 금속 법칙으로 R과 내부 L을 구한 다음 기존 RLGC 네트워크로 유한 길이
S 행렬을 계산합니다. 원 전류 잔차, 형상 미분, 연장, 상호성 및 에너지 검사는
필수로 유지합니다. 공통 실행은 분석 전에 주파수 예산을 검사합니다.

결과는 기존 선로 결과의 R/L/G/C, 네트워크와 전파 진단을 제공합니다.
`current_record()`에 원 기울기 에너지·전류, 두 기하 연장, 두 유한차분 이동 크기,
완료된 모든 진공 정전용량 표본을 보존합니다. 메시 설명에는 절점·삼각형 개수와
절점, 삼각형, 순서 있는 신호·접지 인덱스의 SHA-256 해시를 기록합니다.
float64/int64 little-endian 배열을 명시적으로 사용합니다. 해시는 실제 메시를
식별하지만 좌표 자체를 담거나 다른 플랫폼에서의 재현성을 보장하지는 않습니다.

공통 `normalize_saved`, `execute_saved`, `SavedExecutionRequest`, 실행 기록,
프로젝트 및 CLI 실행에서 새 문서를 받습니다. characteristic/mode 진단은 기존
거부 조건을 유지하며 성공적으로 추출한 선로 결과를 지우지 않습니다. 기존 실행
기록 버전의 기본값과 호스트가 선언하는 산출물 정보의 의미도 바뀌지 않습니다.

`FEMShapeLineError`는 실패 단계와 정확히 정규화된 입력을 기록합니다. 후속 단계
실패에는 완료된 전류를 보존하고, typed current 실패에는 가능한 원 기울기 결과,
완료 정전용량, 실패 요청 주소 및 부분 에너지 관측을 보존합니다. 실패 자료의
비유한 값은 `nan`, `+inf`, `-inf` 문자열로 명시하며 수락된 수치 결과로 취급하지
않습니다. 실패 실행의 result는 null이고 오류 기록은 지원하는 두 실행 기록 버전에
모두 보존할 수 있습니다. 중단 예외는 그대로 전파합니다.

완료는 추출과 수치 일관성 검사가 끝났다는 뜻입니다. 메시·외곽 수렴, 작은 상호항
또는 실측 정확도를 인증하지 않습니다. 거친 메시에서 비물리적 에너지 고유값이
나오면 거부할 수 있으며, 세분과 독립 기준 대조가 계속 필요합니다. 이 문서는
해당 방식의 브라우저 Worker 또는 Windows 실행 파일 검증 완료를 뜻하지 않습니다.
