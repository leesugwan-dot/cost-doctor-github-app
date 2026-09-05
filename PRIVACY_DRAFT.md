# 개인정보 및 코드 처리 고지 초안

상태: `DRAFT_ONLY / NOT_LEGAL_CLEARANCE`

## 무료 공개 저장소 진단

- 사용자가 입력한 공개 GitHub 저장소 주소와 진단 결과는 이 저장소의 **공개 Issue**에 표시됩니다.
- 대상 프로젝트는 CostDoctor 운영자의 개인 PC로 보내지 않습니다.
- 대상 공개 저장소는 GitHub-hosted runner의 임시 작업공간에서만 제한적으로 checkout하고 정적 분석합니다.
- 대상 프로젝트 코드는 실행하지 않습니다.
- 원문 코드, 파일명, 로컬 경로, 비밀번호, 토큰, API Key, private key는 공개 결과 댓글에 포함하지 않습니다.
- 공개 결과의 검증 영수증은 대상 repository/head, CostDoctor 실행 버전, 정적 진단 요약과 실행 URL을 결속하되 원문 코드를 포함하지 않습니다.
- 민감정보 없는 `result.md`와 `receipt.json` Artifact는 현재 1일 보존으로 설정합니다.
- 별도 외부 telemetry 수집 서비스는 연결돼 있지 않습니다.
- GitHub Issue, Actions, Artifact 기록의 저장·보존·삭제는 GitHub의 서비스 정책과 저장소 설정의 적용을 받습니다.
- 정적 진단 결과는 실제 비용·토큰 절감, 품질 개선, 결함 존재를 증명하지 않습니다.

## 비공개 저장소 Self-Scan 준비 경로

- private repository는 공개 URL 진단에 입력하지 않습니다.
- 저장소 소유자가 자신의 private repository에 읽기 전용 CostDoctor workflow를 직접 설치해 GitHub Actions에서 Self-Scan할 수 있도록 별도 template을 준비합니다.
- 기본 workflow 권한은 `contents: read`입니다.
- checkout credential은 영속화하지 않습니다.
- 대상 프로젝트 코드를 실행하지 않으며 자동 commit, push, PR, merge를 하지 않습니다.
- private source를 CostDoctor 운영자의 개인 PC나 별도 분석 서버로 업로드하는 것을 기본 방식으로 사용하지 않습니다.
- private repository의 Actions 로그와 Artifact 접근은 해당 repository의 GitHub 권한을 따릅니다.
- 외부 사용자의 private repository actual-run은 아직 별도 검증이 필요합니다.

## 기존 GitHub App 후보

- PR의 정확한 head commit 압축본은 비공개 임시 작업공간에서만 읽습니다.
- 원문 코드, 파일명, 로컬 경로, 토큰, 비밀정보는 Check 결과에 포함하지 않습니다.
- 임시 압축 해제본은 정상 처리 경로에서 제거합니다.
- 저장되는 운영 장부는 delivery/work 식별자, commit SHA, 요약 수치, 결과 해시 및 재시도 상태로 제한합니다.
- 비용 절감은 서명된 원본 사용량 증거와 승인된 측정 계약이 없으면 `UNKNOWN`으로 표시합니다.
- 비용 telemetry 신뢰 저장소는 선택 사항입니다. 구성하지 않으면 절감액을 검증하지 않고 `UNKNOWN`을 유지합니다.

## 아직 사람이 확정해야 하는 항목

이 문서는 법률 자문이나 최종 개인정보처리방침이 아닙니다. 정식 서비스·유료화·Marketplace 제출 전에 운영주체, 문의 채널, 보존기간, 삭제 절차, 관할 법률, 이용약관을 사람이 확정해야 합니다.
