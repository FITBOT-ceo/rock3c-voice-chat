# Voice Chat Runbook

## 목적

이 문서는 Rock 3C에서 현재 기본 운영 경로와 로컬 실험 경로를 각각 어떻게 검증하는지 정리한다.

## 현재 검증 완료 항목

### 오디오 입력

```bash
arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 3 /tmp/rock3c_mic_test.wav
```

### 오디오 출력

```bash
speaker-test -D plughw:2,0 -c 2 -t sine -f 1000 -l 1
```

## 기본 운영 경로

현재 저장소의 기본 런타임은 Groq 기반 웹 UI다.

- STT: Groq Whisper
- LLM: Groq Chat
- TTS: `edge-tts`

필수 환경 변수 예시:

```bash
export GROQ_API_KEY="..."
export STT_PROVIDER=groq
export LLM_PROVIDER=groq
export TTS_PROVIDER=edge
```

웹 UI 시작 시 로그에는 현재 provider 조합이 `STT=...`, `LLM=...`, `TTS=...` 형태로 남는다.
같은 정보와 필수 구성요소 점검 결과는 웹 UI의 `실행 경로` 패널에서도 바로 확인할 수 있다.

## 로컬 실험 경로 검증 결과

### Current LLM

- `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` 로컬 로딩 성공
- 실제 응답 생성 성공

### Korean STT

- `vosk-model-small-ko-0.22` 로드 성공
- 3초 마이크 캡처 + 인식 파이프라인 실행 성공
- 빈 결과가 한 번 나온 것은 모델 실패가 아니라 입력 음성이 거의 없었던 케이스

### Korean TTS

- `espeak-ng -v ko` 로 한국어 WAV 생성 성공
- `paplay` + 마이크 루프백으로 실제 출력 증가 확인

## 로컬 단일 턴 실행

```bash
/home/radxa/voice-chat/.venv/bin/python /home/radxa/voice-chat/scripts/voice_turn_loop.py --seconds 5
```

동작 순서:

1. 5초 녹음
2. Vosk 한국어 인식
3. Qwen 응답 생성
4. eSpeak NG 한국어 음성 재생

## 로컬 provider 기반 웹 UI 실행

```bash
export STT_PROVIDER=vosk
export VOSK_MODEL_PATH=/home/radxa/voice-chat/models/vosk-model-small-ko-0.22
export LLM_PROVIDER=llama
export LLAMA_SERVER_URL=http://127.0.0.1:8080
export TTS_PROVIDER=espeak
/home/radxa/voice-chat/scripts/run_voice_web.sh
```

주의:

- `STT_PROVIDER=vosk`일 때는 `vosk` 파이썬 패키지와 모델 디렉터리가 필요하다.
- `LLM_PROVIDER=llama`일 때는 `rock3c-llm.service` 또는 `scripts/run_llama_server.sh`로 로컬 서버가 먼저 떠 있어야 한다.
- 위 조건이 빠져 있으면 웹 UI는 기동을 유지하되 녹음을 막고 오류 메시지를 표시한다.

## 버튼 기반 웹 UI 실행

가장 실사용에 가까운 현재 권장 방식은 버튼 기반 웹 UI다.

서비스:

```bash
sudo systemctl status rock3c-voice-web.service
```

보드 로컬 브라우저에서 열 주소:

```text
http://127.0.0.1:5099
```

동작 방식:

1. `녹음 시작` 버튼을 누른다.
2. 말한다.
3. `중지 후 전송` 버튼을 누른다.
4. 화면 로그에 사용자 문장과 모델 답변이 쌓인다.
5. 답변은 스피커로도 재생된다.

기본 운영 기준 설명:

- STT/LLM은 Groq API를 호출한다.
- 응답 음성은 기본적으로 `edge-tts`로 재생한다.
- `espeak-ng`는 fallback 또는 로컬 실험 검증용이다.

## 오류 안내와 fallback 규칙

- 웹 UI 상태 문구는 `대기 중`, `녹음 중`, `음성 처리 중`, `런타임 점검 필요`, `오류 발생`으로 구분한다.
- `런타임 점검 필요`는 provider별 필수 구성요소가 빠졌을 때 표시하며, 녹음 버튼은 비활성화한다.
- 로컬 실험 경로(`STT_PROVIDER=vosk`, `LLM_PROVIDER=llama`, `TTS_PROVIDER=espeak`)가 실패하면 즉시 플로우를 숨기지 않고 오류 사유를 화면에 유지한다.
- 로컬 실험 경로가 막혔을 때 운영 fallback은 `STT_PROVIDER=groq`, `LLM_PROVIDER=groq`, `TTS_PROVIDER=edge` 기본 운영 경로로 되돌린 뒤 재검증하는 것이다.
- STT 결과가 비어 있으면 최근 녹음 재생으로 실제 입력 유입 여부를 먼저 확인한다.

## 현재 성능 최적화 메모

아래 항목은 로컬 실험 경로 기준 최적화 메모다.

1. `Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` 사용
2. `rock3c-llm.service` 로 `llama-server` 상주시킴
3. 웹 앱 시작 시 `Vosk` 모델 preload
4. TTS는 비동기 재생

최근 측정 기준:

- 이전 total: 약 `61.9s`
- 현재 total: 약 `36.6s`

여전히 가장 큰 병목은:

1. `stt_ms`
2. `llm_ms`

즉, 현재 구조에서 속도를 더 줄이려면 다음 단계는 `STT` 경량화 또는 더 작은 LLM으로 추가 하향이다.

## 상시 대기 실행

항상 대기하면서 듣고 응답하게 하려면 아래 스크립트를 사용한다.

```bash
/home/radxa/voice-chat/scripts/run_voice_assistant.sh
```

또는 systemd 서비스:

```bash
sudo cp /home/radxa/voice-chat/systemd/rock3c-voice-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rock3c-voice-assistant.service
```

로그 확인:

```bash
tail -f /home/radxa/voice-chat/logs/voice-assistant.log
```

기본 웹 UI 로그는 systemd/journalctl 기준으로 먼저 확인한다.

```bash
sudo journalctl -u rock3c-voice-web.service -n 100 --no-pager
```

## 성공 기준

- 마이크 입력이 파일 또는 스트림으로 캡처됨
- 기본 운영 경로 또는 로컬 실험 경로 중 하나에서 응답이 생성됨
- 응답이 음성으로 재생됨
- 락카키 시스템과 별도 프로세스로 충돌 없이 동작함
