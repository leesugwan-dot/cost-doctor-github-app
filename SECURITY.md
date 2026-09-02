# 보안 경계

- Webhook 원문 바이트를 HMAC-SHA256으로 먼저 검증한 뒤 JSON을 해석합니다.
- GitHub App installation token은 저장소 1개와 `pull_requests:read`, `contents:read`, `checks:write`로 제한합니다.
- PR을 다시 조회해 webhook의 head SHA와 일치하는 경우에만 분석합니다.
- fork PR은 별도 접근 증거가 없으면 차단합니다.
- ZIP은 추출 전에 경로, 중복, 대소문자·Unicode 충돌, 심볼릭 링크, 압축 폭탄을 검사합니다.
- Check 생성은 공유 영속 장부의 lease/fence 안에서 실행하고 결과를 독립 readback합니다.
- 이 후보는 하나의 공유 SQLite 장부를 사용하는 단일 호스트 배포만 지원합니다. 독립 장부를 가진 다중 호스트 배포는 금지합니다.

취약점 신고 채널은 공개 전에 운영자가 별도로 확정해야 합니다.
