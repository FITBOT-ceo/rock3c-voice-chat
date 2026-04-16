# 음성 파이프라인 레이턴시 베이스라인

## 목적

Rock 3C 음성 어시스턴트의 단계별 레이턴시를 일관되게 측정·기록·비교하기 위한 표준 절차.

## 측정 인프라

| 위치 | 역할 |
|---|---|
| `scripts/latency_logger.py` | `LatencyTimer` 컨텍스트 매니저 + JSONL append |
| `scripts/voice_turn_loop.py::run_once` | CLI 한 턴마다 자동 측정 |
| `web_ui/app.py::/api/chat` | 웹 요청마다 자동 측정 |
| `scripts/analyze_latency.py` | JSONL 로그 → 통계 (min/avg/p50/p95/max) |
| `artifacts/latency_log.jsonl` | append-only 측정 로그 (.gitignore 처리됨) |

## JSONL 레코드 형식

```json
{
  "ts": 1760000000,
  "request_id": "uuid",
  "source": "web|cli",
  "convert_ms": 693.7,
  "stt_ms": 17291.5,
  "llm_ms": 18573.7,
  "tts_ms": 0.9,
  "total_ms": 36566.8,
  "result": "ok|empty_stt",
  "tts_provider": "edge|elevenlabs|espeak",
  "stt_model": "whisper-large-v3-turbo",
  "llm_model": "llama-3.3-70b-versatile"
}
```

CLI 의 `record_ms` 는 사용자가 말한 시간 = `--seconds` 인자에 비례하므로 STT/LLM/TTS 비교에서 제외하는 것이 정상.

## 표준 측정 절차

1. **환경 고정**
   - `TTS_PROVIDER` 명시 (`export TTS_PROVIDER=edge`)
   - 같은 네트워크 (Groq API rtt 영향)
   - 같은 시간대 (Groq 부하 영향 최소화)
2. **20턴 이상 반복**
   - `bash scripts/run_voice_turn.sh` 또는 웹 UI 에서 동일 발화 20회
   - 동일 발화 권장: "안녕하세요" 또는 표준 문장
3. **분석**
   ```bash
   python3 scripts/analyze_latency.py --last 20
   ```

## 베이스라인 (TBD — 사람이 측정 후 채워넣을 영역)

> 아래는 측정 후 ZER-8 코멘트 또는 서브이슈에서 갱신.

| 단계 | min | avg | p50 | p95 | max | 비고 |
|---|---|---|---|---|---|---|
| convert_ms | - | - | - | - | - | webm→wav (web only) |
| stt_ms | - | - | - | - | - | Groq Whisper API rtt |
| llm_ms | - | - | - | - | - | Groq Llama 70B rtt |
| tts_ms | - | - | - | - | - | Edge TTS (async 시 ~0) |
| total_ms | - | - | - | - | - | 사용자 인지 응답 시간 |

마지막 README 기록 (이전 측정, 참고용):

| 단계 | 값 (ms) |
|---|---|
| convert_ms | 693.7 |
| stt_ms | 17291.5 |
| llm_ms | 18573.7 |
| tts_ms | 0.9 |
| total_ms | 36566.8 |

## 최적화 후보 (베이스라인 측정 후 사람이 우선순위 결정)

### STT
- Groq Whisper Large v3 Turbo → 더 빠른 모델 (`distil-whisper-large-v3-en` 은 한국어 미지원). 후보 부족.
- 클라이언트 측 VAD 로 끝점 감지 → 녹음 길이 단축 (가장 효과 큼).
- 서버측 streaming STT (Groq 미지원, faster-whisper 자체 호스팅 필요).

### LLM
- `llama-3.3-70b-versatile` → `llama-3.1-8b-instant` (Groq 동일 인프라, 5~10배 빠름).
- `max_tokens=150` → `100`.
- `messages` history 길이 단축 (현재 3턴 → 1~2턴).

### TTS
- 이미 async (`speak_async`) 라 `tts_ms ≈ 0`. 추가 최적화 불요.

### 네트워크
- Groq API 호출 2회 (STT + LLM). 한국에서 미국 rtt ~150ms × 2 = 300ms 하한.
- 자가 호스팅 LLM (Rock3C 로컬 Qwen) 으로 LLM rtt 제거 가능. 단 응답 지연 trade-off.

## 목표 재정의 필요 (ZER-8 본문)

ZER-8 본문 "현재 > 1s, 500ms 목표" 는 마지막 README 측정 (36초) 과 큰 괴리.
사람 검토 후 현실적 목표 (예: total_ms p50 < 3000ms) 로 재설정 필요. → 별도 [H] 서브이슈.
