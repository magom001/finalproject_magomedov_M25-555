"""
Модуль models.py содержит основные модели данных системы ValutaTrade Hub.
"""

import hashlib
import secrets
from copy import deepcopy
from datetime import datetime
from typing import Dict, Optional

from .exceptions import InsufficientFundsError


class User:
    """
    Класс User представляет пользователя системы.

    Атрибуты:
        _user_id: Уникальный идентификатор пользователя
        _username: Имя пользователя
        _hashed_password: Пароль в зашифрованном виде
        _salt: Уникальная соль для пользователя
        _registration_date: Дата регистрации пользователя
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        password: str = None,
        hashed_password: str = None,
        salt: str = None,
        registration_date: datetime = None,
    ):
        """
        Инициализация пользователя.

        Args:
            user_id: Уникальный идентификатор
            username: Имя пользователя
            password: Пароль в открытом виде (для нового пользователя)
            hashed_password: Хешированный пароль (для загрузки из БД)
            salt: Соль (для загрузки из БД)
            registration_date: Дата регистрации (по умолчанию текущая)
        """
        self._user_id = user_id
        self._username = username
        self._registration_date = registration_date or datetime.now()

        # Если создаём нового пользователя
        if password and not hashed_password:
            self._salt = secrets.token_hex(8)
            self._hashed_password = self._hash_password(password, self._salt)
        # Если загружаем существующего
        elif hashed_password and salt:
            self._salt = salt
            self._hashed_password = hashed_password
        else:
            raise ValueError(
                "Необходимо указать либо password, либо hashed_password+salt"
            )

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Хеширование пароля с солью."""
        combined = (password + salt).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    # Геттеры
    @property
    def user_id(self) -> int:
        """Получить ID пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Получить имя пользователя."""
        return self._username

    @property
    def registration_date(self) -> datetime:
        """Получить дату регистрации."""
        return self._registration_date

    @property
    def hashed_password(self) -> str:
        """Получить хешированный пароль."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Получить соль."""
        return self._salt

    # Сеттеры
    @username.setter
    def username(self, value: str):
        """
        Установить имя пользователя.

        Args:
            value: Новое имя пользователя

        Raises:
            ValueError: Если имя пустое
        """
        if not value or not value.strip():
            raise ValueError("Имя не может быть пустым")
        self._username = value.strip()

    def get_user_info(self) -> dict:
        """
        Получить информацию о пользователе (без пароля).

        Returns:
            Словарь с информацией о пользователе
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str):
        """
        Изменить пароль пользователя.

        Args:
            new_password: Новый пароль

        Raises:
            ValueError: Если пароль короче 4 символов
        """
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """
        Проверить введённый пароль на совпадение.

        Args:
            password: Пароль для проверки

        Returns:
            True если пароль верный, иначе False
        """
        return self._hash_password(password, self._salt) == self._hashed_password

    def to_dict(self) -> dict:
        """Преобразовать пользователя в словарь для сохранения в JSON."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Создать пользователя из словаря (загрузка из JSON)."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )


