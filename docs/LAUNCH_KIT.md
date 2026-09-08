# CostDoctor Launch Kit

이 문서는 외부 게시 전에 검토할 수 있는 준비 문구입니다. 실제 커뮤니티 게시나 광고는 하지 않습니다.

## 한 줄 소개

- 한국어: GitHub 저장소의 AI/LLM 비용 낭비 구조를 코드 실행 없이 무료로 점검합니다.
- English: CostDoctor finds AI/LLM cost-waste structure in a GitHub repository without running or modifying the code.

## 30초 소개

공개 저장소 URL 하나를 입력하면 Static Precheck와 Universal Stage 2가 같은 Issue 결과에 연결됩니다. 모델 API 호출, Secret, 대상 코드 실행, 저장소 쓰기는 무료 경로에서 사용하지 않습니다. 실제 비용·절감률은 별도 Provider usage Evidence가 있을 때만 검증됩니다.

## 결과에서 확인하는 것

1. 점검 우선순위와 가장 중요한 문제
2. 실제 target repository에서 발견한 안전한 근거 위치
3. 구조적으로 측정 가능한 문맥·호출·재시도·캐시 신호
4. 아직 확인할 수 없는 항목과 다음 측정 방법

## 자주 묻는 질문

**비공개 저장소도 되나요?** 공개 URL 경로가 아니라 자신의 GitHub Actions에서 Private Self-Scan을 실행하세요.

**절감률을 바로 보여주나요?** 무료 경로는 실제 Provider usage가 없으면 절감률을 만들지 않습니다. 같은 workload의 Before/After usage가 있을 때만 Verified Savings가 가능합니다.

**코드가 바뀌나요?** 공개 진단과 Self-Scan 모두 read-only입니다. 자동 수정·commit·push·branch·PR·merge는 하지 않습니다.

## 게시 전 금지 문구

- 가짜 사용자 수, 고객 사례, 후기, 절감률을 쓰지 않습니다.
- Static signal을 실제 호출·실제 청구·Verified Savings로 표현하지 않습니다.
- Secret, 원문 prompt, source, 파일명을 공개 결과에 넣지 않습니다.
