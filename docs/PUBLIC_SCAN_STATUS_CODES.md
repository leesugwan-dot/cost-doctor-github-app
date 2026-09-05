# Public Scan 상태 코드

공개 진단 실패 시 원문 로그 대신 아래처럼 제한된 상태 코드를 표시합니다.

| 상태 코드 | 의미 | 사용자 행동 |
| --- | --- | --- |
| `URL_INVALID` | GitHub 저장소 주소 형식이 아님 | 공개 GitHub 저장소 주소를 다시 붙여넣기 |
| `FORM_FIELD_MISSING` | Issue Form 입력을 읽지 못함 | 새 진단 요청 만들기 |
| `FORM_CONFIRMATION_REQUIRED` | 공개 결과 고지 동의 없음 | 확인 후 새 요청 |
| `PUBLIC_REPO_REQUIRED` | private repository | 무료 공개 진단에서는 중단 |
| `REPOSITORY_DISABLED` | 비활성화 저장소 | 다른 활성 공개 저장소 사용 |
| `REPO_TOO_LARGE_FOR_PUBLIC_BETA` | 현재 베타 크기 한도 초과 | 공개 베타 범위 밖 |
| `DEFAULT_BRANCH_MISSING` | 기본 브랜치 확인 불가 | 저장소 상태 확인 후 재시도 |
| `RATE_LIMITED` | 사용자별 24시간 한도 초과 | 한도 갱신 후 재시도 |
| `HEAD_MOVED_RETRY` | 준비 중 기본 브랜치가 변경됨 | 최신 상태로 새 요청 |
| `REPOSITORY_UNAVAILABLE` | GitHub에서 저장소를 읽을 수 없음 | 주소/공개 상태 확인 |
| `SCAN_TIMEOUT` | 안전 실행 시간 한도 초과 | 더 작은 저장소 또는 추후 재시도 |
| `SCAN_FAILED` | 정적 진단이 안전하게 끝나지 않음 | 새 요청 또는 Bug Report |
| `BOT_NOT_ALLOWED` | 자동화 계정 요청 | 일반 GitHub 사용자 계정으로 요청 |
| `INTERNAL_ERROR` | 예기치 않은 내부 오류 | Bug Report |

상태 코드는 문제 분류를 위한 최소 정보이며 private code나 secret을 담지 않습니다.

오류가 나도 대상 저장소에 쓰기 작업을 하지 않으므로 CostDoctor가 되돌릴 소스 변경은 없습니다.
