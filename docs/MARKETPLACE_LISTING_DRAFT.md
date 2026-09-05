# GitHub Marketplace 공개 문구

상태: `CURRENT_FREE_LISTING_COPY / OWNER_RELEASE_PENDING`

## 공개 형태

1차 Marketplace 진입은 **무료 CostDoctor Repository Review**로 시작합니다. 자동 코드 수정, 유료화, 외부 AI Provider 기반 자동수정은 사용자 반응을 본 뒤 결정하므로 현재 Listing에서 제공 기능으로 표시하지 않습니다.

## 이름

**CostDoctor Repository Review**

## 짧은 설명

> Read-only static review for AI/model cost-related repository signals. No API key and no verified-savings claim from static signals.

한국어 설명:

> GitHub 프로젝트에서 AI·모델 비용 검토 신호를 찾는 읽기 전용 정적 진단 도구입니다. 대상 프로젝트를 실행하지 않으며 정적 신호만으로 실제 절감액을 주장하지 않습니다.

## 핵심 장점

- 공개 저장소: GitHub 주소 하나로 무료 진단
- Private Repository: 운영자 PC로 코드를 보내지 않는 사용자 GitHub Actions Self-Scan 기본
- 대상 프로젝트 코드 미실행
- 공개 URL 진단 대상 저장소 자동 write 없음
- 정적 신호를 실제 절감액으로 과장하지 않음
- GitHub-hosted runner 중심
- 공개 결과에 원문 코드·파일명·비밀정보 미포함
- Private Self-Scan 기본 권한 `contents: read`
- Apache-2.0 공개 통합 계층

## 검색어 참고

- AI cost
- LLM cost
- token optimization
- repository review
- GitHub Actions
- cost optimization

Marketplace 실제 카테고리는 Release UI에 표시되는 현재 허용 목록에서 기능과 가장 가까운 항목을 소유자가 선택합니다.

## 무료 범위

- 공개 저장소 URL 정적 진단
- 한국어 / English 결과
- sanitized 검증 영수증
- 실제 비용·토큰 절감액은 측정 Evidence가 없으면 `UNKNOWN`
- Private Repository read-only Self-Scan template

## 현재 보류 — Listing에 광고하지 않음

- 자동 코드 수정/branch/PR 공개 기능
- 유료 Verified Fix 및 가격
- 외부 AI Provider 기반 자동수정/코드 전송

## 게시 준비 링크

- License: `LICENSE`
- Privacy: `PRIVACY.md`
- Terms: `TERMS.md`
- Support: `SUPPORT.md`
- Security: `SECURITY.md`
- Marketplace 단계: `docs/MARKETPLACE_READY.md`

## 마지막 외부 단계

저장소 소유자가 루트 `action.yml`에서 Release 초안을 열고, GitHub Marketplace 게시를 선택하고, 필요 시 Developer Agreement에 동의한 뒤 `v1.0.0` Release를 게시합니다.
