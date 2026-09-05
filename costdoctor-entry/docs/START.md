# 처음 시작

## 로컬: 실행 파일 2개로 시작

1. 공개 저장소의 `costdoctor-entry` 폴더를 같은 이름으로 준비합니다. 모델이나 별도 App 설치는 필요 없습니다.
2. GitHub 프로젝트에서 **Code → Download ZIP**으로 받은 폴더를 같은 위치에 `project`로 둡니다. 비공개 프로젝트는 소유자 허용 없이 사용하지 않습니다.
3. Node.js 24 이상이 이미 설치된 환경에서 그 상위 폴더를 열고 아래 명령을 실행합니다. 설치되어 있지 않으면 자동으로 다운로드/설치하지 않습니다.

```text
node costdoctor-entry/entry/cli.mjs --repo project --output new-costdoctor-report
```

폴더 구조:

```text
trial/
  costdoctor-entry/entry/cli.mjs
  costdoctor-entry/entry/scan.mjs
  project/                     실제 GitHub 소스
  new-costdoctor-report/       실행 후 생성
```

4. 생성된 `report.md`를 열어 신호가 많은 항목의 “다음 행동”을 읽습니다. 어떤 파일도 자동 수정하지 않았습니다.
5. 다른 프로젝트는 새 출력 이름으로 실행합니다. 기존 결과를 삭제해 재실행할 필요가 없습니다.

## GitHub 안에서 사용

기본 경로는 `costdoctor-onefile.yml` 한 파일을 `.github/workflows/costdoctor.yml`로 추가하는 방식입니다. 공개 README에 연결된 고정 implementation commit의 파일을 사용하고 [GitHub 시험 순서](GITHUB_PILOT.md)에 따라 실행합니다. 목표는 실제 참가자가 로컬 명령 없이 Summary까지 도달하는 경로입니다. 그 시간은 아직 측정하지 않았습니다.

## 이 도구가 하지 않는 것

- 모델/API 호출, 저장소 코드 실행, npm/pip 설치, 자동 수정, 결제, 원문 코드 외부 전송.
- 실제 호출 수/토큰/요금을 파일의 단어 수로 추정.
- 검사 대상 밖 파일까지 정상으로 판단.

첫 진단은 정적 검토 후보 찾기입니다. 실제 원가 개선 판단은 [결과 읽기](RESULTS.md)의 다음 단계입니다.
