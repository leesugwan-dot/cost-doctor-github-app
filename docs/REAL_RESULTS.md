# 공개 가능한 실제 결과 범위

상태: `BOUNDED_INTERNAL_EVIDENCE / NO_GENERALIZATION`

격리된 내부 시험에서 GitHub App 등록·설치, hosted backend, 첫 PR 처리와 Check readback을 검증했습니다. 서로 다른 두 workload의 Before/After 실행도 완료했지만, 이 저장소에는 원시 토큰량·단가·금액·비공개 저장소 정보·내부 경로를 공개하지 않습니다.

현재 공개적으로 주장할 수 있는 범위는 다음뿐입니다.

- 내부 제한 시험 두 건을 완료했습니다.
- 두 시험 모두 동일 조건의 Before/After 비교였습니다.
- 품질 저하와 False-PASS 악화가 없는지 함께 확인했습니다.
- 결과는 특정 시험에만 유효하며 일반 고객 절감률로 일반화하지 않습니다.
- 외부 사용자의 설치·반복 사용·고객 수·매출 Evidence는 아직 없습니다.

## 외부 검증 시 기록할 항목

- 공개 가능한 테스트 날짜와 환경
- PR 유형과 기존 CI 조건
- Check 생성 및 readback 결과
- 발견 신호와 사람 검토 결과
- False PASS/FAIL
- 처리시간과 재현 방법
- 공개 가능한 Evidence와 제한사항

## 수용 Gate

- fixture를 실제 외부 사례로 표시하지 않습니다.
- 예상값을 실측값처럼 표시하지 않습니다.
- 원시 비용·토큰·비공개 저장소·고객명·내부 경로·secret을 공개하지 않습니다.
- source 존재만으로 절감효과를 검증 처리하지 않습니다.
- 내부 제한 시험을 Production 또는 일반화된 절감효과 PASS로 승격하지 않습니다.
