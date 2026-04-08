# Voice Chat Runbook

## 목적

이 문서는 Rock 3C에서 로컬 음성 대화 스택이 실제로 도는지 검증할 때 쓰는 실행 절차를 정리한다.

## 현재 검증 완료 항목

### 오디오 입력

```bash
arecord -D plughw:2,0 -f S16_LE -r 16000 -c 1 -d 3 /tmp/rock3c_mic_test.wav
```

### 오디오 출력

```bash
speaker-test -D plughw:2,0 -c 2 -t sine -f 1000 -l 1
```

## 이후 추가할 검증 단계

1. STT 단독 실행 검증
2. Gemma 4 단독 추론 검증
3. TTS 단독 재생 검증
4. 전체 turn-based 파이프라인 검증

## 현재 완료된 검증

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

## 현재 권장 단일 턴 실행

```bash
/home/radxa/voice-chat/.venv/bin/python /home/radxa/voice-chat/project/rock3c/voice_chat/scripts/voice_turn_loop.py --seconds 5
```

동작 순서:

1. 5초 녹음
2. Vosk 한국어 인식
3. Gemma 4 응답 생성
4. eSpeak NG 한국어 음성 재생

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
4. 화면 로그에 사용자 문장과 Gemma 답변이 쌓인다.
5. 답변은 스피커로도 재생된다.

## 현재 성능 최적화 메모

현재 성능 개선을 위해 아래 구조를 적용했다.

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
sudo cp /home/radxa/voice-chat/project/rock3c/voice_chat/systemd/rock3c-voice-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rock3c-voice-assistant.service
```

로그 확인:

```bash
tail -f /home/radxa/voice-chat/logs/voice-assistant.log
```

## 성공 기준

- 마이크 입력이 파일 또는 스트림으로 캡처됨
- 로컬 모델이 응답을 생성함
- 응답이 음성으로 재생됨
- 락카키 시스템과 별도 프로세스로 충돌 없이 동작함
