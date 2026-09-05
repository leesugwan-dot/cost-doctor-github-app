# 비공개 GitHub 저장소: 운영자에게 코드를 보내지 않는 Self-Scan

상태: `PREPARED / USER_REPO_OWNER_ACTION_REQUIRED / EXTERNAL_PRIVATE_REPO_ACTUAL_NOT_YET_VERIFIED`

## 목적

비공개 저장소의 소스코드를 CostDoctor 운영자의 개인 PC나 별도 분석 서버에 업로드하지 않고, **저장소 소유자의 GitHub Actions 안에서 직접** 정적 진단하는 경로입니다.

## 사용자가 하는 일

1. 자신의 private repository에서 `.github/workflows/costdoctor.yml` 파일을 만듭니다.
2. 이 저장소의 [`costdoctor-entry/private-repo-selfscan.yml`](../costdoctor-entry/private-repo-selfscan.yml) 내용을 붙여넣습니다.
3. Commit 합니다.
4. `Actions → CostDoctor private repository self-scan → Run workflow`를 누릅니다.
5. GitHub Summary와 `costdoctor-report` Artifact에서 결과를 확인합니다.

이 과정 자체가 저장소 소유자의 명시적 설치·실행 승인입니다. CostDoctor 운영자가 사용자의 private repository에 직접 접근하도록 권한을 받을 필요가 없습니다.

## 권한 경계

- workflow 권한: `contents: read`
- checkout 후 credential 영속화: `false`
- submodule 자동 확장: `false`
- Git LFS 자동 확장: `false`
- CostDoctor의 대상 저장소 commit/push/PR: 없음
- 자동 merge: 없음
- AI 모델/API key 요구: 없음
- 대상 프로젝트 코드 실행: 없음

## 코드가 머무는 곳

대상 코드는 해당 repository의 GitHub-hosted runner 임시 작업공간에서만 checkout됩니다. CostDoctor 운영자의 개인 PC로 전송하지 않습니다.

GitHub Actions 실행기록·로그·Artifact의 접근 및 보존은 **그 private repository의 GitHub 권한과 GitHub 정책**을 따릅니다. Artifact는 현재 template에서 1일 보존으로 설정합니다.

## 결과 경계

이 모드는 무료 공개 진단과 마찬가지로 **정적 신호**를 찾는 기능입니다. 실제 API 호출 수, 실제 토큰 사용량, 실제 절감액, 품질 개선을 증명하지 않습니다.

## 아직 검증되지 않은 것

- 실제 외부 사용자의 private repository에서의 설치 편의성
- 조직 정책상 GitHub Actions가 제한된 private repository
- GitHub Enterprise Server의 별도 정책 환경

따라서 외부 private repository actual-run이 나오기 전에는 `EXTERNAL_PRIVATE_REPO_VERIFIED`로 표시하지 않습니다.
