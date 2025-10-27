"""Простое периодическое расписание для запуска обновления курсов."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from ..core.exceptions import ApiRequestError
from .updater import RatesUpdater


@dataclass
class UpdateScheduler:
    updater: RatesUpdater
    interval_seconds: int
    logger: Optional[logging.Logger] = None

    def __post_init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join()
        self._thread = None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.updater.run_update()
                if self.logger:
                    self.logger.info("Плановое обновление завершено")
            except ApiRequestError as exc:  # pragma: no cover - background path
                if self.logger:
                    self.logger.error(
                        "Плановое обновление завершилось с ошибкой: %s", exc.detail
                    )
            self._stop_event.wait(self.interval_seconds)
