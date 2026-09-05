# 권한과 수집 경계

설치 시: 선택한 시험 저장소의 파일/워크플로를 추가할 권한이 필요합니다. branch 보호나 조직 정책이 있으면 관리자가 설치해야 합니다. 모든 저장소 권한이나 GitHub App 설치는 요구하지 않습니다.

실행 시: workflow의 `GITHUB_TOKEN`은 `contents: read`만 지정하고, checkout 자격증명을 저장하지 않습니다. PR/Issue/Check 쓰기, OAuth, PAT, 모델 비밀키는 요청하지 않습니다. 보고서 업로드는 GitHub Actions의 해당 실행 Artifact 저장 기능을 이용하며 보고서 2개만, 보존 1일을 지정합니다. GitHub 플랫폼의 실제 보존/관리 정책이 우선합니다.

소스는 GitHub runner 또는 사용자 PC에서 읽고 코드 자체를 실행하지 않습니다. `node_modules`, `.git`, build/cache/vendor, 명시적 secret 관련 이름과 링크는 제외합니다. 자체 진단 방지를 위해 `costdoctor-entry` 폴더와 설치 경로 `.github/workflows/costdoctor.yml`도 제외합니다. 파일당 256KiB, 합계 5MiB, 방문 5,000개, 깊이 12와 디렉터리당 512개 상한입니다. 일부 파일 제외가 있으면 coverage에 표시합니다.

보고서에 포함: 정적 신호 개수, 검사 범위/제외 수, 입력 snapshot 해시, caller가 준 commit, 도구의 시간/CPU, 상태·다음 행동.

보고서에 미포함: 파일명·절대 경로·소스 원문·개인 이름·원문 prompt·API key·토큰·청구서. 파일 안에 있는 지시문은 실행하지 않습니다. 포함된 해시는 출처 인증이나 참가자 동의 증명이 아닙니다.

GitHub 실행은 checkout, 공식 setup-node의 Node 24 준비, GitHub 보고서 저장 네트워크를 사용합니다. 프로젝트 의존성 캐시는 끄며 npm/pip 설치나 저장소 코드를 실행하지 않습니다. **도구 자체 네트워크 0**을 **전체 GitHub 실행 네트워크 0**으로 표시하지 않습니다. GitHub 무료/조직 과금 한도는 계정별이므로 이 작업에서 hosted 실행이나 새 비용을 발생시키지 않았습니다.

시험자는 결과 공유 전 검토하고 중단할 수 있습니다. 공개 PR/Issue에 결과를 자동 게시하지 않습니다. 개인정보 고지·배포 범위 결정 없이 새 공개 서비스로 승격하지 않습니다.
