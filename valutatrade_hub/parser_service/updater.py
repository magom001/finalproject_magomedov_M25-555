"""Координатор получения и сохранения курсов валют."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from ..core.exceptions import ApiRequestError
from ..infra.logging_config import get_parser_logger
from .api_clients import BaseApiClient, RateSample
from .config import ParserConfig
from .storage import RatesStorage


def _iso_to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _best_timestamp(samples: List[RateSample]) -> Optional[str]:
    if not samples:
        return None
    timestamps = [s.timestamp for s in samples if s.timestamp]
    if not timestamps:
        return None
    newest = max(timestamps)
    return newest


@dataclass
class UpdateResult:
    updated_pairs: List[str]
    errors: List[Dict[str, str]]
    last_refresh: Optional[str]
    source_stats: Dict[str, int]


class RatesUpdater:
    """Получает курсы у поставщиков и сохраняет их через `RatesStorage`."""

    def __init__(
        self,
        clients: Iterable[BaseApiClient],
        storage: RatesStorage,
        config: ParserConfig,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.clients = list(clients)
        self.storage = storage
        self.config = config
        self.logger = logger or get_parser_logger()

    def run_update(self, source_filter: Optional[str] = None) -> UpdateResult:
        if source_filter:
            allowed = source_filter.lower()
            active_clients = [c for c in self.clients if c.name.lower() == allowed]
        else:
            active_clients = self.clients

        if not active_clients:
            raise ApiRequestError("Нет доступных источников для обновления курсов")

        self.logger.info(
            "Старт обновления курсов (источники=%s)",
            ",".join(c.name for c in active_clients),
        )

        aggregated_samples: List[RateSample] = []
        errors: List[Dict[str, str]] = []
        source_stats: Dict[str, int] = {}

        for client in active_clients:
            try:
                samples = client.fetch_rates()
                aggregated_samples.extend(samples)
                self.logger.info("Получено %d записей от %s", len(samples), client.name)
                source_stats[client.name] = len(samples)
            except ApiRequestError as exc:
                errors.append({"source": client.name, "message": exc.detail})
                self.logger.error(
                    "Не удалось получить данные от %s: %s", client.name, exc.detail
                )
                source_stats[client.name] = 0

        if not aggregated_samples and errors:
            raise ApiRequestError("Не удалось получить курсы ни от одного источника")

        snapshot = self.storage.load_snapshot()
        pairs_snapshot = snapshot.get("pairs", {})
        merged_pairs: Dict[str, Dict[str, Any]] = {
            key: value.copy() if isinstance(value, dict) else {}
            for key, value in pairs_snapshot.items()
        }

        history_records: List[Dict[str, str]] = []
        updated_pairs: List[str] = []

        for sample in aggregated_samples:
            pair_key = sample.pair
            current_entry = merged_pairs.get(pair_key, {})
            current_ts = _iso_to_datetime(current_entry.get("updated_at"))
            sample_ts = _iso_to_datetime(sample.timestamp) or datetime.now(timezone.utc)

            if not current_ts or sample_ts >= current_ts:
                merged_pairs[pair_key] = {
                    "rate": sample.rate,
                    "updated_at": sample.timestamp,
                    "source": sample.source,
                }
                if pair_key not in updated_pairs:
                    updated_pairs.append(pair_key)

            sample_meta = dict(sample.meta) if sample.meta else {}
            if sample.raw_id is not None:
                sample_meta.setdefault("raw_id", sample.raw_id)

            history_records.append(
                {
                    "id": (
                        f"{sample.from_currency}_{sample.to_currency}_"
                        f"{sample.timestamp}"
                    ),
                    "from_currency": sample.from_currency,
                    "to_currency": sample.to_currency,
                    "rate": sample.rate,
                    "timestamp": sample.timestamp,
                    "source": sample.source,
                    "meta": sample_meta,
                }
            )

        last_refresh = _best_timestamp(aggregated_samples)
        if last_refresh is None:
            last_refresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        self.storage.write_snapshot(merged_pairs, last_refresh)
        self.storage.append_history(history_records)

        self.logger.info(
            "Обновление завершено: сохранено %d пар, ошибок: %d",
            len(updated_pairs),
            len(errors),
        )

        return UpdateResult(
            updated_pairs=updated_pairs,
            errors=errors,
            last_refresh=last_refresh,
            source_stats=source_stats,
        )
