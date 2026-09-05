# 보안 경계

## 무료 공개 저장소 진단

무료 공개 진단은 **공개 GitHub 저장소의 제한된 정적 분석**만 수행합니다.

- 입력 URL은 `github.com` 공개 저장소로 제한합니다.
- private repository, 비활성화 저장소, 공개 베타 크기 한도 초과 저장소는 차단합니다.
- 사용자당 24시간 최대 5회로 제한합니다.
- 분석 전 GitHub API에서 기본 브랜치 HEAD를 확인하고 실제 checkout HEAD와 정확히 일치해야 계속합니다.
- 대상 checkout은 GitHub-hosted runner의 임시 작업공간에서만 사용합니다.
- 대상 저장소 코드는 실행하지 않습니다.
- Git submodule 재귀 checkout과 Git LFS 확장을 사용하지 않습니다.
- Git clone은 외부 file protocol, repository hook, 사용자/global Git 설정의 영향을 제한한 상태로 실행합니다.
- 정적 스캐너는 파일 개수·개별 파일 크기·총 분석 바이트·디렉터리 깊이에 상한을 둡니다.
- 심볼릭 링크, 바이너리, 과대 파일, 비밀정보 가능성이 높은 파일명은 분석 대상에서 제외합니다.
- 대상 저장소에는 commit, push, PR, issue, 파일 수정 등 쓰기를 하지 않습니다.
- 공개 결과에는 원문 코드, 파일명, 비밀키, API Key, private repository 내용을 포함하지 않습니다.
- 분석 실패·시간 초과·HEAD 불일치 시 부분 결과를 성공으로 승격하지 않습니다.
- 성공 결과에는 대상 HEAD, CostDoctor 실행 버전, 정적 진단 요약을 해시로 묶은 **sanitized receipt**를 생성합니다.
- 성공 결과 Artifact는 `result.md`와 `receipt.json`만 담고 현재 1일 보존합니다.
- 완료된 진단 Issue는 결과 보존·후속 스팸 감소를 위해 닫은 뒤 lock을 시도합니다. lock 실패 자체로 정상 진단을 거짓 실패로 바꾸지는 않습니다.

공개 요청과 결과 Issue, GitHub Actions 기록은 GitHub의 공개 저장소 및 보존 정책의 적용을 받습니다.

## 비공개 저장소 Self-Scan

private repository는 공개 URL 진단에서 읽지 않습니다. 준비된 Self-Scan 방식은 저장소 소유자의 GitHub Actions 안에서만 실행합니다.

- workflow 권한은 `contents: read`
- checkout credential 영속화 금지
- submodule/LFS 자동 확장 금지
- 대상 프로젝트 코드 미실행
- 자동 commit/push/PR/merge 없음
- CostDoctor 운영자의 개인 PC나 별도 분석 서버로 private source 업로드 없음
- 결과/로그 접근은 해당 private repository의 GitHub 권한 적용

외부 사용자의 실제 private repository에서 actual-run 검증 전에는 이 경로를 외부 검증 완료로 표시하지 않습니다.

## Verified Fix 준비 경계

자동수정 기능을 공개할 경우에도 진단·수정안 생성·테스트·Before/After 검증은 repository 쓰기 없이 먼저 수행하는 방향을 기본으로 합니다. 실제 branch/PR 게시에는 사용자 승인과 최소 쓰기 권한이 필요하며 **자동 merge는 기본 금지**합니다.

## 기존 GitHub App 후보 경계

- Webhook 원문 바이트를 HMAC-SHA256으로 먼저 검증한 뒤 JSON을 해석합니다.
- GitHub App installation token은 저장소 1개와 `pull_requests:read`, `contents:read`, `checks:write`로 제한합니다.
- PR을 다시 조회해 webhook의 head SHA와 일치하는 경우에만 분석합니다.
- fork PR은 별도 접근 증거가 없으면 차단합니다.
- ZIP은 추출 전에 경로, 중복, 대소문자·Unicode 충돌, 심볼릭 링크, 압축 폭탄을 검사합니다.
- Check 생성은 공유 영속 장부의 lease/fence 안에서 실행하고 결과를 독립 readback합니다.
- 이 후보는 하나의 공유 SQLite 장부를 사용하는 단일 호스트 배포만 지원합니다. 독립 장부를 가진 다중 호스트 배포는 금지합니다.

취약점 신고용 별도 비공개 채널은 운영자가 최종 확정해야 합니다. 비밀정보가 포함된 신고는 공개 Issue에 올리지 마세요.
