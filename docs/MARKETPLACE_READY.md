# CostDoctor GitHub Marketplace 준비상태

상태: `READY_FOR_OWNER_UI_SUBMISSION / FREE_ENTRY_ONLY`

## 공개 전략

무료 진단을 먼저 공개하고, 자동 수정·유료화·AI 자동수정 방식은 현재 보류합니다.

## Marketplace 표시 권장안

- 이름: **CostDoctor Repository Review**
- 한 줄 설명: **Read-only static review for AI/model cost-related repository signals. No API key and no verified-savings claim from static signals.**
- 가격: **Free**
- 대상: 공개/비공개 GitHub 프로젝트에서 AI·모델 비용 관련 코드 신호를 빠르게 점검하려는 개발자·팀
- 기본 진입: 공개 저장소는 CostDoctor 공개 URL 진단, Private Repository는 사용자 저장소 내부 Self-Scan

## 준비 완료 항목

- 루트 `action.yml` Marketplace 메타데이터
- branding 설정
- Apache-2.0 LICENSE + NOTICE
- README/Quick Start
- PRIVACY.md
- TERMS.md
- SECURITY.md
- SUPPORT.md
- Private Repository Self-Scan 설명
- 공개 진단 실제 GitHub-hosted 실행 Evidence
- 자동 회귀검사 및 CodeQL

## 외부 UI에서 남는 항목

GitHub Marketplace 실제 제출은 GitHub 계정 소유자가 GitHub UI에서 다음을 수행해야 할 수 있습니다.

1. Marketplace 게시자/약관 요구사항 확인 및 동의
2. Listing 생성 또는 기존 GitHub App/Action 선택
3. 로고·카테고리·스크린샷 등 UI 필드 최종 확인
4. 제출/Publish 버튼 실행
5. GitHub 심사가 요구되는 경우 심사 대응

이 단계는 저장소 코드 수정이 아니라 GitHub 계정/Marketplace의 외부 약관 및 게시 행위이므로 자동으로 우회하지 않습니다.

## 보류 표시

Marketplace 설명에서 다음 기능을 제공한다고 주장하지 않습니다.

- 자동 코드 수정/PR 공개 기능
- 실제 절감액 자동 보장
- 유료 Verified Fix
- 외부 AI Provider를 이용한 자동 수정

외부 반응과 실제 Evidence 후 별도 승인되면 추가합니다.
