"""
Модуль currencies.py содержит иерархию валют и реестр валют.
"""

import re
from abc import ABC, abstractmethod
from typing import Dict

from .exceptions import CurrencyNotFoundError, ValidationError


class Currency(ABC):
    """
    Абстрактный базовый класс для всех валют.

    Атрибуты:
        name (str): Человекочитаемое имя валюты (например, "US Dollar", "Bitcoin").
        code (str): ISO-код или общепринятый тикер ("USD", "EUR", "BTC", "ETH").

    Инварианты:
        - code должен быть в верхнем регистре, 2-5 символов, без пробелов
        - name не должен быть пустой строкой
    """

    def __init__(self, name: str, code: str):
        """
        Инициализирует валюту с валидацией инвариантов.

        Args:
            name: Человекочитаемое имя валюты
            code: Код валюты (будет преобразован в верхний регистр)

        Raises:
            ValidationError: Если нарушены инварианты валидации
        """
        self._validate_name(name)
        self._validate_code(code)
        self.name = name
        self.code = code.upper()

    def _validate_name(self, name: str) -> None:
        """
        Валидирует имя валюты.

        Args:
            name: Имя валюты для валидации

        Raises:
            ValidationError: Если имя пустое или содержит только пробелы
        """
        if not name or not name.strip():
            raise ValidationError(
                "Некорректное имя валюты", "Имя валюты не может быть пустым"
            )

    def _validate_code(self, code: str) -> None:
        """
        Валидирует код валюты.

        Args:
            code: Код валюты для валидации

        Raises:
            ValidationError: Если код не соответствует требованиям (2-5 символов,
                           только буквы, без пробелов)
        """
        if not code:
            raise ValidationError(
                "Некорректный код валюты", "Код валюты не может быть пустым"
            )

        # Проверка на верхний регистр, 2-5 символов, только буквы
        pattern = r"^[A-Z]{2,5}$"
        if not re.match(pattern, code.upper()):
            raise ValidationError(
                "Некорректный код валюты",
                f"Код валюты '{code}' должен содержать 2-5 букв без пробелов",
            )

    @abstractmethod
    def get_display_info(self) -> str:
        """
        Возвращает строковое представление валюты для UI/логов.

        Returns:
            Отформатированная строка с информацией о валюте
        """
        pass


class FiatCurrency(Currency):
    """
    Фиатная валюта (государственные деньги).

    Дополнительные атрибуты:
        issuing_country (str): Страна или зона эмиссии
            (например, "United States", "Eurozone")
    """

    def __init__(self, name: str, code: str, issuing_country: str):
        """
        Инициализирует фиатную валюту.

        Args:
            name: Человекочитаемое имя валюты
            code: Код валюты (ISO-код)
            issuing_country: Страна или зона эмиссии

        Raises:
            ValidationError: Если нарушены инварианты валидации
        """
        super().__init__(name, code)
        self._validate_issuing_country(issuing_country)
        self.issuing_country = issuing_country

    def _validate_issuing_country(self, issuing_country: str) -> None:
        """
        Валидирует страну эмиссии.

        Args:
            issuing_country: Страна эмиссии для валидации

        Raises:
            ValidationError: Если страна эмиссии пустая
        """
        if not issuing_country or not issuing_country.strip():
            raise ValidationError(
                "Некорректная страна эмиссии",
                "Страна эмиссии не может быть пустой",
            )

    def get_display_info(self) -> str:
        """
        Возвращает строковое представление фиатной валюты.

        Returns:
            Строка формата: "[FIAT] USD — US Dollar (Issuing: United States)"
        """
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """
    Криптовалюта.

    Дополнительные атрибуты:
        algorithm (str): Алгоритм консенсуса/хеширования (например, "SHA-256", "Ethash")
        market_cap (float): Последняя известная рыночная капитализация
    """

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float):
        """
        Инициализирует криптовалюту.

        Args:
            name: Человекочитаемое имя валюты
            code: Тикер криптовалюты
            algorithm: Алгоритм консенсуса/хеширования
            market_cap: Рыночная капитализация

        Raises:
            ValidationError: Если нарушены инварианты валидации
        """
        super().__init__(name, code)
        self._validate_algorithm(algorithm)
        self._validate_market_cap(market_cap)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def _validate_algorithm(self, algorithm: str) -> None:
        """
        Валидирует алгоритм.

        Args:
            algorithm: Алгоритм для валидации

        Raises:
            ValidationError: Если алгоритм пустой
        """
        if not algorithm or not algorithm.strip():
            raise ValidationError(
                "Некорректный алгоритм", "Алгоритм не может быть пустым"
            )

    def _validate_market_cap(self, market_cap: float) -> None:
        """
        Валидирует рыночную капитализацию.

        Args:
            market_cap: Капитализация для валидации

        Raises:
            ValidationError: Если капитализация отрицательная
        """
        if market_cap < 0:
            raise ValidationError(
                "Некорректная капитализация",
                "Рыночная капитализация не может быть отрицательной",
            )

    def get_display_info(self) -> str:
        """
        Возвращает строковое представление криптовалюты.

        Returns:
            Строка формата:
                "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"
        """
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


# Реестр валют
_CURRENCY_REGISTRY: Dict[str, Currency] = {}


def register_currency(currency: Currency) -> None:
    """
    Регистрирует валюту в глобальном реестре.

    Args:
        currency: Экземпляр валюты для регистрации
    """
    _CURRENCY_REGISTRY[currency.code] = currency


def get_currency(code: str) -> Currency:
    """
    Получает валюту из реестра по коду.

    Args:
        code: Код валюты (регистр не важен)

    Returns:
        Экземпляр валюты

    Raises:
        CurrencyNotFoundError: Если валюта с таким кодом не найдена в реестре
    """
    code_upper = code.upper()
    if code_upper not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(code)
    return _CURRENCY_REGISTRY[code_upper]


def initialize_default_currencies() -> None:
    """
    Инициализирует реестр валют стандартными валютами.
    Вызывается при запуске приложения.
    """
    # Фиатные валюты
    register_currency(FiatCurrency("US Dollar", "USD", "United States"))
    register_currency(FiatCurrency("Euro", "EUR", "Eurozone"))
    register_currency(FiatCurrency("British Pound", "GBP", "United Kingdom"))
    register_currency(FiatCurrency("Japanese Yen", "JPY", "Japan"))
    register_currency(FiatCurrency("Swiss Franc", "CHF", "Switzerland"))
    register_currency(FiatCurrency("Canadian Dollar", "CAD", "Canada"))
    register_currency(FiatCurrency("Australian Dollar", "AUD", "Australia"))
    register_currency(FiatCurrency("Chinese Yuan", "CNY", "China"))

    # Криптовалюты
    register_currency(CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12))
    register_currency(CryptoCurrency("Ethereum", "ETH", "Ethash", 3.45e11))
    register_currency(CryptoCurrency("Ripple", "XRP", "RPCA", 2.5e10))
    register_currency(CryptoCurrency("Litecoin", "LTC", "Scrypt", 6.7e9))


def get_all_currencies() -> Dict[str, Currency]:
    """
    Возвращает копию реестра всех зарегистрированных валют.

    Returns:
        Словарь всех валют (код -> экземпляр Currency)
    """
    return _CURRENCY_REGISTRY.copy()
