# Voice Chat Setup

## 목적

Rock 3C에서 로컬 음성 대화를 락카키 시스템과 완전히 분리해서 검증하는 것이 목적이다.

## 현재까지 확인된 하드웨어/OS 상태

- Debian 11 bullseye
- ARM64 / Cortex-A55 4코어
- RAM 8GB
- USB 오디오 장치 인식
- `arecord` 녹음 성공
- `aplay` / `speaker-test` 재생 명령 성공
- 음향 루프백 기준 실제 주 출력 경로는 `rk809` 아날로그 출력(card 1)

## 실제 설치 경로

보드 내부 실제 설치 경로는 다음으로 둔다.

```text
/home/radxa/voice-chat
```

이 안에 아래를 둔다.

- `llama.cpp`
- 모델 파일
- Python 가상환경
- STT/TTS 테스트 스크립트

## 필수 시스템 패키지

버튼 기반 웹 UI까지 포함해 실제로 동작시키려면 아래 시스템 패키지가 필요하다.

```bash
sudo apt-get install -y ffmpeg espeak-ng
```

- `ffmpeg`: 브라우저에서 업로드한 `webm` 오디오를 16k WAV로 변환
- `espeak-ng`: 한국어 음성 출력

## 현재 설치 완료 항목

### llama.cpp

- 설치 위치: `/home/radxa/voice-chat/llama.cpp`
- 빌드 결과: `llama-cli`, `llama-server`, `llama-mtmd-cli` 생성 완료

### 현재 활성 LLM 모델

- 모델 파일: `/home/radxa/voice-chat/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`
- 다운로드 완료
- 로컬 로딩 및 짧은 응답 생성 확인 완료

### 실제 검증 결과

검증 프롬프트에 대해 실제 응답 `안녕하세요.` 가 반환되었다.

관찰된 대략적인 속도:

- Prompt: `4.8 t/s`
- Generation: `2.8 t/s`

## 1차 목표

최초 목표는 **전이중(full duplex)** 이 아니라 아래 파이프라인의 성공 여부를 보는 것이다.

1. 마이크 입력 캡처
2. 음성 인식(STT)
3. Gemma 4 로컬 응답 생성
4. 음성 합성(TTS)
5. 스피커 출력

## 현재 가장 현실적인 스택

- LLM: `llama.cpp` + Qwen2.5 1.5B Instruct GGUF
- STT: `Vosk` 또는 `whisper.cpp tiny/base`
- TTS: `Piper`

현재 버튼 기반 웹 UI의 안정 경로는 아래 조합이다.

- LLM: `llama.cpp` + Qwen2.5 1.5B Instruct GGUF
- STT: `Vosk` Korean
- TTS: `eSpeak NG` Korean

이 선택의 이유는 Rock 3C에서 CPU/메모리 한계를 넘지 않으면서 로컬 구동 가능성이 가장 높기 때문이다.

## 주의사항

- `Gemma 4 E4B` 이상은 8GB 보드에서도 매우 빡빡할 수 있다.
- 실사용 1차 목표는 **turn-based 음성 대화**로 잡는다.
- 모델 파일은 루트 `models/`가 아니라 `rock3c/voice_chat/models/` 아래에서만 관리한다.

## 다음 단계

이 문서는 이후 아래 내용을 추가한다.

- 실제 패키지 설치 명령
- 모델 다운로드 위치
- STT/TTS 엔진 선택 확정
- 최소 실행 스크립트
