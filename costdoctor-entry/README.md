# CostDoctor — GitHub 저장소에서 먼저 확인하기

**상태: 공개 진입점 Pilot — GitHub Ubuntu 실제 실행 및 별도 Windows/Python 보고서 재계산 PASS.** 기존 비공개 App을 공개 설치할 수 있다는 뜻이 아닙니다. 이 폴더는 기존 제품을 교체하지 않습니다.

모델 사용 코드·재시도·캐시·문맥 제한의 **검토 후보**를 찾아, 어디부터 실제 사용량을 측정할지 알려줍니다. API 키, 모델 설치, 정규화된 telemetry 파일 없이 첫 진단을 실행할 수 있습니다. 신호 수는 실제 호출 수·비용·낭비량이 아닙니다.

[처음 시작](docs/START.md) · [결과 읽기](docs/RESULTS.md) · [문제 해결](docs/TROUBLESHOOTING.md) · [권한·정보 수집](docs/PRIVACY_PERMISSIONS.md) · [되돌리기](docs/ROLLBACK.md)

[실제 공개 프로젝트의 결과 예시](examples/report.md)는 고정된 ollama-python 소스를 로컬에서 읽은 결과입니다. 실제 모델 호출이나 절감 측정이 아닙니다. 예시 원본과 실행·해시 결속은 공개 예제의 고정 commit과 snapshot 해시로 구분합니다. 비공개 Evidence와 검증 corpus는 게시하지 않습니다.

## 가장 적은 준비: GitHub Action

GitHub 안의 **워크플로 파일 1개 추가** → 수동 **Run workflow** → 같은 commit 읽기 → 정적 진단 → 실행 Summary와 보고서 Artifact 확인 경로입니다. `costdoctor-onefile.yml`은 검증한 동일 scanner/handler로 자동 생성됩니다. App/secret/npm/별도 서버 없이 runner에서만 읽습니다. 자동 PR 이벤트는 기본적으로 켜지 않습니다.

이 진입점은 소유자가 승인한 공개 범위이며 기존 App과 별도입니다. [정확한 설치·실행 순서](docs/GITHUB_PILOT.md)를 참조하세요. 검증 구현은 `60b99f581a3beb6b40954db98ed388f5441cd593`이며 [실제 실행·Summary](https://github.com/leesugwan-dot/cost-doctor-github-app/actions/runs/33983233394)와 [고정 설치 파일](https://github.com/leesugwan-dot/cost-doctor-github-app/blob/60b99f581a3beb6b40954db98ed388f5441cd593/costdoctor-entry/costdoctor-onefile.yml)을 확인할 수 있습니다. 다른 계정의 설치·사용성이나 실제 절감 인증은 아닙니다.

## 로컬 GitHub 프로젝트 진단

Node.js 24 이상이 설치된 상태에서, GitHub에서 받은 실제 프로젝트 폴더를 그대로 읽습니다. 프로젝트 의존성 설치나 코드 실행은 하지 않습니다.

```text
node costdoctor-entry/entry/cli.mjs --repo project --output new-costdoctor-report
```

`new-costdoctor-report/report.md`를 열면 됩니다. 출력은 프로젝트 바깥의 새 폴더여야 합니다. 같은 폴더를 다시 쓰지 않습니다. [정확한 폴더 배치](docs/START.md)를 보세요.

## 비용과 품질

처음 결과는 **절감액 UNKNOWN**, **품질 미측정**입니다. 실제 절감 검증은 같은 목표의 Before/After 사용량, 품질, 재시도·재작업 및 검증비용 자료가 있어야 합니다. 이 진입점은 자동 최적화·merge 차단·provider 영수증 인증을 하지 않습니다. 기존 검증 제품과 실제 두 workload의 제한된 성과를 새 프로젝트의 성과로 가져오지 않습니다.

## 중단/제거

Action은 수동으로만 실행됩니다. 실행 중이면 GitHub에서 Cancel workflow, 이후 Disable workflow로 중지할 수 있습니다. App 설치·secret 추가가 없으므로 App 권한 회수나 키 회전이 필요하지 않습니다. 로컬 CLI는 상시 서비스가 아닙니다.

5분 설치, 일반 절감률, 외부 참가자 성공, Production 완료는 아직 주장하지 않습니다. 이번 승인은 이 GitHub 진입점의 공개·사용 범위에 한정합니다. 비공개 제품 코어의 배포권이나 일반 상용 라이선스/보증을 부여하지 않습니다.
