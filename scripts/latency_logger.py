"""음성 파이프라인 단계별 레이턴시 측정 + JSONL 로깅.

web_ui/app.py 와 voice_turn_loop.py 가 공유하는 측정 헬퍼.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

DEFAULT_LOG_PATH = Path(
    os.environ.get(
        "ROCK3C_LATENCY_LOG",
        "/home/radxa/voice-chat/artifacts/latency_log.jsonl",
    )
)


class LatencyTimer:
    """한 턴(record→stt→llm→tts) 단계별 ms 측정."""

    def __init__(self, request_id: Optional[str] = None, source: str = "cli") -> None:
        self.request_id = request_id or str(uuid.uuid4())
        self.source = source
        self.started_at = time.perf_counter()
        self.stages: dict[str, float] = {}
        self.meta: dict[str, Any] = {}

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages[f"{name}_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    def set_meta(self, **kwargs: Any) -> None:
        self.meta.update(kwargs)

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started_at) * 1000, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts": int(time.time()),
            "request_id": self.request_id,
            "source": self.source,
            **self.stages,
            "total_ms": self.total_ms(),
            **self.meta,
        }

    def write(self, log_path: Path = DEFAULT_LOG_PATH) -> dict[str, Any]:
        return write_record(self.as_dict(), log_path)


def write_record(record: dict[str, Any], log_path: Path = DEFAULT_LOG_PATH) -> dict[str, Any]:
    """이미 측정된 dict 를 JSONL 로 append. (web_ui 처럼 자체 측정 코드가 있는 경로용)"""
    record.setdefault("ts", int(time.time()))
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return record
