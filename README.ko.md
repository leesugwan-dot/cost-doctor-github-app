# CostDoctor 한국어 안내

[English README](README.md)

CostDoctor는 GitHub 저장소의 AI·LLM 비용 낭비 구조를 코드 실행 없이 무료로 점검하는 읽기 전용 도구입니다.

## 시작

1. [한국어 Quick Scan](https://leesugwan-dot.github.io/cost-doctor-github-app/ko/)을 엽니다.
2. 공개 GitHub 저장소 주소 하나를 입력합니다.
3. GitHub 양식에서 공개 결과 안내를 확인하고 제출합니다.
4. 같은 Issue의 단일 댓글에서 Stage 1 + Stage 2 결과를 확인합니다.

비공개 저장소는 [Private Self-Scan](docs/PRIVATE_REPO_SELF_SCAN.md)을 사용하세요.

## 안전 경계

- 대상 프로젝트 코드를 실행하지 않습니다.
- 공개 진단에서 API Key와 Provider API를 사용하지 않습니다.
- commit·push·branch·PR·merge를 자동으로 만들지 않습니다.
- 고객 source를 운영자 개인 PC로 보내지 않습니다.
- 무료 구조 진단은 실제 비용·절감률을 자동으로 주장하지 않습니다.

## 결과 읽기

결과는 후보 수, 실행 경로 근거, 가능한 결정론적 측정, 구체적 다음 행동, 신뢰도를 함께 표시합니다. Provider usage와 품질 Evidence가 없으면 실제 비용·절감은 `UNKNOWN`입니다.
