"""
Модуль database.py содержит класс Database для работы с данными.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.models import Portfolio, User
from .settings import get_settings


class Database:
    """Класс для работы с JSON файлами (хранилище данных)."""

    def __init__(self, data_dir: str = None):
        """
        Инициализация базы данных.

        Args:
            data_dir: Путь к директории с данными (если None, берется из конфигурации)
        """
        if data_dir is None:
            # Получаем настройки из синглтона
            settings = get_settings()
            data_dir = settings.get_data_dir()

        self.data_dir = Path(data_dir)

        # Используем SettingsLoader для получения имен файлов
        settings = get_settings()
        self.users_file = self.data_dir / settings.get("users_file", "users.json")
        self.portfolios_file = self.data_dir / settings.get(
            "portfolios_file", "portfolios.json"
        )
        self.rates_file = self.data_dir / settings.get("rates_file", "rates.json")

        # Создаём директорию если не существует
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Инициализируем файлы если не существуют
        self._init_files()

    def _init_files(self):
        """Инициализировать JSON файлы если они не существуют."""
        if not self.users_file.exists():
            self._save_json(self.users_file, [])

        if not self.portfolios_file.exists():
            self._save_json(self.portfolios_file, [])

        if not self.rates_file.exists():
            now_iso = datetime.now().isoformat()
            default_pairs = {
                "EUR_USD": {
                    "rate": 1.0786,
                    "updated_at": now_iso,
                    "source": "SeedData",
                },
                "BTC_USD": {
                    "rate": 59337.21,
                    "updated_at": now_iso,
                    "source": "SeedData",
                },
                "RUB_USD": {
                    "rate": 0.01016,
                    "updated_at": now_iso,
                    "source": "SeedData",
                },
                "ETH_USD": {
                    "rate": 3720.00,
                    "updated_at": now_iso,
                    "source": "SeedData",
                },
            }
            default_rates = {
                "pairs": default_pairs,
                "last_refresh": now_iso,
            }
            self._save_json(self.rates_file, default_rates)

    def _load_json(self, file_path: Path) -> Any:
        """Загрузить данные из JSON файла."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return [] if file_path.name in ["users.json", "portfolios.json"] else {}

    def _save_json(self, file_path: Path, data: any):
        """Сохранить данные в JSON файл."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # === Работа с пользователями ===

    def load_users(self) -> List[User]:
        """Загрузить всех пользователей."""
        data = self._load_json(self.users_file)
        return [User.from_dict(user_data) for user_data in data]

    def save_users(self, users: List[User]):
        """Сохранить всех пользователей."""
        data = [user.to_dict() for user in users]
        self._save_json(self.users_file, data)

    def find_user_by_username(self, username: str) -> Optional[User]:
        """Найти пользователя по имени."""
        users = self.load_users()
        for user in users:
            if user.username == username:
                return user
        return None

    def find_user_by_id(self, user_id: int) -> Optional[User]:
        """Найти пользователя по ID."""
        users = self.load_users()
        for user in users:
            if user.user_id == user_id:
                return user
        return None

    def create_user(self, username: str, password: str) -> User:
        """
        Создать нового пользователя.

        Args:
            username: Имя пользователя
            password: Пароль

        Returns:
            Созданный пользователь

        Raises:
            ValueError: Если пользователь с таким именем уже существует
        """
        # Проверка уникальности
        if self.find_user_by_username(username):
            raise ValueError(f"Имя пользователя '{username}' уже занято")

        # Проверка длины пароля
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        # Генерация нового ID
        users = self.load_users()
        new_id = max([u.user_id for u in users], default=0) + 1

        # Создание пользователя
        user = User(user_id=new_id, username=username, password=password)

        # Сохранение
        users.append(user)
        self.save_users(users)

        # Создание пустого портфеля
        portfolio = Portfolio(user_id=new_id)
        self.save_portfolio(portfolio)

        return user

    # === Работа с портфелями ===

    def load_portfolios(self) -> List[Portfolio]:
        """Загрузить все портфели."""
        data = self._load_json(self.portfolios_file)
        return [Portfolio.from_dict(portfolio_data) for portfolio_data in data]

    def save_portfolios(self, portfolios: List[Portfolio]):
        """Сохранить все портфели."""
        data = [portfolio.to_dict() for portfolio in portfolios]
        self._save_json(self.portfolios_file, data)

    def find_portfolio_by_user_id(self, user_id: int) -> Optional[Portfolio]:
        """Найти портфель по ID пользователя."""
        portfolios = self.load_portfolios()
        for portfolio in portfolios:
            if portfolio.user_id == user_id:
                return portfolio
        return None

    def save_portfolio(self, portfolio: Portfolio):
        """Сохранить портфель (обновить или создать)."""
        portfolios = self.load_portfolios()

        # Ищем существующий портфель
        found = False
        for i, p in enumerate(portfolios):
            if p.user_id == portfolio.user_id:
                portfolios[i] = portfolio
                found = True
                break

        # Если не найден, добавляем новый
        if not found:
            portfolios.append(portfolio)

        self.save_portfolios(portfolios)

    # === Работа с курсами валют ===

    def load_rates(self) -> Dict[str, Any]:
        """Загрузить курсы валют с приведением к современному формату."""
        raw_data = self._load_json(self.rates_file)

        if not isinstance(raw_data, dict):
            return {"pairs": {}, "last_refresh": None}

        pairs_section = raw_data.get("pairs")
        if not isinstance(pairs_section, dict):
            pairs_section = {}
            for key, value in raw_data.items():
                if key == "last_refresh":
                    continue
                if isinstance(value, dict) and "rate" in value:
                    pairs_section[key] = value

        return {
            "pairs": pairs_section,
            "last_refresh": raw_data.get("last_refresh"),
        }

    def save_rates(self, rates: Dict[str, Any]):
        """Сохранить курсы валют в формате с секцией pairs."""
        payload = {
            "pairs": rates.get("pairs", {}),
            "last_refresh": rates.get("last_refresh"),
        }
        self._save_json(self.rates_file, payload)

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Получить курс конвертации.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта

        Returns:
            Курс конвертации или None если не найден
        """
        rates_payload = self.load_rates()
        pairs = rates_payload.get("pairs", {})

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Если валюты одинаковые
        if from_currency == to_currency:
            return 1.0

        # Прямой курс
        rate_key = f"{from_currency}_{to_currency}"
        if rate_key in pairs and isinstance(pairs[rate_key], dict):
            return pairs[rate_key].get("rate")

        # Обратный курс
        reverse_key = f"{to_currency}_{from_currency}"
        if reverse_key in pairs and isinstance(pairs[reverse_key], dict):
            base_rate = pairs[reverse_key].get("rate")
            if base_rate:
                return 1.0 / base_rate

        return None

    def update_rate(self, from_currency: str, to_currency: str, rate: float):
        """
        Обновить курс валюты.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            rate: Новый курс
        """
        payload = self.load_rates()
        pairs = payload.setdefault("pairs", {})

        rate_key = f"{from_currency.upper()}_{to_currency.upper()}"
        pairs[rate_key] = {
            "rate": rate,
            "updated_at": datetime.now().isoformat(),
        }
        payload["last_refresh"] = datetime.now().isoformat()

        self.save_rates(payload)

    def get_all_rates_dict(self) -> Dict[str, float]:
        """
        Получить все курсы в виде простого словаря.

        Returns:
            Словарь {currency_pair: rate}
        """
        payload = self.load_rates()
        pairs = payload.get("pairs", {})
        result = {}

        for key, value in pairs.items():
            if isinstance(value, dict) and "rate" in value:
                result[key] = value["rate"]

        return result


# Глобальный экземпляр базы данных
_database = None


def get_database() -> Database:
    """Получить глобальный экземпляр Database."""
    global _database
    if _database is None:
        _database = Database()
    return _database
