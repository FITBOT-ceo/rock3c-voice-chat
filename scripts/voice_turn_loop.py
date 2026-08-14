import argparse
import asyncio
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path("/home/radxa/voice-chat")
DEFAULT_ALSA_INPUT = "plughw:2,0"
DEFAULT_PULSE_SINK = "alsa_output.platform-rk809-sound.HiFi__hw_rockchiprk809__sink"
STT_MODEL = "whisper-large-v3-turbo"
LLM_MODEL = "llama-3.3-70b-versatile"
STT_PROVIDER = os.environ.get("STT_PROVIDER", "groq").strip().lower()
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").strip().lower()
VOSK_MODEL_PATH = Path(os.environ.get("VOSK_MODEL_PATH", str(ROOT / "models" / "vosk-model-small-ko-0.22")))
LLAMA_SERVER_URL = os.environ.get("LLAMA_SERVER_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_SERVER_MODEL = os.environ.get("LLAMA_SERVER_MODEL", "local-model")

# TTS 설정 (환경변수로 전환)
# TTS_PROVIDER: espeak | edge | elevenlabs
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "edge")
EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "ko-KR-SunHiNeural")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

_groq_client = None
_vosk_model = None


def _runtime_mode_label() -> str:
    if STT_PROVIDER == "groq" and LLM_PROVIDER == "groq":
        return "기본 운영 경로"
    if STT_PROVIDER == "vosk" and LLM_PROVIDER == "llama":
        return "로컬 실험 경로"
    return "혼합 검증 경로"


def _client():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
        except ImportError as exc:
            raise RuntimeError("groq 패키지가 설치되지 않았습니다.") from exc
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY 환경변수가 설정되지 않았습니다.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _normalize_provider(kind: str, provider: str, allowed: set[str]) -> str:
    if provider not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise RuntimeError(f"{kind}_PROVIDER 값이 올바르지 않습니다: {provider} (허용: {allowed_text})")
    return provider


def _load_vosk_model():
    global _vosk_model
    if _vosk_model is None:
        if not VOSK_MODEL_PATH.exists():
            raise RuntimeError(f"VOSK_MODEL_PATH 경로를 찾을 수 없습니다: {VOSK_MODEL_PATH}")
        try:
            from vosk import Model
        except ImportError as exc:
            raise RuntimeError("vosk 패키지가 설치되지 않았습니다.") from exc
        _vosk_model = Model(str(VOSK_MODEL_PATH))
    return _vosk_model


def _transcribe_groq(wav_path: Path) -> str:
    with open(wav_path, "rb") as f:
        result = _client().audio.transcriptions.create(
            file=(wav_path.name, f, "audio/wav"),
            model=STT_MODEL,
            language="ko",
            response_format="text",
        )
    text = result if isinstance(result, str) else result.text
    return text.strip()


def _transcribe_vosk(wav_path: Path) -> str:
    try:
        from vosk import KaldiRecognizer
    except ImportError as exc:
        raise RuntimeError("vosk 패키지가 설치되지 않았습니다.") from exc

    model = _load_vosk_model()
    with wave.open(str(wav_path), "rb") as wav_file:
        if wav_file.getnchannels() != 1:
            raise RuntimeError("Vosk STT는 mono WAV 입력이 필요합니다.")
        if wav_file.getsampwidth() != 2:
            raise RuntimeError("Vosk STT는 16-bit WAV 입력이 필요합니다.")
        recognizer = KaldiRecognizer(model, wav_file.getframerate())
        recognizer.SetWords(False)
        while True:
            chunk = wav_file.readframes(4000)
            if not chunk:
                break
            recognizer.AcceptWaveform(chunk)
        result = json.loads(recognizer.FinalResult())
    return (result.get("text") or "").strip()


def transcribe_ko(wav_path: Path) -> str:
    provider = _normalize_provider("STT", STT_PROVIDER, {"groq", "vosk"})
    if provider == "vosk":
        return _transcribe_vosk(wav_path)
    return _transcribe_groq(wav_path)


