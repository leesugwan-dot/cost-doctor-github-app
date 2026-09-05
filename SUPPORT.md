# CostDoctor 공개 베타 지원

공개 베타 지원은 이 저장소의 GitHub Issues에서 받습니다.

- 일반 지원: https://github.com/leesugwan-dot/cost-doctor-github-app/issues
- 개인정보/공개기록 삭제 요청: [Privacy Request 양식](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=privacy-request.yml)
- 현재 개인정보 정책: [PRIVACY.md](PRIVACY.md)
- 현재 이용조건: [TERMS.md](TERMS.md)

**비밀번호, 토큰, API Key, private key, webhook secret, 원문 비공개 코드, 고객정보를 공개 Issue에 올리지 마세요.**

## 무료 공개 저장소 진단

[무료 진단 시작](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/new?template=public-scan.yml)

- 공개 GitHub 저장소 주소만 입력하세요.
- 진단 결과는 공개 Issue에 표시됩니다.
- 현재 무료 베타는 사용자당 24시간 최대 5회입니다.
- 정적 신호는 실제 비용·토큰 절감 검증이 아닙니다.
- 정상 결과에는 대상 HEAD와 CostDoctor 실행 버전/진단 요약을 묶은 검증 영수증이 생성되며, 민감정보 없는 결과 Artifact는 현재 1일 보존합니다.

## 비공개 저장소

private repository 주소는 공개 진단 Issue에 넣지 마세요.

[비공개 저장소 Self-Scan 안내](docs/PRIVATE_REPO_SELF_SCAN.md)를 사용하면 저장소 소유자의 GitHub Actions 안에서 읽기 전용으로 진단할 수 있습니다. 운영자 개인 PC에 private source를 보내는 방식이 아닙니다.

현재 기본방식은 공식적으로 Self-Scan으로 확정했지만, 외부 사용자의 실제 private repository에서의 설치 편의성과 반복 재현성은 해당 소유자의 승인 아래 actual-run Evidence가 더 필요합니다.

## 실제 API 측정 정책

향후 Before/After 실제 API 측정에서는 고객 자신의 Provider 계정과 GitHub Secret을 사용하고 작업별 최대 지출한도를 명시적으로 승인받는 원칙을 적용합니다. 현재 Provider 실행 기능은 활성화되어 있지 않습니다.

[실제 측정 정책](docs/MEASURED_RUN_POLICY.md)

## 현재 보류

다음은 외부 반응을 본 뒤 결정합니다.

- 자동 코드 수정/branch/PR 공개 기능
- 유료화 방식·가격·환불정책
- 외부 AI Provider를 이용한 자동수정 방식

## 오류·버그 보고

공개 가능한 정보만 사용해 다음을 적어 주세요.

- 어떤 단계에서 막혔는지
- 화면에 표시된 제한된 상태 코드
- 발생 시각
- 다시 실행해도 같은지

보안 취약점이나 비밀정보 노출이 의심되면 공개 Issue에 원문을 붙이지 마세요. 별도 비공개 보안 신고채널이 마련되기 전에는 추가 실행을 중단하세요.

이 공개 베타는 무료 실험 단계이며 응답시간 보장, Production SLA, 손실 보증이 없습니다.

[공개 진단 상세 설명](docs/PUBLIC_SCAN.md) · [Marketplace 준비상태](docs/MARKETPLACE_READY.md) · [Pilot 결과 보고 형식](docs/PILOT_FEEDBACK.md)
