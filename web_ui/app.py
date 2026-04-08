import json
import subprocess
import threading
import time
import uuid
import sys
import shutil
from pathlib import Path

from flask import Flask, jsonify, render_template, request


ROOT = Path("/home/radxa/voice-chat")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.voice_turn_loop import ask_gemma, preload_vosk_model, speak_ko_espeak, transcribe_ko

UPLOAD_DIR = ROOT / "uploads"
LOG_LIMIT = 50
DEBUG_RAW_PATH = UPLOAD_DIR / "latest_input.webm"
DEBUG_WAV_PATH = UPLOAD_DIR / "latest_input.wav"
OUTPUT_SINK = "alsa_output.platform-rk809-sound.HiFi__hw_rockchiprk809__sink"

app = Flask(__name__, template_folder="templates", static_folder="static")
conversation_log = []
log_lock = threading.Lock()


def add_log(role: str, text: str) -> None:
    with log_lock:
        conversation_log.append(
            {
                "id": str(uuid.uuid4()),
                "role": role,
                "text": text,
                "timestamp": int(time.time()),
            }
        )
        del conversation_log[:-LOG_LIMIT]


def get_logs():
    with log_lock:
        return list(conversation_log)


def convert_audio_to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(dst),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def probe_audio_file(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0] if data.get("streams") else {}
    fmt = data.get("format", {})
    return {
        "path": str(path),
        "duration": float(fmt.get("duration", 0) or 0),
        "size": int(fmt.get("size", 0) or 0),
        "codec": stream.get("codec_name"),
        "sample_rate": stream.get("sample_rate"),
        "channels": stream.get("channels"),
    }


def play_wav(path: Path) -> None:
    subprocess.run(["pactl", "set-default-sink", OUTPUT_SINK], check=False)
    subprocess.run(["pactl", "set-sink-mute", OUTPUT_SINK, "0"], check=False)
    subprocess.run(["pactl", "set-sink-volume", OUTPUT_SINK, "100%"], check=False)
    subprocess.run(["paplay", str(path)], check=True)


def speak_async(text: str) -> None:
    thread = threading.Thread(target=speak_ko_espeak, args=(text, OUTPUT_SINK), daemon=True)
    thread.start()


@app.route("/")
def index():
    return render_template("voice_ui.html")


@app.route("/api/history")
def history():
    return jsonify({"ok": True, "messages": get_logs()})


@app.route("/api/debug/last-audio")
def last_audio_info():
    if not DEBUG_WAV_PATH.exists():
        return jsonify({"ok": False, "error": "최근 녹음 파일이 없습니다."}), 404
    return jsonify(
        {
            "ok": True,
            "wav": probe_audio_file(DEBUG_WAV_PATH),
            "webm": probe_audio_file(DEBUG_RAW_PATH) if DEBUG_RAW_PATH.exists() else None,
        }
    )


@app.route("/api/debug/play-last", methods=["POST"])
def play_last_audio():
    if not DEBUG_WAV_PATH.exists():
        return jsonify({"ok": False, "error": "최근 녹음 파일이 없습니다."}), 404
    try:
        play_wav(DEBUG_WAV_PATH)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"ok": False, "error": "오디오 파일이 없습니다."}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    request_id = str(uuid.uuid4())
    raw_path = UPLOAD_DIR / f"{request_id}.webm"
    wav_path = UPLOAD_DIR / f"{request_id}.wav"
    raw_path.write_bytes(audio_file.read())
    started_at = time.perf_counter()

    try:
        convert_started = time.perf_counter()
        convert_audio_to_wav(raw_path, wav_path)
        convert_ms = round((time.perf_counter() - convert_started) * 1000, 1)
        shutil.copyfile(raw_path, DEBUG_RAW_PATH)
        shutil.copyfile(wav_path, DEBUG_WAV_PATH)

        stt_started = time.perf_counter()
        user_text = transcribe_ko(wav_path)
        stt_ms = round((time.perf_counter() - stt_started) * 1000, 1)
        if not user_text:
            info = probe_audio_file(DEBUG_WAV_PATH)
            total_ms = round((time.perf_counter() - started_at) * 1000, 1)
            app.logger.warning(
                "VOICE_CHAT request_id=%s convert_ms=%s stt_ms=%s llm_ms=0 tts_ms=0 total_ms=%s result=empty_stt audio=%s",
                request_id,
                convert_ms,
                stt_ms,
                total_ms,
                info,
            )
            return jsonify({"ok": False, "error": "음성이 인식되지 않았습니다. 최근 녹음 재생으로 실제 입력을 확인해 주세요.", "audio_info": info, "timing": {"convert_ms": convert_ms, "stt_ms": stt_ms, "llm_ms": 0, "tts_ms": 0, "total_ms": total_ms}}), 422

        add_log("user", user_text)

        llm_started = time.perf_counter()
        reply = ask_gemma(user_text)
        llm_ms = round((time.perf_counter() - llm_started) * 1000, 1)
        add_log("assistant", reply)

        tts_started = time.perf_counter()
        speak_async(reply)
        tts_ms = round((time.perf_counter() - tts_started) * 1000, 1)
        total_ms = round((time.perf_counter() - started_at) * 1000, 1)
        timing = {
            "convert_ms": convert_ms,
            "stt_ms": stt_ms,
            "llm_ms": llm_ms,
            "tts_ms": tts_ms,
            "total_ms": total_ms,
        }
        app.logger.warning(
            "VOICE_CHAT request_id=%s convert_ms=%s stt_ms=%s llm_ms=%s tts_ms=%s total_ms=%s user_text=%r assistant_text=%r",
            request_id,
            convert_ms,
            stt_ms,
            llm_ms,
            tts_ms,
            total_ms,
            user_text,
            reply,
        )

        return jsonify(
            {
                "ok": True,
                "user_text": user_text,
                "assistant_text": reply,
                "audio_info": probe_audio_file(DEBUG_WAV_PATH),
                "timing": timing,
                "messages": get_logs(),
            }
        )
    except subprocess.CalledProcessError:
        return jsonify({"ok": False, "error": "오디오 변환에 실패했습니다."}), 500
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        raw_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)


def ensure_bootstrap_logs() -> None:
    if not get_logs():
        add_log("system", "음성 UI가 준비되었습니다. [녹음 시작]을 눌러 말한 뒤 [중지]를 누르세요.")
    preload_vosk_model()


if __name__ == "__main__":
    ensure_bootstrap_logs()
    app.run(host="0.0.0.0", port=5099, debug=False)
