# Rock 3C Voice Chat

> Rock 3C에서 락카키 시스템과 완전히 분리해서 운영하는 로컬 음성 대화 실험 영역

## 목표

이 서브프로젝트의 목표는 다음과 같다.

1. Rock 3C에서 로컬 모델이 실제로 뜨는지 확인
2. 마이크 입력 → 음성 인식 → LLM 응답 → 음성 출력 파이프라인이 동작하는지 확인
3. 기존 락카키 시스템과 코드/설정/실행 경로를 분리해서 관리

## 현재 방향

현재까지 확인된 보드 조건은 다음과 같다.

- 보드: Radxa Rock 3C
- RAM: 8GB
- OS: Debian 11 bullseye
- 오디오: USB Audio 장치 인식 완료
- 마이크 녹음: 성공
- 스피커 재생: 장치 레벨 재생 명령 성공
- 실제 음향 루프백 기준 주 출력 경로: `rk809` 아날로그 출력(card 1)

Gemma 4 로컬 실행 경로는 현재 조사 기준으로 아래 순서가 가장 현실적이다.

1. `llama.cpp` + Qwen2.5 1.5B Instruct GGUF
2. 경량 STT (`Vosk` 또는 `whisper.cpp tiny/base`)
3. 경량 TTS (`Piper` 또는 `eSpeak NG`)

## 실제 런타임 설치 위치

보드 안의 실제 작업 디렉터리는 아래로 고정한다.

```text
/home/radxa/voice-chat
```

현재 상태:

- `llama.cpp` 소스 다운로드 완료
- CMake 설정 완료
- ARM64 CPU 빌드 완료
- `Qwen2.5-1.5B-Instruct-Q4_K_M` 모델 다운로드 완료
- 로컬 단일 턴 응답 검증 완료

## 현재 검증 결과

실제 로컬 모델 검증은 아래 조건에서 성공했다.

- runtime: `llama.cpp`
- model: `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`
- install path: `/home/radxa/voice-chat`
- measured generation speed: 약 `2.8 t/s`

즉, Rock 3C에서 **Qwen2.5 1.5B 로컬 설치 및 실제 응답 생성**까지는 확인된 상태다.

## 현재 음성 파이프라인 상태

- Korean STT: `vosk-model-small-ko-0.22` 로드 확인
- Korean TTS: `espeak-ng -v ko` WAV 생성 및 음향 루프백 검증 완료
- Piper TTS: 공식 영어 보이스는 동작 확인, 비공식 한국어 보이스는 `pygoruut` 호환 문제로 보류

현재 가장 안정적인 1차 음성 루프는 다음 조합이다.

- STT: Vosk Korean
- LLM: Qwen2.5 1.5B Q4_K_M
- TTS: eSpeak NG Korean

## 현재 최적화 상태

현재 웹 UI는 다음 구조로 최적화되었다.

- STT: 웹 앱 시작 시 `Vosk` 모델 사전 로드
- LLM: 매 요청마다 `llama-cli`를 띄우지 않고 `rock3c-llm.service`로 `llama-server` 상주 실행
- TTS: 응답 JSON 반환 후 백그라운드 재생

즉, 이전의 `CLI 1회 실행형` 구조보다 현재 `상주형 서버` 구조가 더 빠르다.

## 최근 측정 결과

동일한 테스트 오디오 기준 측정:

- 이전 (`Qwen 1.5B`, CLI 실행형):
  - `convert_ms`: `613.8`
  - `stt_ms`: `24087.9`
  - `llm_ms`: `29262.0`
  - `tts_ms`: `7940.9`
  - `total_ms`: `61911.6`

- 현재 (`Qwen 1.5B`, llama-server 상주형 + Vosk preload + TTS async):
  - `convert_ms`: `693.7`
  - `stt_ms`: `17291.5`
  - `llm_ms`: `18573.7`
  - `tts_ms`: `0.9`
  - `total_ms`: `36566.8`

대략적으로 총 지연이 **61.9초 → 36.6초**로 줄었다.

버튼 기반 웹 UI 엔트리포인트:

- `rock3c/voice_chat/web_ui/app.py`
- `rock3c/voice_chat/scripts/run_voice_web.sh`
- `rock3c/voice_chat/systemd/rock3c-voice-web.service`

상시 대기용 엔트리포인트:

- `rock3c/voice_chat/scripts/voice_assistant_daemon.py`
- `rock3c/voice_chat/scripts/run_voice_assistant.sh`
- `rock3c/voice_chat/systemd/rock3c-voice-assistant.service`

## 폴더 구성

```text
rock3c/voice_chat/
├── README.md
├── config/
│   ├── audio_devices.example.json
│   └── voice_chat_config.example.json
├── docs/
│   ├── VOICE_CHAT_MODEL_NOTES.md
│   ├── VOICE_CHAT_RUNBOOK.md
│   └── VOICE_CHAT_SETUP.md
├── scripts/
│   ├── run_voice_web.sh
│   ├── run_voice_assistant.sh
│   ├── run_voice_turn.sh
│   ├── voice_assistant_daemon.py
│   └── voice_turn_loop.py
├── systemd/
│   ├── rock3c-voice-web.service
│   └── rock3c-voice-assistant.service
├── web_ui/
│   ├── app.py
│   ├── static/
│   │   ├── voice_ui.css
│   │   └── voice_ui.js
│   └── templates/
│       └── voice_ui.html
├── models/
│   └── README.md
└── artifacts/
    └── README.md
```

## 문서 링크

- [설치/환경 준비](./docs/VOICE_CHAT_SETUP.md)
- [모델 선택 메모](./docs/VOICE_CHAT_MODEL_NOTES.md)
- [실행/검증 절차](./docs/VOICE_CHAT_RUNBOOK.md)
- [버튼 기반 웹 UI 서비스 유닛](./systemd/rock3c-voice-web.service)
- [상시 대기 서비스 유닛](./systemd/rock3c-voice-assistant.service)
- [한 턴 음성 루프 스크립트](./scripts/voice_turn_loop.py)

## 분리 원칙

- 이 영역은 락카키 앱의 `app/`, `config/`, `models/`를 직접 재사용하지 않는다.
- 보이스 실험용 모델/설정/스크립트는 여기 또는 `rock3c/scripts/` 하위에만 둔다.
- 안정화 전까지는 별도 프로세스로만 실행한다.
