# rock3c-voice-chat — P3 Rock3C 음성 인터페이스 (paused)

> ⚠️ **현행 본체는 여기가 아니다.** 최신은 `gym-locker-system-2026/rock3c/voice_chat/` 다.
> 이 repo 는 초기 음성 상담 UX 검증본이며 **P3 프로젝트가 paused** 상태다.

## 도달점

Rock 3C(Radxa, 8GB, Debian 11)에서 마이크 녹음·스피커 재생 확인, 웹 UI 음성 대화 동작.
녹음 → webm 업로드 → ffmpeg 16kHz 변환 → STT → LLM 응답 → 비동기 재생.
경로 변경: 로컬 모델(llama.cpp + Qwen2.5) → **Groq STT + Groq LLM + 선택형 TTS**.

기준 문서: `docs/VOICE_UX_STATUS.md` (단, 흡수본이 더 최신).

## 승계 상태 (2026-08-14 blob SHA 대조)

- 실질 유일본은 `scripts/test_groq_chat.py` 1건 — 흡수본으로 옮긴 뒤 아카이브 가능
- 나머지는 흡수본에 동일하거나 흡수본이 더 최신

## ⚠️ 이 repo 는 org 에서 PUBLIC 이다

자격증명은 없으나(config 는 example 뿐) 공개 상태 자체가 결정 사항이다.
새 파일을 넣기 전에 공개돼도 되는 내용인지 확인한다.
공개 repo 목록 기준: `zerolane-control/.claude/rules/known-public-repos.txt`

## 작업 규약

- 재개 전까지 신규 기능 이슈를 만들지 않는다 (stage=paused)
- 브랜치 `claude/{agent}/YYYY-MM-DD-{slug}` — `origin/main` 기준
- PR 본문 `Closes zerolane-os/zerolane-os#{n}` (풀패스)
- `main` 직접 push 금지
