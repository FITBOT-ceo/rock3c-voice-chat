"""artifacts/latency_log.jsonl 통계 분석.

Usage:
    python3 scripts/analyze_latency.py [--log path] [--last N]
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

STAGES = ["convert_ms", "stt_ms", "llm_ms", "tts_ms", "total_ms"]


def load_records(log_path: Path, last_n: int | None) -> list[dict]:
    if not log_path.exists():
        return []
    records = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if last_n:
        records = records[-last_n:]
    return records


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 1)


def summarize(records: list[dict]) -> dict:
    out = {"n": len(records), "stages": {}}
    for stage in STAGES:
        vals = [r[stage] for r in records if isinstance(r.get(stage), (int, float))]
        if not vals:
            continue
        out["stages"][stage] = {
            "min": round(min(vals), 1),
            "avg": round(statistics.mean(vals), 1),
            "p50": percentile(vals, 0.5),
            "p95": percentile(vals, 0.95),
            "max": round(max(vals), 1),
        }
    return out


def render_markdown(summary: dict) -> str:
    if summary["n"] == 0:
        return "측정 데이터 없음. (artifacts/latency_log.jsonl 비어있음)\n"
    lines = [f"# Latency Summary (n={summary['n']})", "", "| stage | min | avg | p50 | p95 | max |", "|---|---|---|---|---|---|"]
    for stage, s in summary["stages"].items():
        lines.append(f"| {stage} | {s['min']} | {s['avg']} | {s['p50']} | {s['p95']} | {s['max']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="/home/radxa/voice-chat/artifacts/latency_log.jsonl")
    parser.add_argument("--last", type=int, default=None, help="마지막 N개만 분석")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    records = load_records(Path(args.log), args.last)
    summary = summarize(records)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(summary))


if __name__ == "__main__":
    main()
