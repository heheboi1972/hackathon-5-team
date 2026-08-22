# 커플 대화 리포트 — Day 0 산출물

처음이면 docs/GETTING_STARTED.md 부터.
스캐폴딩(from scratch)은 docs/SCAFFOLD.md §5 의 지시문을 Claude Code에 붙여넣기.

## docs/  (읽는 순서)
1. GETTING_STARTED.md  30분 가이드 + 막혔을 때 + 스캐폴딩 순서
2. PRD_기획서_v1.md    기획서
3. REQUIREMENTS.md     FR/NFR/US + 추적 매트릭스
4. API_SPEC.md         프론트·백 계약
5. TRD.md              기술 스택 + 아키텍처 + 관측성(Instana)
6. SCAFFOLD.md         디렉토리 트리, 역할별 편집 범위, .env, Claude Code 지시문
7. TASKS.md            3일 Phase 계획
8. TEST_CASES.md       완료 기준표

## src/  (완성된 파일 — 스캐폴딩 때 제자리로 이동)
- kakao_parser.py     카톡 파서
- metrics.py          세션·주간 지표·이상치
- ai_service.py       watsonx/Mock (e5 접두사, gpt-oss 토큰 예산, OTel 스팬)
- infra/              docker-compose, Dockerfile×2, nginx.conf, requirements.txt
