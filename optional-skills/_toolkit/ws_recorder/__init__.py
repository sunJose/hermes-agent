"""Shared WebSocket recorder utilities for optional skills."""

from .ws_recorder import WSRecorder, build_ws_record, write_jsonl

__version__ = "0.1.0"

__all__ = ["WSRecorder", "build_ws_record", "write_jsonl"]
