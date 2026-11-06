# 네트워크 연결과 알려진 fixture 제거

임의 포트 쌍의 명시적 연결과 이상적인 분기점은
[이름 지정 연결](named_connections.md)을 참고하세요.

`cascade_networks(left, right)`는 왼쪽 far 포트를 오른쪽 near 포트에 도체
순서대로 연결합니다. 입력은 single-ended `LineNetwork`이며 **near 전체 다음
far 전체** 순서의 2N포트입니다. 포트 이름으로 배선을 추정하지 않습니다.
주파수 배열과 연결 지점의 기준 임피던스는 정확히 같아야 합니다. 필요하면
`renormalized(...)`를 명시적으로 먼저 호출합니다.

```python
from sipi import cascade_networks, deembed_network

# left_fixture, device and right_fixture are known LineNetwork objects.
measured = cascade_networks(cascade_networks(left_fixture, device), right_fixture)
recovered = deembed_network(
    measured, left=left_fixture, right=right_fixture,
    port_names=device.port_names,
)
```

`deembed_network`는 왼쪽 fixture → 장치 → 오른쪽 fixture 순서에서 **이미
알려진** fixture 하나 또는 둘을 제거합니다. 오른쪽 fixture도 이 방향으로
입력하며 자동으로 뒤집지 않습니다. fixture 바깥 기준은 측정 네트워크 해당
끝과 같아야 합니다. 복원 기준은 fixture 안쪽 포트, fixture가 없는 쪽은
측정 끝에서 가져옵니다. fixture 추정이나 측정 표준을 통한 교정은 아닙니다.

기본 이름은 연결 시 남은 바깥 포트, 제거 시 노출된 안쪽 포트에서 가져옵니다.
중복되면 고유한 `port_names`를 지정합니다. 결과는 수정할 수 없는 배열 복사본이며
입력은 바뀌지 않습니다. mixed-mode의 d-near/d-far/c-near/c-far는 near/far
그룹 순서가 아니므로 거부합니다. 보간·자동 재정규화·수동성 보정·잡음 억제는
하지 않습니다.

## 수치 계약과 검증

연결은 scattering feedback을 직접 풉니다. 제거는
`[a_near; b_near] = T [b_far; a_far]`인 wave-chain 행렬에서 양쪽 선형계를
풉니다. S 자체를 역행렬로 만들지 않습니다. 기준의 두 배인 직렬 저항은 S가
특이행렬이지만 제거 가능합니다. 순방향 전송·wave-chain·복원 입사 블록은
유한하고 비특이이며 2-norm 조건수가 `1e12` 이하여야 합니다. 연결 feedback에도
같은 검사를 적용합니다. 이는 보수적 부동소수점 검사이며 **정확도 보증이
아닙니다**. 제한 이내에서도 감쇠와 측정 불확도가 유용한 정보를 없앨 수 있습니다.
큰 감쇠·특이 fixture는 거부하며 정규화로 숨기거나 사라진 정보를 복원하지 않습니다.

해석적 직렬 저항 합·이상적 through는 `1e-12`, 동일 RLGC 길이 합·알려진 장치
복원은 `1e-10` 기준입니다. 비상호·비가환 2/4포트는 scikit-rf 2.2.0 연결·
역변환과 S 최대 절대 차이 `1e-10`으로 대조합니다. 다른 실수 기준, 한쪽/양쪽
제거, 메타데이터 오류, 불투과 fixture·특이 feedback을 시험합니다.
`OPENPHYSICS_CROSSCHECK_DIR` 지정 시 독립 비교 기록을 남깁니다. 이는 네트워크
대수 검증이며 실제 fixture나 재료 정확도를 입증하지 않습니다.

[네트워크 모델](network.md) · [Touchstone 입력](touchstone.md)
