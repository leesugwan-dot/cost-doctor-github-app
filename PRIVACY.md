# CostDoctor 개인정보 및 코드 처리 정책

적용일: 2026-09-06

이 문서는 현재 무료 공개 진단과 읽기 전용 Private Repository Self-Scan의 실제 기술 경계를 설명합니다. 유료화 또는 별도 hosted 서비스가 추가되면 해당 기능의 처리 범위를 별도로 고지합니다.

## 운영 표시 및 문의

- 서비스 표시명: **CostDoctor**
- 일반 문의·삭제 요청 접수: https://github.com/leesugwan-dot/cost-doctor-github-app/issues
- 공개 Issue에는 비밀번호, 토큰, API Key, private key, 비공개 코드, 고객정보 등 민감정보를 올리지 마세요.

현재 무료 베타의 문의 채널은 공개 GitHub Issues입니다. 민감정보가 필요한 문의는 공개 Issue에 내용을 올리지 말고 추가 실행을 중단하세요. 별도 비공개 보안 연락채널이 마련되면 SECURITY.md에 고지합니다.

## 무료 공개 저장소 진단

1. 사용자가 입력한 공개 GitHub 저장소 주소와 진단 결과는 이 저장소의 공개 Issue에 표시됩니다.
2. 대상 프로젝트는 CostDoctor 운영자의 개인 PC로 전송하거나 저장하지 않습니다.
3. 대상 저장소는 GitHub-hosted runner의 임시 작업공간에서 제한적으로 checkout하고 정적 분석합니다.
4. 대상 프로젝트 코드는 실행하지 않습니다.
5. 원문 코드, 파일명, 로컬 경로, 비밀번호, 토큰, API Key, private key는 공개 결과 댓글에 포함하지 않습니다.
6. CostDoctor 자체 외부 telemetry 수집 서비스는 기본적으로 사용하지 않습니다.
7. GitHub Issue, Actions 로그, Artifact의 보존·삭제에는 GitHub의 서비스 정책과 저장소 설정이 적용됩니다.
8. 공개 진단의 sanitized 결과 Artifact는 현재 1일 보존으로 설정합니다.
9. 정적 진단 결과만으로 실제 비용·토큰 절감, 결함 존재, 품질 개선을 확정하지 않습니다.

## Private Repository Self-Scan

Private Repository는 운영자의 PC나 운영자 저장소로 소스코드를 보내는 방식보다 **저장소 소유자의 GitHub Actions 안에서 읽기 전용으로 실행하는 Self-Scan**을 기본 방식으로 합니다.

- 기본 권한: `contents: read`
- 원본 코드의 운영자 PC/서버 영속 저장: 하지 않음
- 기본 외부 telemetry: OFF
- 대상 저장소 자동 수정·push·PR·merge: 하지 않음
- 결과 보존: 사용자의 GitHub 저장소/Actions 정책에 따름

실제 외부 사용자의 Private Repository에서의 재현성 검증은 해당 소유자의 명시적 설치·실행 승인이 필요합니다.

## 실제 API/모델을 사용하는 측정

향후 실제 Before/After 측정을 실행하는 경우 기본 원칙은 다음과 같습니다.

- API Key는 고객 자신의 GitHub Secret에 둡니다.
- CostDoctor 운영자에게 API Key를 전달하도록 요구하지 않습니다.
- 작업마다 사용자가 최대 지출한도를 명시적으로 승인해야 합니다.
- 승인 한도를 넘길 가능성이 있으면 실행을 중단합니다.
- AI를 이용한 자동 코드 수정 및 외부 Provider 전송 방식은 현재 보류 상태이며 공개 기능으로 활성화하지 않습니다.

## 수집하지 않는 정보

현재 무료 공개 진단은 CostDoctor 자체 데이터베이스에 다음을 수집·보관하지 않습니다.

- 비밀번호, API Key, PAT, private key
- 비공개 저장소 원문 소스
- 사용자의 로컬 파일 경로
- 원문 프롬프트
- 결제정보

## 삭제 요청

현재 별도 CostDoctor 사용자 DB는 없습니다. 공개 진단 요청/결과의 삭제 요청은 GitHub Issue의 번호나 URL만 적어 공개 지원 채널에 요청할 수 있습니다. 민감정보를 새로 적지 마세요. GitHub 자체 기록의 삭제 가능 범위와 로그 보존은 GitHub 정책의 영향을 받습니다.

## 준거 기준

현재 무료 베타의 운영정책은 대한민국을 기본 관할로 설계합니다. 강행법규 또는 사용자의 소재지에서 반드시 적용되는 법령이 있는 경우 해당 규정이 우선될 수 있습니다.

## 변경

기능 범위, 보존정책, 외부 전송, 유료화가 변경되면 이 문서를 먼저 갱신하고 변경이력에 기록합니다.
