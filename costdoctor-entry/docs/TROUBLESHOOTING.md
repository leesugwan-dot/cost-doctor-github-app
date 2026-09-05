# 실패 원인과 다음 행동

| 표시 | 이유 | 다음 행동 |
| --- | --- | --- |
| REPOSITORY_INVALID | 폴더가 없거나 루트가 링크임 | 압축을 푼 실제 프로젝트 폴더를 선택 |
| OUTPUT_MUST_BE_OUTSIDE_REPOSITORY | 입력 안에 결과를 쓰려 함 | 프로젝트 옆 새 폴더로 지정 |
| OUTPUT_EXISTS | 이전 결과 보존 | 다른 새 출력 이름 사용, 삭제 불필요 |
| OUTPUT_PARENT_INVALID | 상위 폴더가 없거나 링크임 | 실제 존재하는 상위 폴더 선택 |
| HEAD_INVALID | commit 형식 오류 | GitHub의 실제 40자리 commit 사용, 모르면 CLI --head 생략 |
| ARGUMENT_MISSING/INVALID | 명령 형식 오류 | START의 명령과 --help 확인 |
| RUNNER_CONTEXT_MISSING | Action을 로컬 CLI처럼 실행함 | CLI 사용 또는 실제 workflow 실행 |
| REPOSITORY_OUTSIDE_WORKSPACE | workflow 범위 밖 경로 | repository 입력을 기본값 .으로 복원 |
| NO_SUPPORTED_SOURCE | 지원 소스가 없음 | docs-only 프로젝트라면 실제 코드가 있는 사본으로 전환 |
| PARTIAL_SCAN | 일부 링크/크기/읽기 한도 | coverage를 읽고 범위를 좁힌 사본에서 새 결과로 검사 |
| IO_ERROR | 파일 접근/공간 문제 | 권한과 공간 확인, 기존 결과는 유지 |
| Action not found | 잘못된 버전/파일 경로 또는 설치 누락 | 공개 commit/설치 파일 확인. 반복 실행하지 말고 공개 README의 고정 링크 확인 |
| Run workflow 버튼 없음 | 기본 branch에 수동 workflow 없음/권한 부족 | 기본 branch와 workflow_dispatch, 조직 Actions 정책 확인 |

부분 보고서가 생긴 뒤 실패했으면 그 폴더를 성공 결과로 사용하지 않습니다. 새 출력 경로로 다시 실행합니다. 자동 재시도·모델 fallback·추가 비용은 없습니다.
