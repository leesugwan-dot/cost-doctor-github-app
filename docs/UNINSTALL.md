# 비활성화 및 제거

현재 후보는 GitHub App 설치형이며 저장소 workflow 파일을 추가하지 않습니다.

1. GitHub App 설치 설정에서 test repository 접근을 제거하거나 App을 uninstall합니다.
2. 새 `pull_request` webhook이 오지 않는지 확인합니다.
3. 운영자는 worker/scheduler를 정상 중지하고 처리 중 lease가 없는지 확인합니다.
4. secret 파일과 ledger는 확정된 보존·삭제 정책에 따라 별도로 처리합니다.

이 문서는 secret·ledger 삭제를 승인하지 않습니다. 실제 로그인·권한 취소도 사용자가 승인합니다.

현재 후보는 Required Status Check나 Repository Ruleset을 자동 설정하지 않습니다. 운영자가 `Cost Doctor`를 required check로 별도 연결했다면 App 제거와 함께 해당 규칙도 검토해야 합니다. App만 제거하고 required check를 남기면 merge가 대기할 수 있습니다.

내부 격리 E2E의 임시 설치·정리 round-trip은 `PASS`입니다. 외부 사용자의 uninstall 재현은 아직 `NOT_TESTED`입니다.
