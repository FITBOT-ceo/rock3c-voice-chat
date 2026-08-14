# Voice Chat Setup

## 목적

Rock 3C에서 음성 대화 런타임을 락카키 시스템과 분리해서 운영하고, 기본 운영 경로와 로컬 실험 경로를 명확히 구분하는 것이 목적이다.

## 현재까지 확인된 하드웨어/OS 상태

- Debian 11 bullseye
- ARM64 / Cortex-A55 4코어
- RAM 8GB
- USB 오디오 장치 인식
- `arecord` 녹음 성공
- `aplay` / `speaker-test` 재생 명령 성공
- 음향 루프백 기준 실제 주 출력 경로는 `rk809` 아날로그 출력(card 1)

## 실제 설치 경로

보드 내부 실제 작업 경로는 다음으로 고정한다.

```text
/home/radxa/voice-chat
```

## 기본 운영 경로

현재 저장소의 기본 웹 런타임은 Groq API 기반이다.

- STT: Groq Whisper (`whisper-large-v3-turbo`)
- LLM: Groq Chat (`llama-3.3-70b-versatile`)
- TTS: `edge-tts` 기본, 필요 시 `espeak-ng` 또는 `ElevenLabs` 전환

버튼 기반 웹 UI와 Flask 앱을 실제로 돌리려면 아래 패키지가 필요하다.

```bash
sudo apt-get install -y ffmpeg espeak-ng
```

- `ffmpeg`: 브라우저 업로드 `webm` 오디오를 16k WAV로 변환
- `espeak-ng`: 로컬 fallback TTS 검증용

운영 시 필수 환경 변수는 아래다.

- `GROQ_API_KEY`
- `STT_PROVIDER=groq`
- `LLM_PROVIDER=groq`
- `TTS_PROVIDER=edge`

현재 웹 UI는 아래 provider 조합을 환경 변수로 전환할 수 있다.

- `STT_PROVIDER`: `groq` | `vosk`
- `LLM_PROVIDER`: `groq` | `llama`
- `TTS_PROVIDER`: `edge` | `elevenlabs` | `espeak`

로컬 경로를 사용할 때 추가로 쓰는 값:

- `VOSK_MODEL_PATH=/home/radxa/voice-chat/models/vosk-model-small-ko-0.22`
- `LLAMA_SERVER_URL=http://127.0.0.1:8080`
- `LLAMA_SERVER_MODEL=local-model`

웹 UI는 시작 직후 현재 조합을 `기본 운영 경로`, `로컬 실험 경로`, `혼합 검증 경로`로 표시하고, 필요한 구성요소가 빠져 있으면 녹음을 막은 채 오류 사유를 화면에 보여준다.

## 로컬 실험 경로

Groq API와 별도로, Rock 3C 로컬 단독 구동 가능성은 아래 조합으로 검증해 두었다.

- LLM: `llama.cpp` + `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`
- STT: `Vosk` Korean (`vosk-model-small-ko-0.22`)
- TTS: `eSpeak NG` Korean

추가로 확인된 항목:

- `/home/radxa/voice-chat/llama.cpp` 빌드 완료
- Qwen 1.5B GGUF 다운로드 및 단일 턴 응답 생성 확인
- `espeak-ng -v ko` WAV 생성 및 재생 확인
- 비공식 Korean Piper 보이스는 호환성 문제로 보류

로컬 LLM 단독 측정 기준 속도:

- Prompt: `4.8 t/s`
- Generation: `2.8 t/s`

## 1차 목표

실사용 1차 목표는 전이중이 아니라 turn-based 음성 대화다.

1. 마이크 입력 캡처
2. 음성 인식(STT)
3. LLM 응답 생성
4. 음성 합성(TTS)
5. 스피커 출력

## 운영/실험 구분 원칙

- 기본 운영 문서와 서비스 유닛은 Groq + `edge-tts` 경로를 기준으로 설명한다.
- `llama.cpp`/Vosk/eSpeak는 로컬 실험 또는 fallback 경로로 분리해 설명한다.
- 모델 파일은 Git에 직접 넣지 않고, 파일명/출처/체크섬만 문서화한다.
- 실사용 1차 목표는 버튼 기반 웹 UI 안정화다.

## 로컬 UI 전환 예시

웹 UI를 로컬 STT/LLM 경로로 시험할 때는 예를 들어 아래처럼 설정한다.

```bash
export STT_PROVIDER=vosk
export VOSK_MODEL_PATH=/home/radxa/voice-chat/models/vosk-model-small-ko-0.22
export LLM_PROVIDER=llama
export LLAMA_SERVER_URL=http://127.0.0.1:8080
export TTS_PROVIDER=espeak
```

## 주의사항

- 로컬 `llama.cpp` 경로는 유효한 실험 결과이지만 현재 기본 운영값은 아니다.
- `Gemma 4 E4B` 이상은 8GB 보드에서 여유가 매우 적어 기본 선택지로 두지 않는다.
- 로컬 모델 파일은 저장소의 `models/` 또는 보드의 `/home/radxa/voice-chat/models/` 아래에서만 관리한다.
