# 실제 공개 저장소 진단 예시

현재 공개 진입점의 첫 실제 GitHub 실행 예시는 다음 Issue에 보존돼 있습니다.

- [실제 공개 저장소 진단 예시 #1](https://github.com/leesugwan-dot/cost-doctor-github-app/issues/1)

이 예시는 공개 저장소를 대상으로 GitHub-hosted runner에서 실제 workflow가 실행되고, CostDoctor 결과 댓글이 자동 생성된 뒤 요청이 자동 종료되는 흐름을 확인하기 위한 것입니다.

주의:

- 예시의 정적 신호 수는 해당 저장소 스냅샷에서 찾은 검토 후보 수입니다.
- 실제 API 호출 수나 비용 낭비량을 뜻하지 않습니다.
- 실제 절감액과 품질은 별도 Before/After 실행 증거가 없으므로 `UNKNOWN`입니다.
- 이후 공개 스캐너 고도화는 같은 안전 경계를 유지하면서 입력 검증, HEAD 결속, 남용 방지, 다국어 결과, 자동 self-test를 추가합니다.
