# CHANGELOG v1.1

## 수정한 구조 문제

- v1.0은 README에서 `recommendations[recommendation_id]` 조회를 안내했지만 실제 `recommendations`는 배열이었습니다.
- v1.1은 `recommendations`를 ID 키 기반 객체로 변환하고 출력 순서는 `recommendation_order`로 별도 보존합니다.
- 기존 `match` 필드는 `search_metadata`로 이름을 변경하여 런타임 규칙과 혼동되지 않게 했습니다.

## 수정한 규칙 문제

- v1.0: 권고안 23개 중 규칙으로 도달 가능한 권고안 13개, 미도달 10개
- v1.1: 권고안 23개 모두 활성 규칙으로 도달 가능
- 추가된 범주: FTP, legacy SNMP, PLC Write, mDNS, DHCPv6, SMB 공유/Named Pipe, 원격관리, 인바운드 서비스, Highly Connected Asset, 과다 TLS 연결
- `risk_tags_any`를 추가하여 네트워크 행위형 Finding을 이름 문자열에만 의존하지 않게 했습니다.

## 오매칭 방지

다음 일반 Finding은 단독으로 특정 권고안에 매칭하지 않습니다.

- `UDP 검토 후보`
- `HTTP 검토 후보`
- `SSL 검토 후보`
- `Attempt 상태 통신 후보`

이 값들은 프로토콜·포트·방향 또는 위험 태그가 추가로 충족될 때만 구체 규칙으로 처리해야 합니다.

## 검증 결과

`python validate_catalog.py` 기준:

- recommendation schema 정상
- recommendation ID 중복 없음
- rule ID 중복 없음
- priority 내림차순 정상
- dangling recommendation ID 없음
- unreachable recommendation 없음
- 대표 테스트 전체 통과
