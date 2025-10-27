"""Вспомогательные классы для работы с JSON-файлами сервиса парсинга."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import ParserConfig


class RatesStorage:
    """Отвечает за чтение и запись артефактов сервиса парсинга."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.config.rates_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.history_file_path.parent.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, target: Path, payload: Any) -> None:
        temp_path = target.with_suffix(target.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
        temp_path.replace(target)

    def load_snapshot(self) -> Dict[str, Any]:
        if not self.config.rates_file_path.exists():
            return {"pairs": {}, "last_refresh": None}

        try:
            with open(self.config.rates_file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"pairs": {}, "last_refresh": None}

        if not isinstance(data, dict):
            return {"pairs": {}, "last_refresh": None}

        raw_pairs = data.get("pairs") if isinstance(data.get("pairs"), dict) else None

        if raw_pairs is None:
            raw_pairs = {}
            for key, value in data.items():
                if key == "last_refresh":
                    continue
                if isinstance(value, dict) and "rate" in value:
                    raw_pairs[key] = value

        return {
            "pairs": raw_pairs,
            "last_refresh": data.get("last_refresh"),
        }

    def write_snapshot(
        self, pairs: Dict[str, Any], last_refresh: Optional[str]
    ) -> None:
        payload = {key: value for key, value in pairs.items()}
        payload["last_refresh"] = last_refresh
        self._atomic_write(self.config.rates_file_path, payload)

    def load_history(self) -> List[Dict[str, Any]]:
        if not self.config.history_file_path.exists():
            return []

        try:
            with open(self.config.history_file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []

        if isinstance(data, list):
            return data

        return []

    def append_history(self, entries: Iterable[Dict[str, Any]]) -> None:
        records = list(entries)
        if not records:
            return

        history = self.load_history()
        existing_ids = {
            item.get("id")
            for item in history
            if isinstance(item, dict) and item.get("id")
        }

        for record in records:
            record_id = record.get("id")
            if record_id and record_id in existing_ids:
                continue
            history.append(record)
            if record_id:
                existing_ids.add(record_id)

        self._atomic_write(self.config.history_file_path, history)
