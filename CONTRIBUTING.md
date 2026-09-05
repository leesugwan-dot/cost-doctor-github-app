# Contributing to CostDoctor public beta

공개 베타 개선 제안과 PR은 환영합니다. 다만 신뢰 경계를 먼저 지켜 주세요.

## 절대 올리지 말아야 할 것

- private repository 원문
- API Key, PAT, OAuth token, webhook secret, private key
- 고객정보, 개인정보, 사내 경로
- 공개 권한이 없는 로그·데이터

## 공개 진단의 고정 경계

현재 one-link public scan은 공개 GitHub 저장소의 제한된 정적 진단입니다.

- 대상 코드를 실행하지 않습니다.
- 대상 저장소에 쓰지 않습니다.
- 운영자 개인 PC로 프로젝트를 보내지 않습니다.
- 정적 신호만으로 실제 호출 수·낭비·절감액·품질을 확정하지 않습니다.
- private repository 지원은 별도 권한 설계 없이 추가하지 않습니다.

## 변경 절차

1. 작은 범위의 변경으로 분리합니다.
2. 새 외부 GitHub Action은 공식 출처를 우선하고 commit SHA 고정을 사용합니다.
3. `python3 .github/scripts/test_public_scan.py`를 통과시킵니다.
4. Node entry 파일의 문법 검사를 통과시킵니다.
5. public scan self-test workflow가 성공하는지 확인합니다.
6. PR 템플릿의 안전 확인을 완료합니다.

## 검출 규칙 변경

새 정적 규칙을 추가할 때는 단순히 신호 수가 늘어나는 것을 개선으로 보지 않습니다. 최소한 다음을 구분해야 합니다.

- 어떤 비용/품질 문제의 후보인지
- 오탐 가능성
- 실제 실행 증거가 없을 때 어떤 주장을 금지해야 하는지
- 기존 결과와의 회귀 위험

실제 절감 수치가 필요한 기능은 정적 스캔과 분리하고 동일 목표·입력·모델·품질 기준의 Before/After Evidence가 필요합니다.
