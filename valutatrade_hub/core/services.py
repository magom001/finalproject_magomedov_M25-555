"""
Модуль services.py содержит сервисы для работы с данными.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import Portfolio, User


class DataService:
    """Сервис для работы с JSON файлами."""

    def __init__(self, data_dir: str = None):
        """
        Инициализация сервиса.

        Args:
            data_dir: Путь к директории с данными
        """
        if data_dir is None:
            # Получаем путь к корню проекта
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"

        self.data_dir = Path(data_dir)
        self.users_file = self.data_dir / "users.json"
        self.portfolios_file = self.data_dir / "portfolios.json"
        self.rates_file = self.data_dir / "rates.json"

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
            default_rates = {
                "EUR_USD": {"rate": 1.0786, "updated_at": datetime.now().isoformat()},
                "BTC_USD": {"rate": 59337.21, "updated_at": datetime.now().isoformat()},
                "RUB_USD": {"rate": 0.01016, "updated_at": datetime.now().isoformat()},
                "ETH_USD": {"rate": 3720.00, "updated_at": datetime.now().isoformat()},
                "source": "ParserService",
                "last_refresh": datetime.now().isoformat(),
            }
            self._save_json(self.rates_file, default_rates)

    def _load_json(self, file_path: Path) -> any:
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

    def load_rates(self) -> Dict:
        """Загрузить курсы валют."""
        return self._load_json(self.rates_file)

    def save_rates(self, rates: Dict):
        """Сохранить курсы валют."""
        self._save_json(self.rates_file, rates)

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Получить курс конвертации.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта

        Returns:
            Курс конвертации или None если не найден
        """
        rates = self.load_rates()

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Если валюты одинаковые
        if from_currency == to_currency:
            return 1.0

        # Прямой курс
        rate_key = f"{from_currency}_{to_currency}"
        if rate_key in rates and isinstance(rates[rate_key], dict):
            return rates[rate_key].get("rate")

        # Обратный курс
        reverse_key = f"{to_currency}_{from_currency}"
        if reverse_key in rates and isinstance(rates[reverse_key], dict):
            return 1.0 / rates[reverse_key].get("rate", 1)

        return None

    def update_rate(self, from_currency: str, to_currency: str, rate: float):
        """
        Обновить курс валюты.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            rate: Новый курс
        """
        rates = self.load_rates()

        rate_key = f"{from_currency.upper()}_{to_currency.upper()}"
        rates[rate_key] = {"rate": rate, "updated_at": datetime.now().isoformat()}
        rates["last_refresh"] = datetime.now().isoformat()

        self.save_rates(rates)

    def get_all_rates_dict(self) -> Dict[str, float]:
        """
        Получить все курсы в виде простого словаря.

        Returns:
            Словарь {currency_pair: rate}
        """
        rates = self.load_rates()
        result = {}

        for key, value in rates.items():
            if isinstance(value, dict) and "rate" in value:
                result[key] = value["rate"]

        return result


# Глобальный экземпляр сервиса
_data_service = None


def get_data_service() -> DataService:
    """Получить глобальный экземпляр DataService."""
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service
