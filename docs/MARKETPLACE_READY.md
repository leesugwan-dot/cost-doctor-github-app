# CostDoctor GitHub Marketplace 준비상태

상태: `READY_FOR_OWNER_RELEASE_AND_PUBLISH / FREE_ENTRY_ONLY`

## 공개 전략

무료 진단을 먼저 공개하고, 자동 수정·유료화·AI 자동수정 방식은 현재 보류합니다.

## Marketplace 표시 권장안

- 이름: **CostDoctor Repository Review**
- 한 줄 설명: **Read-only static review for AI/model cost-related repository signals. No API key and no verified-savings claim from static signals.**
- 가격: **Free**
- 대상: 공개/비공개 GitHub 프로젝트에서 AI·모델 비용 관련 코드 신호를 빠르게 점검하려는 개발자·팀
- 기본 진입: 공개 저장소는 CostDoctor 공개 URL 진단, Private Repository는 사용자 저장소 내부 Self-Scan

## 저장소 준비 완료

- 공개 repository
- 루트 `action.yml` 1개
- Marketplace용 `name`, `description`, `branding`
- 실제 root Action CI 실행
- Apache-2.0 LICENSE + NOTICE
- README/Quick Start
- PRIVACY.md
- TERMS.md
- SECURITY.md
- SUPPORT.md
- Private Repository Self-Scan 설명
- 공개 진단 실제 GitHub-hosted 실행 Evidence
- 자동 회귀검사 및 CodeQL

## GitHub 계정 소유자가 UI에서 해야 하는 마지막 게시 단계

GitHub Action Marketplace 게시에는 저장소 소유자 계정의 약관 동의와 Release 게시가 필요하므로 이 부분은 자동 우회하지 않습니다.

1. repository 루트의 `action.yml`을 GitHub에서 엽니다.
2. 표시되는 Marketplace 게시 배너에서 `Draft a release`를 선택합니다.
3. `Publish this Action to the GitHub Marketplace`를 선택합니다.
4. 아직 동의하지 않았다면 GitHub Marketplace Developer Agreement에 동의합니다.
5. Marketplace 카테고리를 선택합니다.
6. 버전 태그를 지정합니다. 첫 공개 권장값: `v1.0.0`.
7. Release 제목 권장값: `CostDoctor Repository Review v1.0.0`.
8. 무료 공개 범위와 설명을 최종 확인하고 `Publish release`를 실행합니다.
9. GitHub가 요구하는 2단계 인증 절차를 완료합니다.

현재 GitHub 공식 문서 기준으로 Action은 게시 요구사항을 충족하면 App Marketplace처럼 별도 심사요청 흐름을 거치는 방식이 아니라 Release 게시 과정에서 Marketplace에 공개됩니다.

## 보류 표시

Marketplace 설명에서 다음 기능을 제공한다고 주장하지 않습니다.

- 자동 코드 수정/PR 공개 기능
- 실제 절감액 자동 보장
- 유료 Verified Fix
- 외부 AI Provider를 이용한 자동 수정

외부 반응과 실제 Evidence 후 별도 승인되면 추가합니다.
