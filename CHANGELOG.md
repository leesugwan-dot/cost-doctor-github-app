# Changelog

## Universal Engine R1 — 2026-09-06

- Added data-driven Model, Pricing, and Provider registries without changing the existing Marketplace Action identity
- Added offline adapters for Generic, OpenAI, Anthropic, Gemini, Agnes, and Ollama usage exports
- Added privacy-safe runtime Usage Evidence, append-only receipts, broad measured waste detectors, bound Before/After benchmarks, Quality Guard, Routing Advisor, and separate Independent Validator
- Added fixture-scoped Verified Savings binding, actual rollback/reapply runs, and CostDoctor self-dogfood measurements
- Added a `future-model-x` Registry-only compatibility gate; unknown pricing remains `UNKNOWN/BLOCKED`
- Added a read-only GitHub self-test that performs two separate fresh actual acceptance runs with one-day sanitized Artifact retention

The public Action, public scanner, private read-only Self-Scan, external-telemetry-off policy, no-write defaults, D5/D7/D9 deferrals, and paid-run approval boundary remain unchanged.

## v1.0.1 — Discovery and privacy-safe user Evidence

- Marketplace identity name stays stable while its short description adds `AI cost`, `LLM cost`, `Cost Doctor`, token, retry, and cache search terms
- README first screen now presents the free public scan, Marketplace Action, and private read-only Self-Scan paths directly
- Earlier GitHub App material moved out of the Marketplace first-time user path and preserved as a separate legacy reference
- Added a privacy-safe feedback Issue Form
- Added repository-native user Evidence reporting after public scans and on a daily schedule
- User Evidence reports aggregate public scan and feedback counts without reporting usernames, user Issue bodies or comments, customer source, filenames, secrets, or private-repository activity
- Marketplace installation counts and private Self-Scan users remain `UNKNOWN` because external telemetry stays off

D5 automatic modification/PR, D7 monetization, and D9 external AI-provider automatic fixes remain deferred.

## Public Beta R2 — 2026-09-06

- 공개 GitHub 저장소 주소 하나로 자동 진단하는 one-link 진입점 유지
- GitHub 저장소 내부 branch/file 링크도 저장소 URL로 정리
- 한국어 / English 결과 선택
- 사용자당 24시간 5회 남용 제한
- private/disabled/과대 저장소 fail-closed
- GitHub API 기본 브랜치 HEAD와 실제 checkout HEAD 결속
- submodule/LFS 미확장, Git 설정/프로토콜 제한 강화
- 운영자 개인 PC 미사용, target project code 미실행 경계 문서화
- Python unit tests + Node syntax check + fresh scanner smoke test 자동화
- weekly self-test 추가
- CodeQL/Dependabot 유지관리 추가
- 공개 FAQ, 상태 코드, 실제 예시, 기계 판독 계약 추가
- privacy-safe Bug Report / PR template / CODEOWNERS / CONTRIBUTING 추가

실제 외부 사용자 가치, 실제 비용·토큰 절감, 품질 개선은 이 정적 공개 진단만으로 증명하지 않습니다.

## Public Beta R1 — 2026-09-06

- 공개 저장소 URL 입력 Issue Form 공개
- GitHub-hosted runner에서 실제 공개 저장소 정적 진단 실행
- 결과 댓글 자동 생성 및 요청 자동 종료
- 원문 코드·파일명·비밀정보 미출력
