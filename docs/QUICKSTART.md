# Quick Start

상태: `PUBLIC_PILOT_CANDIDATE / NOT_5_MINUTE_VALIDATED / TEMPORARY_ISOLATED_LIVE_E2E_PASS`

현재 실제 설치 구조와 최초 검증 순서를 설명합니다. hosted endpoint와 내부 격리 GitHub E2E는 검증됐지만 외부 사용자 설치 허용은 최종 공개 Gate 전입니다. 외부 clean repository에서 시간을 측정해 성공하기 전에는 ‘5분 설치’라고 부르지 않습니다.

## 기본 경로

```text
GitHub App → 비공개 HTTPS webhook → 단일 호스트 worker·공유 SQLite → GitHub Check
```

GitHub Action, Marketplace action, Docker image, 데스크톱 설치파일은 제공하지 않습니다.

## 5분 설치 목표 체크리스트

이 목록은 시간 측정 전 가이드이며 `5분 설치 검증 완료` 주장이 아닙니다.

1. [설치 페이지](https://github.com/apps/cost-doctor-staging-pilot-r2)에서 테스트 저장소 하나만 선택합니다.
2. Pull requests 읽기, Contents 읽기, Checks 쓰기 외 권한이 없는지 확인합니다.
3. 무해한 README 변경 PR을 엽니다.
4. `Cost Doctor` Check의 생성과 exact head SHA 일치를 확인합니다.
5. 검증이 끝나면 [제거 절차](UNINSTALL.md)로 접근을 회수합니다.

## 0. 요구사항

- Python 3.12 호환 환경
- 승인된 HTTPS webhook endpoint
- 비공개 작업 디렉터리와 단일 호스트 scheduler
- GitHub App·대상 저장소 관리자 권한
- secret을 제한된 파일로 보관하는 안전한 저장소

공개 문서 패키지에는 비공개 backend가 없습니다. 운영 패키지와 hosted endpoint가 없으면 여기서 멈춥니다.

## 1. App 권한 초안

| 설정 | 값 |
| --- | --- |
| Pull requests | Read-only |
| Contents | Read-only |
| Checks | Read and write |
| Event | Pull request |
| User authorization | 사용하지 않음 |

처음에는 test repository 하나만 선택합니다. App은 이미 등록·설치 실증을 마쳤으며, 외부 사용자는 공개 허용 이후 자신의 저장소 범위를 직접 승인합니다.

## 2. 비공개 runtime 설정

| 이름 | 필수 | 의미 |
| --- | --- | --- |
| `COST_DOCTOR_PRIVATE_WORK_ROOT` | 예 | 비공개 작업 루트 |
| `COST_DOCTOR_LEDGER_PATH` | 예 | 루트 바로 아래 SQLite 장부 |
| `GITHUB_ALLOWED_REPOSITORY_IDS` | 예 | 허용할 숫자 repository ID |
| `GITHUB_APP_ID` | 예 | App ID |
| `GITHUB_APP_CLIENT_ID` | 예 | App JWT issuer binding |
| `GITHUB_WEBHOOK_SECRET_FILE` | 예 | webhook secret 파일 참조 |
| `GITHUB_APP_PRIVATE_KEY_FILE` | 예 | private key 파일 참조 |
| `COST_TELEMETRY_TRUST_STORE_FILE` | 아니오 | 서명 telemetry trust-store 참조 |

- work root와 secret 경로에 link/junction/reparse point를 쓰지 않습니다.
- ledger는 work root 바로 아래의 `.sqlite`, `.sqlite3`, `.db` 파일이어야 합니다.
- secret·private key·token 값을 문서, 로그, Evidence, 채팅에 복사하지 않습니다.

## 3. 무네트워크 preflight

비공개 운영 패키지 루트에서 실행합니다.

```powershell
python -c "import private_entry; print('IMPORT_OK_NO_NETWORK')"
python -m unittest discover -s tests -v
```

현재 회귀 기준은 `55/55 PASS`입니다. 이 결과는 실제 GitHub 설치나 live PR 성공을 증명하지 않습니다.

## 4. 실제 첫 PR

App, HTTPS endpoint, secret 파일, repository 설치가 준비된 뒤에만 수행합니다.

1. 안전한 test repository 하나만 선택합니다.
2. App 범위를 그 repository로 제한합니다.
3. endpoint와 worker를 시작합니다.
4. README 오타 수정처럼 무해한 PR을 만듭니다.
5. `Cost Doctor` Check를 확인합니다.
6. 실제 PR head SHA와 처리 SHA가 같은지 확인합니다.
7. Check readback, 중복 delivery, worker restart를 검증합니다.
8. 끝나면 App 접근과 별도 ruleset을 원복합니다.

현재 내부 격리 actual-run 결과는 `PASS`입니다. 외부 사용자 설치 및 5분 내 완료는 `NOT_TESTED`입니다.

## 5. 결과 읽기

- `success`: 서명·입력 binding·측정 계약까지 검증된 telemetry가 관측됨
- `neutral`: telemetry가 없거나 조건이 부족해 절감액이 `UNKNOWN`
- 미생성/오류: webhook, 허용목록, secret 참조, worker, GitHub API readback 점검

현재 구현은 merge를 자동 차단하지 않습니다.

## 완료 기준

clean repository에서 문서만 보고 최소권한 설치, 첫 PR, 정확한 commit 분석, Check readback, 제거, secret·원문 노출 0을 실제 재현해야 Quick Start live 검증으로 올립니다. 이 전 과정을 5분 이내에 반복 성공한 뒤에만 ‘5분 설치’를 표시합니다.
