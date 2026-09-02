# 공개·운영 전 필수 조건

현재: `PUBLIC_PILOT_CANDIDATE / TEMPORARY_ISOLATED_LIVE_E2E_PASS / PRODUCTION_AUTHORITY_FALSE`

1. 승인된 HTTPS 실행환경과 비공개 작업영역 ACL 검증
2. GitHub App 등록 및 최소 권한·저장소 범위 readback
3. Webhook secret과 private key의 안전한 파일 참조 및 접근권한 검증
4. 실제 테스트 저장소의 PR event → exact commit → Check Run end-to-end
5. Check Run 외부 readback, 중복 delivery, crash/restart, rate-limit 회귀
6. 공개 라이선스, 개인정보 고지, 이용조건, 환불·지원 정책 확정
7. 실제 사용량 증거가 없을 때 절감 수치 `UNKNOWN` 유지 확인
8. clean test repository에서 설치·첫 PR·readback·제거 actual-run
9. 실제 측정 전까지 `Quick Start`를 ‘5분 설치’로 표시하지 않는 문서 Gate

1~5의 내부 격리 실증은 완료됐습니다. 외부 공개에는 6의 실제 정책 선택과 외부 clean repository 설치 검증이 남아 있으며, 판매·정산·Production 완료를 주장하지 않습니다.
