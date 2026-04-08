import argparse
import asyncio
import os
import subprocess
import tempfile
import time
from pathlib import Path

from groq import Groq

ROOT = Path("/home/radxa/voice-chat")
DEFAULT_ALSA_INPUT = "plughw:2,0"
DEFAULT_PULSE_SINK = "alsa_output.platform-rk809-sound.HiFi__hw_rockchiprk809__sink"
STT_MODEL = "whisper-large-v3-turbo"
LLM_MODEL = "llama-3.3-70b-versatile"

# TTS 설정 (환경변수로 전환)
# TTS_PROVIDER: espeak | edge | elevenlabs
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "edge")
EDGE_TTS_VOICE = os.environ.get("EDGE_TTS_VOICE", "ko-KR-SunHiNeural")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

_groq_client = None


def _client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY 환경변수가 설정되지 않았습니다.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def transcribe_ko(wav_path: Path) -> str:
    with open(wav_path, "rb") as f:
        result = _client().audio.transcriptions.create(
            file=(wav_path.name, f, "audio/wav"),
            model=STT_MODEL,
            language="ko",
            response_format="text",
        )
    text = result if isinstance(result, str) else result.text
    return text.strip()


def preload_vosk_model() -> None:
    pass


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
    response = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=150,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


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
    print("[2/4] Transcribing (Groq Whisper)...")
    text = transcribe_ko(temp_wav)
    print(f"[STT] {text or '(empty)'}")
    if not text:
        return False
    print(f"[3/4] LLM (Groq)...")
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
