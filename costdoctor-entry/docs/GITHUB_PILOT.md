# GitHub 설치·실행 순서

현재 공개 저장소는 `https://github.com/leesugwan-dot/cost-doctor-github-app`입니다. 이번 진입점은 `costdoctor-entry`에 있으며 App 설치 없이 workflow 파일 한 개로 사용합니다. 과거 비공개 App의 설치 URL은 이 경로에서 사용하지 않습니다.

## 현재 공개 범위

소유자가 entry 코드/Action/workflow/설명과 공개 예제의 게시를 승인했습니다. 비공개 backend/core, telemetry 원문, secret, 검증 corpus, 전체 Evidence ZIP은 공개 범위가 아닙니다. root README의 검증 상태와 고정 implementation commit을 먼저 확인합니다. 다른 사람의 저장소 쓰기는 별도 자발적 동의 없이는 수행하지 않습니다.

## 참가자가 정확히 할 일

게시 후 실제 버전이 고정되면 공개 코드/문서만으로 로컬 재현할 수 없는 **다른 계정의 권한·설치·사용성** 확인에 한해 참가자가 필요합니다. 임의의 타인 저장소를 대신 수정하지 않습니다.

1. 참가자는 자신이 관리하는 비밀정보 없는 공개 시험 저장소 하나의 사용에 자발적으로 동의합니다. 이름·연락처·개인 저장소 내용을 보낼 필요는 없습니다.
2. 공개 CostDoctor README에서 검증된 release/commit의 `costdoctor-onefile.yml`을 열고 Raw 내용 전체를 복사합니다. App의 Install 버튼을 사용하지 않습니다. root README에서 검증한 버전의 고정 링크를 확인합니다.
3. 시험 저장소 **Code → Add file → Create new file**에서 파일명을 `.github/workflows/costdoctor.yml`로 입력하고 복사한 내용을 붙여 넣습니다. **Commit changes**로 기본 branch에 저장합니다. 권한이 없거나 branch 보호가 있으면 저장소 관리자가 설치 commit을 승인합니다. 별도 Action 폴더 업로드·모델/API key는 필요 없습니다.
4. 기본 branch에 설치 후 **Actions → CostDoctor repository review → Run workflow → Run workflow**를 누릅니다. 기본 branch에 workflow가 있어야 버튼이 보입니다.
5. 완료 실행을 열어 **Summary**의 진단 표와 다음 행동을 읽습니다. 필요하면 **Artifacts → costdoctor-report**를 받아 report.md/report.json을 봅니다. 녹색 실행은 scan 완료이지 절감 PASS가 아닙니다.
6. 시험 후 workflow를 Disable하고, 필요하면 설치 commit만 되돌립니다. 기존 소스는 바꾸지 않습니다.

## 필요한 권한

설치: 선택 저장소에 workflow 파일을 추가할 쓰기 권한. 실행: 해당 workflow 수동 실행 권한. 도구 토큰: contents 읽기만. App/OAuth/PAT/secret/model 결제는 없음. 조직 정책/Actions 요금 한도는 참가자가 확인하며 추가 비용에 동의하지 않으면 hosted 실행하지 않습니다.

## 무엇을 보내는가

참가자가 허용한 비공개 전달 경로로 무작위 시험 ID, 동의 확인, 사용한 버전 SHA, OS/runtime 주 버전, 설치/실행 성공, 첫 Summary까지 걸린 시간, 고정 오류코드, 보고서의 이해/행동 가능 여부와 재사용 의향만 보냅니다. 원문 코드·파일명·계정 ID·token·prompt·private repo·청구서는 보내지 않습니다. 실행 URL 공유는 해당 공개 실행의 별도 동의가 있을 때만 선택사항입니다.

엔진은 자기보고만으로 외부 PASS를 만들지 않고 exact 공개 버전/관측 가능한 실행/권한 경계와 독립 readback을 재확인합니다. 참가자 동의는 비용절감 인증이나 공개/판매 동의가 아닙니다.
