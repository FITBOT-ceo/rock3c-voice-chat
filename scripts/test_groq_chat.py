#!/usr/bin/env python3
"""
Rock 3C Voice Chat E2E Test
- espeak-ng으로 테스트 문장 WAV 생성
- /api/chat에 POST → STT + LLM + TTS 전체 파이프라인 검증
- 타이밍, 응답 내용 기록
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path

import urllib.request

API_URL = "http://127.0.0.1:5099/api/chat"
HISTORY_URL = "http://127.0.0.1:5099/api/history"

TEST_PHRASES = [
    "오늘 기분이 어때요",
    "헬스장에서 어떤 운동을 하면 좋을까요",
    "방금 내가 뭐라고 했는지 기억해요",
]

BOUNDARY = "----TestBoundary7f3k"


def espeak_to_wav(text: str, wav_path: Path) -> None:
    subprocess.run(
        ["espeak-ng", "-v", "ko", "-s", "130", text, "-w", str(wav_path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def post_audio(wav_path: Path) -> dict:
    with open(wav_path, "rb") as f:
        audio_data = f.read()

    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="test.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + audio_data + f"\r\n--{BOUNDARY}--\r\n".encode()

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main():
    results = []
    print("=" * 60)
    print("Rock 3C Voice Chat E2E Test")
    print("=" * 60)

    for i, phrase in enumerate(TEST_PHRASES, 1):
        print(f"\n[{i}/{len(TEST_PHRASES)}] 테스트 문장: {phrase!r}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)

        try:
            # 1. 음성 생성
            t0 = time.perf_counter()
            espeak_to_wav(phrase, wav_path)
            tts_gen_ms = round((time.perf_counter() - t0) * 1000, 1)
            size_kb = round(wav_path.stat().st_size / 1024, 1)
            print(f"  TTS 생성: {tts_gen_ms}ms  ({size_kb}KB)")

            # 2. API 전송
            t1 = time.perf_counter()
            data = post_audio(wav_path)
            total_ms = round((time.perf_counter() - t1) * 1000, 1)

            if not data.get("ok"):
                print(f"  ERROR: {data.get('error')}")
                results.append({"phrase": phrase, "ok": False, "error": data.get("error")})
                continue

            timing = data.get("timing", {})
            print(f"  STT 인식: {data['user_text']!r}")
            print(f"  AI 응답:  {data['assistant_text']!r}")
            print(f"  타이밍:")
            print(f"    convert : {timing.get('convert_ms')}ms")
            print(f"    stt     : {timing.get('stt_ms')}ms")
            print(f"    llm     : {timing.get('llm_ms')}ms")
            print(f"    total   : {timing.get('total_ms')}ms")

            results.append({
                "phrase": phrase,
                "ok": True,
                "stt_result": data["user_text"],
                "llm_reply": data["assistant_text"],
                "timing": timing,
            })

        except Exception as e:
            print(f"  EXCEPTION: {e}")
            results.append({"phrase": phrase, "ok": False, "error": str(e)})
        finally:
            wav_path.unlink(missing_ok=True)

        time.sleep(0.5)

    # 최종 요약
    print("\n" + "=" * 60)
    print("최종 결과 요약")
    print("=" * 60)
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"성공: {ok_count}/{len(results)}")

    for r in results:
        status = "OK" if r.get("ok") else "FAIL"
        t = r.get("timing", {})
        total = t.get("total_ms", "-")
        stt = t.get("stt_ms", "-")
        llm = t.get("llm_ms", "-")
        print(f"  [{status}] {r['phrase']!r}")
        if r.get("ok"):
            print(f"         STT={stt}ms LLM={llm}ms Total={total}ms")
            print(f"         → {r['llm_reply']!r}")
        else:
            print(f"         오류: {r.get('error')}")

    # 대화 로그 전체 출력
    print("\n" + "=" * 60)
    print("대화 히스토리 (서버 기준)")
    print("=" * 60)
    req = urllib.request.Request(HISTORY_URL)
    with urllib.request.urlopen(req, timeout=10) as resp:
        hist = json.loads(resp.read().decode())
    for m in hist.get("messages", []):
        role_label = {"user": "나", "assistant": "AI", "system": "시스템"}.get(m["role"], m["role"])
        print(f"  [{role_label}] {m['text']}")


if __name__ == "__main__":
    main()
