# 중지와 rollback

진단은 저장소를 읽기만 하므로 소스 복구가 필요하지 않습니다. 비용절감 최적화를 자동 적용하지 않습니다.

GitHub 설치 후 중지: Actions → 해당 실행 → Cancel workflow. 이후 workflow 메뉴 → Disable workflow. 이는 시험자 자신의 저장소에서 직접 할 수 있습니다. 기본 수동 실행이므로 끄지 않아도 예약·PR 자동실행은 없습니다.

설치 변경을 완전히 되돌릴 때는 설치 commit만 Revert합니다. 다른 프로젝트 파일은 건드리지 않습니다. 새 파일의 목록과 설치 전 commit을 먼저 보존하고 branch 보호 규칙을 지킵니다. 이 작업에서 원격 revert/삭제는 수행하지 않았습니다.

App·webhook·PAT·API key를 추가하지 않으므로 키 제거 작업이 없습니다. Artifact는 해당 저장소 관리 정책 및 지정한 1일 보존 설정에 따릅니다. 삭제를 자동 수행하지 않습니다.

향후 개선 적용은 별도 branch에서 Before/After와 품질검사 후 채택합니다. 이 후보를 채택하지 않아도 기존 App/제품/Authority는 그대로 동작합니다.
