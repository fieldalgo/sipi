# 다신호 상수 RLGC 혼합 종단

[English](../../../../../packages/sipi/multiconductor_boundary_startup.md) | **한국어**

`multiconductor_boundary_ladder_response`는 이상/저항 전압원과 개방/단락/
저항 부하를 쓰는 별도3·4신호 상수 유한 회로입니다. 기존
[양저항 모델](multiconductor_startup.md)과 [두 신호 혼합 종단](coupled_boundary_startup.md)은 유지합니다.

```python
import numpy as np
from sipi import multiconductor_boundary_ladder_response
t=np.linspace(0.,4e-9,41)
drive=np.minimum(t[:,None]/1e-9,1.)*np.array([1.,-.4,.2])
r=multiconductor_boundary_ladder_response(t,drive,signals=3,
    R=np.array([[20.,-20.,0.],[-20.,20.,0.],[0.,0.,0.]]),
    L=np.array([[450.,60.,0.],[60.,480.,60.],[0.,60.,510.]])*1e-9,
    G=np.array([[0.,0.,0.],[0.,.002,.002],[0.,.002,.002]]),
    C=np.array([[210.,-20.,0.],[-20.,220.,-20.],[0.,-20.,230.]])*1e-12,
    length=.1,cells=8,source_resistance=[0.,25.,0.],
    load_resistance=[None,0.,75.])
assert r.voltage.shape==r.current.shape==(41,6)
assert r.node_voltage.shape==(41,9,3) and r.segment_current.shape==(41,8,3)
np.testing.assert_array_equal(r.voltage[:,[0,2]],drive[:,[0,2]])
assert not np.any(r.current[:,3]) and not np.any(r.voltage[:,4])
assert r.current[0,0]!=0.  # A prescribed ramp includes endpoint displacement current.
```

명시 signals3/4·cells1–128·0에서 시작하는 균일 시간2–10000행과 첫 행0인
PWL 전압(times,signals)을 받습니다. 상수 SI R[ohm/m]·G[S/m]는 정확 대칭
PSD, L[H/m]·C[F/m]는 정확 대칭 SPD이고 정규화 고유값 비율>1e-12입니다.
R/G의0·특이 행렬을 허용하며 음의 정규화 고유값을 clipping·대칭 보정·
숨은 rank 기준으로 복구하지 않습니다. 부동소수 고유값 부호 모호성으로
수학적 PSD를 보수적으로 거부할 수 있습니다.

소스 저항은 유한>=0이며0은 지정한 이상 전압입니다. 부하 각 항은
None=개방,0=단락,유한>0=저항입니다. 벡터에 정확히 signals개가 필요하고
스칼라 broadcast나 소스None alias는 없습니다. 외부 리액티브 부하·전류원·
분산은 이 계약 밖입니다.

끝에 절반 가중치를 주는 pi 회로는 전체 상호 C/G를 유지합니다. mass 행렬의
고정 전압 좌표를 제거하고 자유 상태를 변환해 전압 도함수 forcing을 없앤 뒤
SciPy lsim을 실행합니다. 복원에는 knot에서 오른쪽 PWL 기울기·마지막0을
사용합니다. 이상/단락 단자 전류에는 구간 전류뿐 아니라 전체 끝점 변위·
병렬 전류가 포함됩니다. near N개 뒤 far N개 모두 선로 안으로 향합니다.
초기 저장 에너지0이어도 이상 소스의 초기 변위 전류는0이 아닐 수 있습니다.

```python
import json
np.testing.assert_allclose(r.energy_rate,
    r.line_power-r.series_loss-r.shunt_loss,rtol=1e-10,atol=1e-12)
np.testing.assert_allclose(r.source_power,
    r.source_resistor_loss+r.load_resistor_loss+r.line_power,rtol=1e-10,atol=1e-12)
assert max(r.power_balance_relative_error,r.total_power_balance_relative_error)<=1e-10
assert r.port_names==('near_0','near_1','near_2','far_0','far_1','far_2')
assert not r.current.flags.writeable
out=r.to_dict(include_states=True)
assert out['input']['source_resistance_ohm']==[0.,25.,0.]
assert out['input']['load_resistance_ohm']==[None,0.,75.]
json.dumps(out,allow_nan=False)
```

저장 에너지와 수동 손실은 유한·비음수여야 하며 선로/소스 전력 수지에 각각
원래 상대1e-10 기준을 적용합니다. 출력은 분리된 읽기 전용 배열이며 원래
소스/부하·PSD 값을 보존합니다. 표현 불가능한 cell/source 범위와 전파
실패는 명시 오류입니다. 작은 저항으로 이상 종단을 대신하지 않습니다.

독립 기준은 원래 노드 전하 KCL을 직접 자유 전압·지정 전압 도함수·DOP853으로
풀고 입력 knot를 나눕니다. 후보의 변환 상태·mass 행렬·전파 계수를 재사용하지
않습니다.3·4신호 비가환 PSD/조건부 저장 ramp/pulse는 V1e-8/A1e-9 기준을
만족합니다.1cell ideal/short의 ramp RL·순수L 해석에는 상호 끝점 C 전류를
포함합니다. 모든1512종단 조합(3신호216·4신호1296)에서 경계와 전력을 확인하고
기존 양저항·Debye 강도0·대각 scalar·2+1/2+2 block 기준과도 대조합니다.

무손실 모드 수렴은 길이.1m·2ns ramp·12ns 관측·1201표본,Rs0/25ohm과
부하0/개방/100ohm의12조건입니다.32/64/128cell에서 오차가 감소하며 지정 전압이
정확한 경우는 예외입니다. 최종 기준은 V.02/A.0005 이하이고 실제 최댓값은
V.00646841224/A.000157794877입니다. 동일 PWL knot의601/1201/2401표본은 공통
시간 결과를 유지합니다. 명시1D 공간/표본 기준이며 임의 소스·field 추출·실측
정확도를 보장하지 않습니다.

기존144개 전체 상태 출력은 소스/설치본에서 exact이며 이전 수치 코드/시험은
그대로입니다. 별도 결과형은 저장·단자 파동 API에 자동 연결되지 않습니다.
90스키마·37템플릿을 유지하며 새 의존성·브라우저/데스크톱 업데이트·플랫폼
지원을 추가하지 않습니다. [개발 검증](../../../../../development.ko.md)을 참고하세요.


[명시 혼합 종단 저장 입력](multiconductor_boundary_startup_document.md)은 수치 모델을 바꾸지 않고 이상/개방/단락 값을 보존합니다. 단자 파동 수락은 별도입니다.