def _ping_llama_server() -> None:
    req = urllib.request.Request(f"{LLAMA_SERVER_URL}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3):
            return
    except Exception as health_exc:
        tags_req = urllib.request.Request(f"{LLAMA_SERVER_URL}/v1/models", method="GET")
        try:
            with urllib.request.urlopen(tags_req, timeout=3):
                return
        except Exception as models_exc:
            raise RuntimeError(
                f"로컬 LLM 서버에 연결할 수 없습니다: {LLAMA_SERVER_URL}"
            ) from models_exc


def preload_runtime() -> None:
    """Validate required runtime configuration at web app startup."""
    _normalize_provider("STT", STT_PROVIDER, {"groq", "vosk"})
    _normalize_provider("LLM", LLM_PROVIDER, {"groq", "llama"})
    _normalize_provider("TTS", TTS_PROVIDER, {"edge", "elevenlabs", "espeak"})
    if STT_PROVIDER == "groq" or LLM_PROVIDER == "groq":
        _client()
    if STT_PROVIDER == "vosk":
        _load_vosk_model()
    if LLM_PROVIDER == "llama":
        _ping_llama_server()
    if TTS_PROVIDER == "elevenlabs" and not os.environ.get("ELEVENLABS_API_KEY", ""):
        raise RuntimeError("ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")


def runtime_config_details() -> dict:
    checks = []
    if STT_PROVIDER == "groq":
        checks.append("STT는 GROQ_API_KEY가 필요합니다.")
    else:
        checks.append(f"STT는 Vosk 모델 디렉터리가 필요합니다: {VOSK_MODEL_PATH}")

    if LLM_PROVIDER == "groq":
        checks.append("LLM은 GROQ_API_KEY가 필요합니다.")
    else:
        checks.append(f"LLM은 llama-server가 먼저 떠 있어야 합니다: {LLAMA_SERVER_URL}")

    if TTS_PROVIDER == "elevenlabs":
        checks.append("TTS는 ELEVENLABS_API_KEY가 필요합니다.")
    elif TTS_PROVIDER == "espeak":
        checks.append("TTS는 espeak-ng 실행 파일이 필요합니다.")
    else:
        checks.append("TTS는 edge-tts와 ffmpeg가 필요합니다.")

    return {
        "mode": _runtime_mode_label(),
        "summary": runtime_config_summary(),
        "providers": {
            "stt": STT_PROVIDER,
            "llm": LLM_PROVIDER,
            "tts": TTS_PROVIDER,
        },
        "checks": checks,
        "llama_server_url": LLAMA_SERVER_URL,
        "vosk_model_path": str(VOSK_MODEL_PATH),
    }


def runtime_config_summary() -> str:
    return f"STT={STT_PROVIDER}, LLM={LLM_PROVIDER}, TTS={TTS_PROVIDER}"


def _ask_llm_groq(messages: list[dict[str, str]]) -> str:
    response = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=150,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def _ask_llm_llama(messages: list[dict[str, str]]) -> str:
    payload = json.dumps(
        {
            "model": LLAMA_SERVER_MODEL,
            "messages": messages,
            "max_tokens": 150,
            "temperature": 0.3,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{LLAMA_SERVER_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"로컬 LLM 응답 요청에 실패했습니다: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"로컬 LLM 서버에 연결할 수 없습니다: {LLAMA_SERVER_URL}") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("로컬 LLM 응답에 choices가 없습니다.")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("로컬 LLM 응답 본문이 비어 있습니다.")
    return content


def ask_llm(user_text: str, history: list = None) -> str:
    messages = [{"role": "system", "content": (
        "당신은 헬스장 카운터 직원입니다. "
        "회원들에게 항상 친근하고 밝게 대화하세요. "
        "운동, 식단, 헬스 관련 질문에는 전문 지식을 바탕으로 구체적이고 실용적으로 답하세요. "
        "헬스와 무관한 일상 대화에도 따뜻하게 응대하세요. "
        "답변은 반드시 한국어로, 최대 3문장 이내로 간결하게 답하세요."
    )}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    provider = _normalize_provider("LLM", LLM_PROVIDER, {"groq", "llama"})
    if provider == "llama":
        return _ask_llm_llama(messages)
    return _ask_llm_groq(messages)


def ask_gemma(user_text: str) -> str:
    return ask_llm(user_text)


# ── TTS: espeak-ng (로컬, 로봇 목소리) ───────────────────────────────────────

def speak_ko_espeak(text: str, sink: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        with wav_path.open("wb") as out_f:
            subprocess.run(["espeak-ng", "-v", "ko", text, "--stdout"], check=True, stdout=out_f)
        _paplay(wav_path, sink)
    finally:
        wav_path.unlink(missing_ok=True)


# ── TTS: edge-tts (무료 클라우드, Microsoft) ─────────────────────────────────

async def _edge_generate(text: str, path: Path, voice: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(path))


def speak_edge(text: str, sink: str, voice: str = None) -> None:
    v = voice or EDGE_TTS_VOICE
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3_path = Path(tmp.name)
    wav_path = mp3_path.with_suffix(".wav")
    try:
        asyncio.run(_edge_generate(text, mp3_path, v))
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "22050", str(wav_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _paplay(wav_path, sink)
    finally:
        mp3_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


# ── TTS: ElevenLabs (무료 10,000자/월) ───────────────────────────────────────

def speak_elevenlabs(text: str, sink: str, voice_id: str = None) -> None:
    from elevenlabs import ElevenLabs
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다.")
    vid = voice_id or ELEVENLABS_VOICE_ID
    client = ElevenLabs(api_key=api_key)
    audio_gen = client.text_to_speech.convert(
        text=text,
        voice_id=vid,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        mp3_path = Path(tmp.name)
    wav_path = mp3_path.with_suffix(".wav")
    try:
        with open(mp3_path, "wb") as f:
            for chunk in audio_gen:
                if chunk:
                    f.write(chunk)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3_path), "-ar", "22050", str(wav_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        _paplay(wav_path, sink)
    finally:
        mp3_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


# ── 디스패처 ─────────────────────────────────────────────────────────────────

def _paplay(wav_path: Path, sink: str) -> None:
    subprocess.run(["pactl", "set-default-sink", sink], check=False)
    subprocess.run(["pactl", "set-sink-mute", sink, "0"], check=False)
    subprocess.run(["pactl", "set-sink-volume", sink, "100%"], check=False)
    subprocess.run(["paplay", str(wav_path)], check=True)


def speak_tts(text: str, sink: str) -> None:
    provider = TTS_PROVIDER
    if provider == "edge":
        speak_edge(text, sink)
    elif provider == "elevenlabs":
        speak_elevenlabs(text, sink)
    else:
        speak_ko_espeak(text, sink)


# ── CLI 유틸 ──────────────────────────────────────────────────────────────────

def record_wav(output_path: Path, device: str, seconds: int, sample_rate: int) -> None:
    subprocess.run(
        ["arecord", "-D", device, "-f", "S16_LE", "-r", str(sample_rate), "-c", "1", "-d", str(seconds), str(output_path)],
        check=True,
    )


def run_once(seconds: int, input_device: str, sink: str, sample_rate: int) -> bool:
    temp_wav = Path("/tmp/rock3c_voice_turn.wav")
    print("[1/4] Recording...")
    record_wav(temp_wav, input_device, seconds, sample_rate)
    print(f"[2/4] Transcribing ({STT_PROVIDER})...")
    text = transcribe_ko(temp_wav)
    print(f"[STT] {text or '(empty)'}")
    if not text:
        return False
    print(f"[3/4] LLM ({LLM_PROVIDER})...")
    reply = ask_llm(text)
    print(f"[LLM] {reply}")
    print(f"[4/4] Speaking ({TTS_PROVIDER})...")
    speak_tts(reply, sink)
    print("Done.")
    return True


def loop_forever(seconds: int, input_device: str, sink: str, sample_rate: int, idle_sleep: float, speak_cooldown: float) -> None:
    print(f"Voice assistant loop started. (TTS: {TTS_PROVIDER})")
    while True:
        try:
            handled = run_once(seconds, input_device, sink, sample_rate)
            if handled:
                time.sleep(speak_cooldown)
            else:
                time.sleep(idle_sleep)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[ERROR] {exc}")
            time.sleep(2.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-turn voice chat on Rock 3C")
    parser.add_argument("--seconds", type=int, default=5)
    parser.add_argument("--input-device", default=DEFAULT_ALSA_INPUT)
    parser.add_argument("--sink", default=DEFAULT_PULSE_SINK)
    parser.add_argument("--sample-rate", type=int, default=16000)
    args = parser.parse_args()
    ok = run_once(args.seconds, args.input_device, args.sink, args.sample_rate)
    if not ok:
        raise SystemExit("No speech recognized.")


if __name__ == "__main__":
    main()
