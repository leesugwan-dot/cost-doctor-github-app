# CostDoctor 무료 공개 저장소 진단

[처음 방문했다면 Pages Quick Scan 화면](https://leesugwan-dot.github.io/cost-doctor-github-app/) · [저장소 README](../README.md) · [Private Self-Scan](PRIVATE_REPO_SELF_SCAN.md)

[FAQ](PUBLIC_SCAN_FAQ.md) · [상태 코드](PUBLIC_SCAN_STATUS_CODES.md) · [실제 예시](PUBLIC_SCAN_EXAMPLE.md) · [보안 경계](../SECURITY.md) · [코드/개인정보 처리 초안](../PRIVACY_DRAFT.md) · [기계 판독 계약](../public_scan_contract.json)

## Quick Scan 기본 경로

[Pages Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/)에서 공개 GitHub URL 하나를 입력하면 브라우저가 `owner/repository`로 정규화하고 안전한 GitHub Issue Form으로 이동합니다. 이 정적 화면에는 GitHub credential, workflow, ref, runner, shell, secret이 없습니다. Issue Form은 공개 결과 동의를 받는 trusted fallback 경로이며 기존 `public-scan.yml`을 그대로 사용합니다.

진행 상태는 `요청 접수 → 분석 중 → 완료/실패`로 안내합니다. 실제 결과는 GitHub Issue의 단일 CostDoctor 댓글에서 확인합니다.

## 가장 간단한 사용법

1. [Pages Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/) 또는 [fallback Issue Form](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml)을 엽니다.
2. 검사할 **공개 GitHub 저장소 주소**를 붙여넣습니다.
3. 결과 언어를 선택합니다.
4. 공개 진단 고지를 확인하고 `Submit new issue`를 누릅니다.
5. CostDoctor가 결과 댓글을 남기고 요청을 자동으로 닫습니다.

별도 설치, API Key, PAT, OAuth, AI 모델 결제가 필요하지 않습니다.

## 현재 공개 베타에서 하는 일

CostDoctor는 한 번의 요청에서 Stage 1 Static Precheck와 Stage 2 Deep Diagnosis를 이어서 제공합니다. 제한된 텍스트 소스 범위에서 다음 후보를 찾고, 가능한 경우 구조적 정량값을 함께 계산합니다.

- 모델 호출 후보(실제 invocation과 SDK import를 구분)
- 재시도 후보(활성/비활성 설정과 문서·테스트 신호를 구분)
- AI 요청 문맥 재사용 후보(일반 파일·CI 캐시와 구분)
- 토큰·문맥 제한 후보(Before/개선 후보/Delta)

결과는 근거 범위와 신뢰도(강함/중간/약함)를 함께 보여줍니다. 숫자는 **실제 API 호출 수, 결함 수, 낭비량, 절감액이 아닐 수 있습니다.** 실제 비용·토큰 절감은 동일 목표·입력·모델·품질 조건의 Before/After 실행 증거가 있어야 검증할 수 있습니다.

## R5 결과 읽는 순서

댓글의 주요 항목은 **후보 수 → 실제 runtime 영향 후보 → 안전한 상대경로/호출 그룹 → 가능한 토큰·비용 영향 → 구체적 측정·수정 방법 → 예상 효과 또는 산정 불가 사유 → 신뢰도와 미확인 항목** 순서로 표시됩니다. 테스트·평가·문서 호출, 비활성 재시도, 일반 파일/CI 캐시는 production 비용 누수로 승격하지 않습니다.

무료 경로에서는 다음 상태를 따로 표시합니다: 구조 진단, 실제 사용량, 실제 비용, 실제 절감 검증, 품질 비열화 검증. 무료 구조 측정은 Provider 청구량이 아니며, 실제 usage와 품질 Evidence가 없으면 절감률은 `UNKNOWN`으로 남습니다.

## 코드 처리 경계

- 공개 GitHub 저장소만 받습니다.
- 비공개 저장소는 읽지 않습니다.
- 대상 프로젝트는 CostDoctor 운영자의 개인 PC로 보내지 않습니다.
- GitHub-hosted runner의 임시 작업공간에서만 읽습니다.
- 대상 프로젝트 코드를 실행하지 않습니다.
- submodule과 Git LFS 콘텐츠를 자동 실행/확장하지 않습니다.
- 분석 직전 GitHub API에서 기본 브랜치 HEAD를 확인하고 실제 checkout HEAD와 일치해야 계속합니다.
- 원문 코드·파일명·비밀키·API Key를 결과 댓글에 넣지 않습니다.
- 대상 저장소에 commit, push, PR, issue, 파일 수정 등 쓰기 작업을 하지 않습니다.

## 무료 베타 보호장치

- 사용자당 24시간 최대 5회
- 작업당 최대 실행 시간 제한
- 공개 저장소 크기 상한
- 파일 개수·파일 크기·총 분석 바이트 상한
- 심볼릭 링크, 비밀정보 가능성이 높은 파일명, 바이너리, 과대 파일 제외
- 자동화 계정 요청 차단
- GitHub 외부 URL 차단
- 실패 시 부분 결과를 성공으로 표시하지 않는 fail-closed 처리

## 결과 언어

현재 결과 댓글은 다음을 지원합니다.

- 한국어
- English

한국어와 English는 같은 정보와 안전 경계를 제공하며, 내부 판정 enum은 기본 댓글에 표시하지 않습니다.

## 결과 공개 범위

요청과 결과는 이 공개 GitHub 저장소의 Issue에 표시됩니다. 따라서 공개해서는 안 되는 프로젝트명, 비밀값, 사내 경로, 고객정보 등을 입력하지 마세요.

GitHub 자체의 Issue/Actions 로그 보존은 GitHub 정책의 적용을 받습니다. CostDoctor 공개 진단은 별도 외부 telemetry 수집 서비스를 사용하지 않습니다.

## 오류가 날 때

오류 댓글에는 원문 소스 대신 제한된 상태 코드와 다시 시도할 링크만 표시합니다. 저장소가 private이거나, 비활성화됐거나, 공개 베타 한도를 초과하거나, 분석 중 기본 브랜치가 바뀌면 안전하게 중단합니다.

[상태 코드 표](PUBLIC_SCAN_STATUS_CODES.md)에서 의미와 다음 행동을 확인할 수 있습니다.

## 현재 범위 밖

다음은 이 무료 공개 정적 진단이 자동으로 수행하지 않습니다.

- 실제 API/모델 호출 실행
- 실제 비용 청구
- 실제 토큰 절감액 확정
- 코드 자동 수정
- branch/PR 자동 생성
- private repository 접근
- Production merge 차단

이 기능들은 별도 권한·측정·검증 경계가 필요한 후속 단계입니다.

---

## English quick summary

Paste one **public GitHub repository URL** into the scan form, choose English, submit, and wait for the result comment. CostDoctor performs a bounded static scan in a temporary GitHub-hosted runner workspace. It does not execute the target project's code, request repository credentials, write to the target repository, or claim measured savings from static signals alone.
