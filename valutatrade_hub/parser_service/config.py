"""Конфигурационные объекты сервиса парсинга."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..core.currencies import (
    get_crypto_currency_codes,
    get_fiat_currency_codes,
)
from ..infra.settings import SettingsLoader, get_settings

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

        default_fiat = tuple(
            code for code in get_fiat_currency_codes() if code != base_currency
        )
        default_crypto = tuple(get_crypto_currency_codes())

        fiat_config = settings_loader.get("parser_fiat_currencies")
        crypto_config = settings_loader.get("parser_crypto_currencies")

        fiat_codes = cls._normalize_currency_list(
            fiat_config, default_fiat, exclude={base_currency}
        )
        crypto_codes = cls._normalize_currency_list(crypto_config, default_crypto)

        return cls(
            base_currency=base_currency,
            fiat_currencies=fiat_codes,
            crypto_currencies=crypto_codes,
            crypto_id_map=DEFAULT_CRYPTO_ID_MAP,
            coingecko_url="https://api.coingecko.com/api/v3/simple/price",
            exchangerate_api_url="https://v6.exchangerate-api.com/v6",
            request_timeout=10,
            rates_file_path=rates_path,
            history_file_path=history_path,
            parser_log_path=log_path,
            exchangerate_api_key=settings_loader.get_exchangerate_api_key(),
        )

    @staticmethod
    def _normalize_currency_list(
        raw_value: Optional[Iterable[str]],
        fallback: Sequence[str],
        *,
        exclude: Optional[Iterable[str]] = None,
    ) -> Tuple[str, ...]:
        """Преобразовать значение конфигурации в кортеж кодов валют."""

        exclude_set = {item.upper() for item in exclude} if exclude else set()

        def _apply_exclude(codes: Iterable[str]) -> Tuple[str, ...]:
            result: List[str] = []
            for code in codes:
                upper = code.upper().strip()
                if not upper or upper in exclude_set:
                    continue
                if upper not in result:
                    result.append(upper)
            return tuple(result)

        if raw_value is None:
            return _apply_exclude(fallback)

        if isinstance(raw_value, str):
            tokens = [token.strip() for token in raw_value.replace(";", ",").split(",")]
            filtered = [token for token in tokens if token]
            if filtered:
                return _apply_exclude(filtered)
            return _apply_exclude(fallback)

        if isinstance(raw_value, (list, tuple, set)):
            if raw_value:
                return _apply_exclude(str(item) for item in raw_value)
            return _apply_exclude(fallback)

        return _apply_exclude(fallback)

    def coingecko_params(self) -> Dict[str, str]:
        """Вернуть параметры запроса для CoinGecko."""
        ids = ",".join(
            self.crypto_id_map.get(code, code.lower())
            for code in self.crypto_currencies
        )
        vs_currencies = self.base_currency.lower()
        return {"ids": ids, "vs_currencies": vs_currencies}
