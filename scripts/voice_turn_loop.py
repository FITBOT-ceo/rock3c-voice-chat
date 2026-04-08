import argparse
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
    # Groq 모드에서는 preload 불필요
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


# 하위 호환
def ask_gemma(user_text: str) -> str:
    return ask_llm(user_text)


def speak_ko_espeak(text: str, sink: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        with wav_path.open("wb") as out_f:
            subprocess.run(["espeak-ng", "-v", "ko", text, "--stdout"], check=True, stdout=out_f)
        subprocess.run(["pactl", "set-default-sink", sink], check=False)
        subprocess.run(["pactl", "set-sink-mute", sink, "0"], check=False)
        subprocess.run(["pactl", "set-sink-volume", sink, "100%"], check=False)
        subprocess.run(["paplay", str(wav_path)], check=True)
    finally:
        wav_path.unlink(missing_ok=True)


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
    print("[3/4] LLM (Groq)...")
    reply = ask_gemma(text)
    print(f"[LLM] {reply}")
    print("[4/4] Speaking...")
    speak_ko_espeak(reply, sink)
    print("Done.")
    return True


def loop_forever(seconds: int, input_device: str, sink: str, sample_rate: int, idle_sleep: float, speak_cooldown: float) -> None:
    print("Voice assistant loop started. (Groq backend)")
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
    parser = argparse.ArgumentParser(description="Single-turn voice chat on Rock 3C (Groq backend)")
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
