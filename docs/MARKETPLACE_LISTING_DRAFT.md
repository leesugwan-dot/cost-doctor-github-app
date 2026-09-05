# GitHub Marketplace 공개 준비 초안

상태: `DRAFT_READY / NOT_SUBMITTED`

## 추천 공개 형태

1차 Marketplace 진입은 **무료 CostDoctor 진단**으로 시작합니다. 유료 결제는 외부 사용성·가치 Evidence가 쌓인 뒤 별도로 추가합니다.

## 이름

**CostDoctor**

## 짧은 설명 초안

> Find AI/LLM cost-review signals in a GitHub repository without executing the target project. Public URL scan is free; private repositories can self-scan in their own GitHub Actions runner.

한국어 설명:

> GitHub 프로젝트에서 AI·LLM 비용 검토 후보를 찾는 무료 정적 진단 도구입니다. 대상 프로젝트를 실행하지 않으며 공개 저장소는 링크 하나로, 비공개 저장소는 해당 저장소의 GitHub Actions 안에서 Self-Scan하도록 설계합니다.

## 핵심 장점

- 공개 저장소: GitHub 주소 하나로 무료 진단
- private repo: 운영자 PC로 코드를 보내지 않는 Self-Scan 준비
- 대상 프로젝트 코드 미실행
- 정적 신호를 실제 절감액으로 과장하지 않음
- GitHub-hosted runner 중심
- 결과에 원문 코드·파일명·비밀정보 미포함
- 최소권한 우선

## 추천 카테고리/검색어 초안

- Developer tools
- Code quality
- AI / LLM
- Cost optimization
- Token optimization
- GitHub Actions

실제 Marketplace가 허용하는 카테고리 목록에 맞춰 제출 시 최종 선택합니다.

## 무료 플랜 초안

**Free Diagnosis**

- 공개 저장소 URL 정적 진단
- 한국어 / English 결과
- 실제 비용·토큰 절감액은 측정 Evidence가 없으면 `UNKNOWN`
- private repo Self-Scan은 GitHub Actions 설치형으로 제공 가능

## 추후 유료 후보

- Verified Fix
- Before/After 측정
- 품질/회귀검증
- 독립 검증 Evidence
- 반복 모니터링

유료 항목은 가격·환불·지원정책이 확정되기 전 Marketplace에 가격으로 표시하지 않습니다.

## 제출 전 사람 결정 필요

- 공개 라이선스
- 운영자/사업자 표시명
- 공식 문의 이메일 또는 지원 URL
- 최종 개인정보처리방침 URL
- 최종 이용약관 URL
- 실제 Marketplace 카테고리
- Marketplace 제출 승인

## 제출 전 actual 확인

- 외부 계정에서 무료 진단 진입 가능
- 외부 사용자의 첫 결과까지 시간 측정
- 모바일/데스크톱 사용성
- private Self-Scan을 공개할 경우 실제 외부 private repo actual-run
- 개인정보/지원 링크가 실제로 열림

이 문서는 제출 준비용이며 Marketplace 등록 완료를 의미하지 않습니다.