class Wallet:
    """
    Класс Wallet представляет кошелёк для одной конкретной валюты.

    Атрибуты:
        currency_code: Код валюты (например, "USD", "BTC")
        _balance: Баланс в данной валюте
    """

    def __init__(self, currency_code: str, balance: float = 0.0):
        """
        Инициализация кошелька.

        Args:
            currency_code: Код валюты
            balance: Начальный баланс (по умолчанию 0.0)
        """
        self.currency_code = currency_code.upper()
        self._balance = 0.0
        self.balance = balance  # Используем сеттер для валидации

    @property
    def balance(self) -> float:
        """Получить текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float):
        """
        Установить баланс.

        Args:
            value: Новое значение баланса

        Raises:
            ValueError: Если значение отрицательное или некорректного типа
        """
        if not isinstance(value, (int, float)):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float):
        """
        Пополнить баланс.

        Args:
            amount: Сумма пополнения

        Raises:
            ValueError: Если сумма не положительная
        """
        if not isinstance(amount, (int, float)):
            raise ValueError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self._balance += float(amount)

    def withdraw(self, amount: float):
        """
        Снять средства.

        Args:
            amount: Сумма снятия

        Raises:
            ValueError: Если сумма не положительная
            InsufficientFundsError: Если сумма превышает баланс
        """
        if not isinstance(amount, (int, float)):
            raise ValueError("Сумма должна быть числом")
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        if amount > self._balance:
            raise InsufficientFundsError(self.currency_code, self._balance, amount)
        self._balance -= float(amount)

    def get_balance_info(self) -> str:
        """
        Получить информацию о текущем балансе.

        Returns:
            Строка с информацией о балансе
        """
        return f"{self.currency_code}: {self._balance:.4f}"

    def to_dict(self) -> dict:
        """Преобразовать кошелёк в словарь для сохранения в JSON."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        """Создать кошелёк из словаря (загрузка из JSON)."""
        return cls(currency_code=data["currency_code"], balance=data["balance"])


class Portfolio:
    """
    Класс Portfolio управляет всеми кошельками одного пользователя.

    Атрибуты:
        _user_id: Уникальный идентификатор пользователя
        _wallets: Словарь кошельков (ключ - код валюты, значение - объект Wallet)
    """

    def __init__(self, user_id: int, wallets: Optional[Dict[str, Wallet]] = None):
        """
        Инициализация портфеля.

        Args:
            user_id: ID пользователя
            wallets: Словарь кошельков (опционально)
        """
        self._user_id = user_id
        self._wallets: Dict[str, Wallet] = wallets or {}

    @property
    def user_id(self) -> int:
        """Получить ID пользователя (без возможности перезаписи)."""
        return self._user_id

    @property
    def wallets(self) -> Dict[str, Wallet]:
        """Получить копию словаря кошельков."""
        return deepcopy(self._wallets)

    def add_currency(self, currency_code: str) -> Wallet:
        """
        Добавить новый кошелёк в портфель.

        Args:
            currency_code: Код валюты

        Returns:
            Созданный или существующий кошелёк

        Raises:
            ValueError: Если такой кошелёк уже существует
        """
        currency_code = currency_code.upper()

        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк для валюты {currency_code} уже существует")

        wallet = Wallet(currency_code)
        self._wallets[currency_code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        """
        Получить кошелёк по коду валюты.

        Args:
            currency_code: Код валюты

        Returns:
            Объект Wallet или None если не найден
        """
        return self._wallets.get(currency_code.upper())

    def get_or_create_wallet(self, currency_code: str) -> Wallet:
        """
        Получить существующий кошелёк или создать новый.

        Args:
            currency_code: Код валюты

        Returns:
            Объект Wallet
        """
        currency_code = currency_code.upper()
        if currency_code not in self._wallets:
            self._wallets[currency_code] = Wallet(currency_code)
        return self._wallets[currency_code]

    def get_total_value(
        self,
        base_currency: str = "USD",
        exchange_rates: Optional[Dict[str, float]] = None,
    ) -> float:
        """
        Получить общую стоимость всех валют в указанной базовой валюте.

        Args:
            base_currency: Базовая валюта для конвертации (по умолчанию USD)
            exchange_rates: Словарь курсов валют (например, {"BTC_USD": 59337.21})

        Returns:
            Общая стоимость в базовой валюте
        """
        if exchange_rates is None:
            # Используем фиксированные курсы по умолчанию
            exchange_rates = {
                "EUR_USD": 1.0786,
                "BTC_USD": 59337.21,
                "RUB_USD": 0.01016,
                "ETH_USD": 3720.00,
                "USD_USD": 1.0,
            }

        total = 0.0
        base_currency = base_currency.upper()

        for currency_code, wallet in self._wallets.items():
            if currency_code == base_currency:
                # Если валюта совпадает с базовой
                total += wallet.balance
            else:
                # Ищем курс валюты к базовой валюте
                rate_key = f"{currency_code}_{base_currency}"
                if rate_key in exchange_rates:
                    rate = exchange_rates[rate_key]
                    total += wallet.balance * rate
                else:
                    # Если прямого курса нет, пробуем через обратный
                    reverse_key = f"{base_currency}_{currency_code}"
                    if reverse_key in exchange_rates:
                        rate = 1.0 / exchange_rates[reverse_key]
                        total += wallet.balance * rate

        return total

    def to_dict(self) -> dict:
        """Преобразовать портфель в словарь для сохранения в JSON."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: wallet.to_dict() for code, wallet in self._wallets.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        """Создать портфель из словаря (загрузка из JSON)."""
        wallets = {
            code: Wallet.from_dict(wallet_data)
            for code, wallet_data in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets)
