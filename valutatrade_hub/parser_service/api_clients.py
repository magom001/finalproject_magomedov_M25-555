"""HTTP-клиенты для получения курсов из внешних источников."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from ..core.exceptions import ApiRequestError
from .config import ParserConfig


def _utc_now_iso() -> str:
    """Вернуть текущую отметку времени UTC в формате ISO-8601."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_timestamp(raw_value: Optional[str]) -> str:
    if not raw_value:
        return _utc_now_iso()

    try:
        parsed = datetime.strptime(raw_value, "%a, %d %b %Y %H:%M:%S %z")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return raw_value


@dataclass
class RateSample:
    """Нормализованная запись курсa, полученного от внешнего API."""

    from_currency: str
    to_currency: str
    rate: float
    source: str
    timestamp: str
    meta: Dict[str, Any]
    raw_id: Optional[str] = None

    @property
    def pair(self) -> str:
        return f"{self.from_currency}_{self.to_currency}"


class BaseApiClient(ABC):
    """Абстрактный базовый класс для HTTP-клиентов."""

    def __init__(self, config: ParserConfig):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Вернуть человеко-понятное название источника."""

    @abstractmethod
    def fetch_rates(self) -> List[RateSample]:
        """Получить курсы и вернуть их в нормализованном виде."""


class CoinGeckoClient(BaseApiClient):
    """Клиент для эндпоинта CoinGecko Simple Price."""

    @property
    def name(self) -> str:  # pragma: no cover - simple property
        return "CoinGecko"

    def fetch_rates(self) -> List[RateSample]:
        params = self.config.coingecko_params()
        request_url = self.config.coingecko_url

        try:
            started = time.perf_counter()
            response = requests.get(
                request_url,
                params=params,
                timeout=self.config.request_timeout,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
        except (
            requests.exceptions.RequestException
        ) as exc:  # pragma: no cover - network
            raise ApiRequestError(f"{self.name}: {exc}") from exc

        if response.status_code != 200:
            raise ApiRequestError(
                f"{self.name}: HTTP {response.status_code} при обращении к API"
            )

        payload = response.json()
        base_key = self.config.base_currency.lower()
        timestamp = _utc_now_iso()

        samples: List[RateSample] = []

        for code in self.config.crypto_currencies:
            asset_id = self.config.crypto_id_map.get(code)
            if not asset_id:
                continue

            asset_info = payload.get(asset_id)
            if not isinstance(asset_info, dict):
                continue

            rate_value = asset_info.get(base_key)
            if not isinstance(rate_value, (int, float)):
                continue

            meta = {
                "raw_id": asset_id,
                "status_code": response.status_code,
                "request_ms": elapsed_ms,
            }
            if etag := response.headers.get("ETag"):
                meta["etag"] = etag

            samples.append(
                RateSample(
                    from_currency=code,
                    to_currency=self.config.base_currency,
                    rate=float(rate_value),
                    source=self.name,
                    timestamp=timestamp,
                    meta=meta,
                    raw_id=asset_id,
                )
            )

        return samples


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для сервиса ExchangeRate-API."""

    @property
    def name(self) -> str:  # pragma: no cover - simple property
        return "ExchangeRate-API"

    def _build_url(self) -> str:
        api_key = self.config.exchangerate_api_key
        if not api_key:
            raise ApiRequestError(
                "ExchangeRate-API: отсутствует API ключ. "
                "Добавьте EXCHANGERATE_API_KEY в .env"
            )
        return (
            f"{self.config.exchangerate_api_url}/{api_key}/latest/"
            f"{self.config.base_currency}"
        )

    def fetch_rates(self) -> List[RateSample]:
        request_url = self._build_url()

        try:
            started = time.perf_counter()
            response = requests.get(request_url, timeout=self.config.request_timeout)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
        except (
            requests.exceptions.RequestException
        ) as exc:  # pragma: no cover - network
            raise ApiRequestError(f"{self.name}: {exc}") from exc

        if response.status_code != 200:
            raise ApiRequestError(
                f"{self.name}: HTTP {response.status_code} при обращении к API"
            )

        payload = response.json()
        if payload.get("result") != "success":
            error_type = payload.get("error-type", "unknown")
            raise ApiRequestError(
                f"{self.name}: ответ API содержит ошибку {error_type}"
            )

        rates_section = payload.get("conversion_rates")
        if not isinstance(rates_section, dict):
            raise ApiRequestError(
                f"{self.name}: неожиданный формат поля 'conversion_rates'"
            )

        timestamp = _normalize_timestamp(payload.get("time_last_update_utc"))

        samples: List[RateSample] = []
        base_currency = self.config.base_currency

        for code in self.config.fiat_currencies:
            rate_value = rates_section.get(code)
            if not isinstance(rate_value, (int, float)):
                continue

            if rate_value == 0:
                continue

            meta = {
                "status_code": response.status_code,
                "request_ms": elapsed_ms,
            }

            inverse_rate = 1.0 / float(rate_value)

            samples.append(
                RateSample(
                    from_currency=code,
                    to_currency=base_currency,
                    rate=inverse_rate,
                    source=self.name,
                    timestamp=timestamp,
                    meta=meta,
                )
            )

        return samples
