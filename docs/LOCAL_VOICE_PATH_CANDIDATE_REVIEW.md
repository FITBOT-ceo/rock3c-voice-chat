# 로컬 음성 경로 기본 실행 후보 검증 메모

## 1. 목적
현재 Rock 3C 음성 웹 런타임에서 Groq 기본 경로 대신 로컬 STT·LLM·TTS 경로를 기본 실행 후보로 올릴 수 있는지 코드와 문서 기준으로 정리한다.

## 2. 현재 결론
- 결론: 비교 검증 단계까지는 진입했지만, 아직 기본 실행 후보로 승격하기는 이르다.
- 이유 1: 웹 UI에서 provider 분기와 점검 메시지는 보이지만 기본 서비스 값은 여전히 Groq 경로다.
- 이유 2: 로컬 LLM 서버와 로컬 STT는 통합됐지만, 실기기 장시간 안정성 검증은 아직 없다.
- 이유 3: 실기기 기준 지연, 오디오 장치 복구력, 음질 수용 여부는 여전히 사람 검증이 필요하다.

## 3. 현재 웹 런타임의 실제 설정 지점

| 구분 | 현재 상태 | 코드/파일 |
|------|-----------|-----------|
| 웹 앱 진입점 | Flask 웹 UI | `web_ui/app.py` |
| STT 호출 | Groq Whisper 고정 | `scripts/voice_turn_loop.py`의 `transcribe_ko()` |
| LLM 호출 | Groq Chat 고정 | `scripts/voice_turn_loop.py`의 `ask_llm()` |
| TTS 전환 | 가능 (`edge`, `elevenlabs`, `espeak`) | `scripts/voice_turn_loop.py`의 `TTS_PROVIDER`, `speak_tts()` |
| 웹 서비스 환경 변수 | `GROQ_API_KEY`, `TTS_PROVIDER=edge`만 실사용 | `systemd/rock3c-voice-web.service` |
| 로컬 LLM 서버 | 별도 준비됨 | `scripts/run_llama_server.sh`, `systemd/rock3c-llm.service` |

## 4. 로컬 경로를 켜기 위해 필요한 실제 전환 지점

### 4.1 STT
- 현재 `STT_PROVIDER`는 `groq`와 `vosk`를 분기한다.
- `transcribe_ko()`는 Groq Whisper와 Vosk를 환경 변수로 나눠 호출한다.
- 웹 앱 시작 시 `VOSK_MODEL_PATH` preload와 실패 메시지 노출도 들어가 있다.
- 남은 과제는 실제 마이크 환경에서 인식률과 지연을 반복 검증하는 것이다.

### 4.2 LLM
- 현재 `LLM_PROVIDER`는 `groq`와 `llama`를 분기한다.
- `ask_llm()`은 Groq Chat과 로컬 `llama-server` HTTP 경로를 환경 변수로 나눠 호출한다.
- 로컬 서버 미기동 시에는 웹 UI가 점검 실패 상태와 오류 메시지를 표시한다.
- 남은 과제는 장시간 연속 질의에서 속도 저하와 메모리 여유를 재확인하는 것이다.

### 4.3 TTS
- TTS는 `TTS_PROVIDER`로 `edge`, `elevenlabs`, `espeak` 전환이 가능하다.
- 로컬 기본 후보 관점에서는 `espeak`가 가장 단순하고 외부 의존이 없다.
- 다만 음질은 `edge-tts`보다 낮으므로 운영 기본값 전환 시 사용자 체감 검증이 필요하다.

## 5. Groq 기본 경로와 로컬 경로 비교

| 항목 | Groq 기본 경로 | 로컬 경로 후보 |
|------|----------------|----------------|
| STT | 정확도와 편의성이 높음, 네트워크 필요 | Vosk 사용 가능, 네트워크 불필요, 정확도/속도 재검증 필요 |
| LLM | 응답 품질 높음, API 의존 | Qwen 1.5B 로컬 가능, 속도와 품질 타협 필요 |
| TTS | `edge-tts` 음질 우수, 네트워크 의존 | `espeak-ng` 즉시 사용 가능, 음질 열세 |
| 외부 의존성 | API 키와 인터넷 필요 | 인터넷 의존성 낮음 |
| 장애 격리 | 외부 API 장애 영향 큼 | 장치 자체 성능과 설정에 더 민감 |
| 현재 코드 완성도 | 웹 UI에 이미 반영됨 | 실험 조각은 있으나 웹 경로 통합 미완료 |
| 운영 준비도 | 높음 | 중간 이하 |

## 6. 병목, 장점, 남은 리스크

| 구분 | 내용 |
|------|------|
| 장점 | 인터넷 없이 동작 가능, API 비용 없음, 목표 아키텍처와 일치 |
| 장점 | `llama.cpp` 상주형, Vosk preload, 비동기 TTS 방향이 이미 문서화되어 있음 |
| 병목 | 최근 측정에서도 `stt_ms`, `llm_ms`가 전체 지연의 대부분을 차지함 |
| 병목 | 8GB 보드에서 로컬 LLM 상주시 메모리와 장시간 안정성 여유가 크지 않음 |
| 리스크 | 웹 UI 코드에 provider 분기가 없어 문서와 실제 동작이 어긋남 |
| 리스크 | 로컬 STT 결과 품질이 입력 볼륨, 마이크 위치, 주변 소음에 크게 좌우될 수 있음 |
| 리스크 | `espeak-ng` 음질이 안내/상담 시나리오에서 충분한지 아직 미확인 |

## 7. 기본 실행 후보 승격 조건

### 코드만으로 닫을 수 있는 항목
- [x] `STT_PROVIDER` 분기 구현
- [x] `LLM_PROVIDER` 분기 구현
- [x] 웹 앱 시작 시 로컬 경로 필수 구성요소 점검 추가
- [x] Groq 기본값과 로컬 기본값을 서비스 유닛/문서에서 명확히 분리
- [ ] 로컬 경로 실패 시 오류 메시지와 fallback 동작 정의

### 사람 실기기 검증이 필요한 항목
- [ ] 실제 마이크 거리와 주변 소음에서 Vosk 한국어 인식률 확인
- [ ] 실제 스피커 볼륨과 `espeak-ng` 음질의 수용 가능 여부 확인
- [ ] 10회 이상 연속 질의에서 발열, 메모리, 지연 악화 여부 확인
- [ ] 네트워크 단절 상태에서 장시간 반복 사용 안정성 확인
- [ ] 장치 재부팅 후 systemd 서비스 자동 복구 확인

## 8. 권장 판단
- 지금 단계에서는 Groq 웹 경로를 기본값으로 유지하는 편이 안전하다.
- 다만 로컬 경로는 목표 아키텍처와 부합하고, 이미 실험 자산이 있으므로 다음 단계의 1순위는 웹 UI에 provider 분기를 붙여 동일 UI에서 비교 검증 가능하게 만드는 것이다.
- 위 코드 통합이 끝나고 실기기 체크리스트가 통과되면 그때 로컬 경로를 기본 실행 후보로 재평가하는 것이 적절하다.

## 9. 참고 파일
- `README.md`
- `docs/VOICE_CHAT_SETUP.md`
- `docs/VOICE_CHAT_RUNBOOK.md`
- `web_ui/app.py`
- `scripts/voice_turn_loop.py`
- `systemd/rock3c-voice-web.service`
- `scripts/run_llama_server.sh`
