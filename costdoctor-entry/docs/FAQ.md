# 사진 가이드 FAQ

## App 설치나 API key가 필요한가요?

아니요. 현재 공개 진입점은 workflow 파일 한 개를 본인 저장소에 추가합니다. 과거 App 설치 문서와 혼동하지 마세요. 도구 토큰은 contents 읽기만 요청합니다. 설치 commit에는 저장소 쓰기 권한이 필요합니다. [권한·정보 범위](PRIVACY_PERMISSIONS.md)

## Run workflow 버튼이 없어요.

파일이 `.github/workflows/costdoctor.yml`이고 기본 branch에 저장됐는지, Actions가 허용됐는지, 본인에게 실행 권한이 있는지 확인합니다. 조직·보호 branch 제한을 우회하지 마세요. [오류 해결](TROUBLESHOOTING.md)

## 사진처럼 초록색이면 비용이 줄어든 건가요?

아니요. 초록색은 workflow 성공입니다. `UNKNOWN`은 비용 미측정, `NOT_MEASURED`는 품질 미측정입니다. 4종 신호 0도 제한된 검사 범위에 일치가 없다는 뜻입니다. 보고서는 자동 수정하지 않습니다. [결과·Before/After](RESULTS.md)

## 무엇부터 개선하나요?

신호 항목 하나를 실제 실행과 비교하세요. 예제·주석에 나온 단어일 수도 있으므로 곧바로 retry나 cache를 없애면 안 됩니다. 실제 입력·버전·품질 기준을 고정하고 격리 branch의 Before/After를 비교합니다. 코드를 판단하기 어렵다면 항목과 질문만 관리자에게 전달하세요.

## 실제로 5분이면 끝나나요?

아직 보장하지 않습니다. 5분 Quick Start는 간결한 안내 목표입니다. [관측한 hosted 실행](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/runs/33983233394)은 17초였지만 사람의 설치·이해 시간과 다릅니다. 외부 시험자의 첫 가치 도달시간은 별도 측정합니다.

## 성공 실행의 Node.js 경고는 무엇인가요?

현재 고정 실행은 성공했지만 `actions/upload-artifact`의 고정 버전이 Node 20을 지정하고 GitHub가 Node 24로 실행했다는 경고가 표시됩니다. 경고 1개를 누락하지 않고 보존했습니다. GitHub는 Node 24 전환과 Node 20 제거 일정을 안내합니다. 유지관리자는 공식 Node 24 지원 버전을 별도 검증한 뒤 핀을 갱신해야 합니다. [GitHub 공식 전환 안내](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)

이 문서 보강에서는 workflow나 실행 코드를 바꾸지 않았습니다. 경고를 없애려고 보안 완화 변수·무검증 최신 버전을 사용하지 마세요. 사진 G12는 실제 전환 경고이며 의도적 실패 테스트가 아닙니다.

## Artifact가 사라졌어요.

보고서 보존은 1일입니다. 만료 뒤에는 GitHub Summary를 읽거나 본인이 만료 전에 보관한 보고서를 사용합니다. 사진을 재현하려고 불필요한 실행을 반복할 필요는 없습니다. 보고서에는 원문 소스 대신 집계값이 들어가지만 GitHub의 공개 저장소/실행 메타데이터는 공개됩니다.

## PR 자동 실행이나 merge 차단도 하나요?

현재 기본 경로는 수동 실행입니다. PR 자동 실행, App Check Run, merge enforcement로 승격하지 않습니다. [GitHub 시험 안내](GITHUB_PILOT.md)

## 중지하거나 없애려면요?

실행은 Cancel workflow, 이후 Disable workflow를 사용합니다. 설치를 되돌릴 때는 설치 commit만 Revert합니다. 진단이 소스를 수정하지 않으므로 최적화 코드를 복구할 필요는 없습니다. [상세 rollback](ROLLBACK.md)

## 어떤 자료를 보내면 되나요?

자발적으로 동의한 시험 ID, 정확한 버전, 성공/고정 오류코드, 설치·결과 도달시간, 이해 여부, 재사용 의향만 보냅니다. 원문 코드·계정 ID·비밀키·개인정보·프롬프트·청구서는 보내지 않습니다. [최소 피드백](GITHUB_PILOT.md)
