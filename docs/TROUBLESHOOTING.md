# 문제 해결

## Check가 없음

- App이 정확한 test repository에 설치됐는지 확인합니다.
- 숫자 repository ID가 허용목록에 있는지 확인합니다.
- 이벤트와 action이 지원 범위인지 확인합니다.
- HTTPS endpoint, webhook secret 파일, worker/scheduler를 확인합니다.
- webhook과 실제 PR head SHA가 다르면 새 이벤트를 기다립니다.

## Check가 `neutral`

오류로 단정하지 않습니다. 서명 telemetry, 입력 binding, 측정 계약, 신뢰키, 재계산 조건 중 하나라도 부족하면 `UNKNOWN` 유지가 정상입니다.

## fork PR 차단

fork 접근 Evidence가 없으면 fail-closed합니다. 권한을 넓혀 우회하지 않습니다.

## private 경로 오류

- link/junction/reparse point가 없는지 확인합니다.
- ledger가 work root 바로 아래인지 확인합니다.
- POSIX secret 파일이 group/other에 열려 있지 않은지 확인합니다.
- Windows ACL은 운영 계정에서 read-only로 확인합니다.

secret·private key를 오류 보고나 채팅에 붙이지 마세요.

## 중복 Check 우려

공유 장부와 lease/fence가 delivery를 식별하고 Check를 readback합니다. 장부를 임의 삭제하면 보호가 깨질 수 있습니다. 서로 다른 SQLite 장부를 쓰는 다중 호스트는 지원하지 않습니다.

공개 pilot 지원은 저장소의 GitHub Issues를 사용합니다. [지원 경계](../SUPPORT.md)와 [Pilot 보고 형식](PILOT_FEEDBACK.md)을 따르며 원문 로그·코드·비밀값을 올리지 않습니다.
