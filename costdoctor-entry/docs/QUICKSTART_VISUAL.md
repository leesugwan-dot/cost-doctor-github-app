# 사진으로 시작하기 — 5분 Quick Start

**5분은 안내의 목표 길이이며 실제 초보자 설치 시간은 아직 측정하지 않았습니다.** 아래 사진은 2026-09-06 실제 GitHub 화면입니다. 이 진입점은 App 설치나 모델 키 없이 저장소의 정적 신호를 읽습니다. 자동 최적화·절감 인증은 아닙니다.

## 준비: 내 시험 저장소와 권한

자신이 관리하고 시험에 동의한, 비밀정보 없는 공개 저장소를 사용합니다. 파일을 추가할 쓰기 권한과 수동 Actions 실행 권한이 필요합니다. 조직 정책·Actions 요금 한도를 먼저 확인하고 새 결제가 필요하면 진행하지 마세요. 도구 토큰은 `contents: read`입니다. [권한·개인정보](PRIVACY_PERMISSIONS.md)

## 1. 검증한 파일을 복사

[고정 버전 workflow](https://github.com/leesugwan-dot/cost-doctor-github-app/blob/60b99f581a3beb6b40954db98ed388f5441cd593/costdoctor-entry/costdoctor-onefile.yml)를 열어 **Raw/복사**로 전체 내용을 복사합니다. App의 Install 버튼은 이 경로가 아닙니다.

![G04 실제 workflow 복사 도구와 읽기 전용 권한](images/G04.jpg)

## 2. 내 저장소에 파일 하나 추가

**Code → Add file → Create new file**에서 `.github/workflows/costdoctor.yml`을 입력하고 전체 내용을 붙여 넣습니다. **Commit changes**로 기본 branch에 저장합니다. 보호된 branch는 관리자의 승인 절차를 따릅니다. 이미 같은 파일이 있으면 덮어쓰지 말고 내용을 비교하세요.

![G05 실제 새 파일 편집 화면 — 이 캡처는 입력·저장 전](images/G05.jpg)

사진은 실제 빈 편집 화면이며 이번 촬영 중 설치 commit을 다시 만들지는 않았습니다. 파일 이름과 코드가 들어가면 저장 단계로 진행합니다.

## 3. 수동 실행

**Actions → CostDoctor repository review → Run workflow**를 엽니다. 설치한 기본 branch인지 확인한 뒤 초록색 **Run workflow**를 누릅니다. 이 안내 사진은 메뉴를 연 상태이고, 촬영 때문에 새 실행을 만들지 않았습니다.

![G08 실제 branch 선택과 수동 실행 버튼](images/G08.jpg)

## 4. 첫 결과 읽기

완료한 실행의 **Summary**에서 검사 범위와 4종 신호를 읽습니다. 녹색은 workflow 완료입니다. `UNKNOWN`은 미측정이고 0건은 검사 범위 내 불일치입니다. **절감 0% 또는 낭비 없음이 아닙니다.**

![G10 기존 실제 hosted 실행의 Summary](images/G10.jpg)

이 예시는 3개 파일, 3,366 bytes를 검사했고 신호 4종은 모두 0이었습니다. 17초는 서버 실행 시간이지 설치/이해 시간은 아닙니다. [결과 해석과 Before/After](RESULTS.md)

## 5. 보고서 보관·중지

**Artifacts → costdoctor-report**를 받으면 `report.md`와 `report.json`이 있습니다. 보존은 1일이므로 필요하면 만료 전에 본인이 보관하세요. 원문 코드·키·프롬프트는 보내지 마세요. 끝나면 필요 시 workflow를 Disable하고 설치 commit만 되돌립니다. [중지·rollback](ROLLBACK.md)

다음: [14단계 화면 상세 가이드](SCREEN_GUIDE.md) · [오류 해결](TROUBLESHOOTING.md) · [FAQ](FAQ.md) · [다른 계정 시험·PR 경계](GITHUB_PILOT.md)

화면 기준: [실제 run 33983233394](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/runs/33983233394), 실행 구현 `60b99f581a3beb6b40954db98ed388f5441cd593`. 사진은 공개 내용만 잘라 보존했고 계정 헤더·세션 알림은 제외했습니다. 실제 외부 시험자 사용성·새 비용절감·Production 상태를 이 사진만으로 증명하지 않습니다.
