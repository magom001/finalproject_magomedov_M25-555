"""Конфигурационные объекты сервиса парсинга."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..infra.settings import SettingsLoader, get_settings

DEFAULT_FIAT_CURRENCIES: Tuple[str, ...] = ("EUR", "GBP", "RUB")
DEFAULT_CRYPTO_CURRENCIES: Tuple[str, ...] = ("BTC", "ETH", "SOL")
DEFAULT_CRYPTO_ID_MAP: Dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}


@dataclass(frozen=True)
class ParserConfig:
    """Неизменяемый контейнер с настройками сервиса парсинга."""

    base_currency: str
    fiat_currencies: Tuple[str, ...]
    crypto_currencies: Tuple[str, ...]
    crypto_id_map: Dict[str, str]
    coingecko_url: str
    exchangerate_api_url: str
    request_timeout: int
    rates_file_path: Path
    history_file_path: Path
    parser_log_path: Path
    exchangerate_api_key: Optional[str] = field(default=None)

    @classmethod
    def load(cls, settings: Optional[SettingsLoader] = None) -> "ParserConfig":
        settings_loader = settings or get_settings()
        base_currency = settings_loader.get("default_base_currency", "USD").upper()

        rates_path = settings_loader.get_rates_file_path()
        history_path = settings_loader.get_exchange_rates_file_path()
        log_path = settings_loader.get_parser_log_file_path()

        return cls(
            base_currency=base_currency,
            fiat_currencies=DEFAULT_FIAT_CURRENCIES,
            crypto_currencies=DEFAULT_CRYPTO_CURRENCIES,
            crypto_id_map=DEFAULT_CRYPTO_ID_MAP,
            coingecko_url="https://api.coingecko.com/api/v3/simple/price",
            exchangerate_api_url="https://v6.exchangerate-api.com/v6",
            request_timeout=10,
            rates_file_path=rates_path,
            history_file_path=history_path,
            parser_log_path=log_path,
            exchangerate_api_key=settings_loader.get_exchangerate_api_key(),
        )

    def coingecko_params(self) -> Dict[str, str]:
        """Вернуть параметры запроса для CoinGecko."""
        ids = ",".join(
            self.crypto_id_map.get(code, code.lower())
            for code in self.crypto_currencies
        )
        vs_currencies = self.base_currency.lower()
        return {"ids": ids, "vs_currencies": vs_currencies}
