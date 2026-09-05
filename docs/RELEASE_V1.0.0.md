# CostDoctor Repository Review v1.0.0

첫 공개 GitHub Action Marketplace release 준비본입니다.

## 제공 기능

- 공개 repository URL one-link 정적 진단
- GitHub Action 기반 읽기 전용 repository review
- Private Repository는 사용자 자신의 GitHub Actions 안에서 Self-Scan 가능
- 모델 호출, retry, cache, token/context-limit 관련 정적 검토 신호
- sanitized 결과 및 검증 영수증
- 원문 코드·파일명·비밀키를 공개 결과에 포함하지 않음
- 대상 프로젝트 코드 미실행
- 실제 절감 Evidence가 없으면 savings는 `UNKNOWN`

## 안전경계

- 고객 코드를 CostDoctor 운영자의 개인 PC에 저장하지 않음
- 공개 URL 진단에서 대상 repository write 없음
- Private Self-Scan 기본 권한 `contents: read`
- 자동 merge 없음
- 실제 API/모델 비용이 필요한 미래 측정은 고객 GitHub Secret과 작업별 최대 지출한도 승인 필요

## 현재 보류

- 자동 코드 수정/branch/PR 공개 기능
- 유료화 방식·가격
- 외부 AI Provider 기반 자동수정

## License

Apache-2.0. 저장소에 포함되지 않은 비공개 상용 최적화 핵심은 이 공개 라이선스 범위에 포함되지 않습니다.
