"""
Модуль usecases.py содержит всю бизнес-логику приложения.
"""

from datetime import datetime
from typing import Optional

from ..infra.database import Database, get_database
from ..infra.settings import SettingsLoader, get_settings
from .currencies import get_currency
from .decorators import log_action
from .exceptions import (
    ApiRequestError,
    AuthenticationError,
    EmptyValueError,
    InsufficientFundsError,
    InvalidPasswordError,
    NegativeValueError,
    RateUnavailableError,
    ShortPasswordError,
    UnauthenticatedError,
    UsernameExistsError,
    UserNotFoundError,
    WalletNotFoundError,
)
from .models import User


class Session:
    """Класс для управления сессией пользователя."""

    def __init__(self):
        self.current_user: Optional[User] = None

    def is_logged_in(self) -> bool:
        """Проверить, залогинен ли пользователь."""
        return self.current_user is not None

    def login(self, user: User):
        """Залогинить пользователя."""
        self.current_user = user

    def logout(self):
        """Разлогинить пользователя."""
        self.current_user = None

    def get_current_user(self) -> Optional[User]:
        """Получить текущего пользователя."""
        return self.current_user

    def require_login(self):
        """Проверить что пользователь залогинен, иначе вызвать исключение."""
        if not self.is_logged_in():
            raise AuthenticationError("Сначала выполните login")


class UserUseCases:
    """Use cases для работы с пользователями."""

    def __init__(
        self,
        session: Session,
        database: Database = None,
        settings: SettingsLoader = None,
    ):
        self.session = session
        self.database = database or get_database()
        self.settings = settings or get_settings()

    @log_action("REGISTER")
    def register_user(self, username: str, password: str) -> str:
        """
        Зарегистрировать нового пользователя.

        Args:
            username: Имя пользователя
            password: Пароль

        Returns:
            Сообщение об успешной регистрации

        Raises:
            EmptyValueError: Если имя пустое
            ShortPasswordError: Если пароль слишком короткий
            UsernameExistsError: Если имя уже занято
        """
        # Проверка пустого имени
        if not username or not username.strip():
            raise EmptyValueError("Имя пользователя")

        # Проверка длины пароля
        if len(password) < 4:
            raise ShortPasswordError()

        # Создание пользователя
        try:
            user = self.database.create_user(username, password)
        except ValueError:
            raise UsernameExistsError(username)

        message = (
            f"Пользователь '{username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {username} --password ****"
        )
        return message

    @log_action("LOGIN")
    def login_user(self, username: str, password: str) -> str:
        """
        Войти в систему.

        Args:
            username: Имя пользователя
            password: Пароль

        Returns:
            Сообщение об успешном входе

        Raises:
            UserNotFoundError: Если пользователь не найден
            InvalidPasswordError: Если пароль неверный
        """
        # Найти пользователя
        user = self.database.find_user_by_username(username)

        if not user:
            raise UserNotFoundError(username)

        # Проверить пароль
        if not user.verify_password(password):
            raise InvalidPasswordError()

        # Залогинить
        self.session.login(user)
        return f"Вы вошли как '{username}'"


class PortfolioUseCases:
    """Use cases для работы с портфелями."""

    def __init__(
        self,
        session: Session,
        database: Database = None,
        settings: SettingsLoader = None,
    ):
        self.session = session
        self.database = database or get_database()
        self.settings = settings or get_settings()

    def show_portfolio(self, base_currency: str = None) -> str:
        """
        Показать портфель пользователя.

        Args:
            base_currency: Базовая валюта для конвертации
                (если None, берется из конфигурации)

        Returns:
            Отформатированный портфель

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            CurrencyNotFoundError: Если базовая валюта не найдена в реестре
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Если базовая валюта не указана, берем из конфигурации
        if base_currency is None:
            base_currency = self.settings.get_default_base_currency()

        # Валидация базовой валюты через get_currency() - бросит CurrencyNotFoundError
        base_currency = base_currency.upper()
        get_currency(base_currency)  # Валидация существования валюты

        # Безопасная операция: загрузить курсы и портфель
        rates = self.database.get_all_rates_dict()
        portfolio = self.database.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        if not portfolio or not portfolio._wallets:
            message = (
                f"Портфель пользователя '{self.session.current_user.username}' пуст\n"
                f"Используйте команду 'buy' для покупки валюты"
            )
            return message

        result = [
            f"Портфель пользователя '{self.session.current_user.username}' "
            f"(база: {base_currency}):"
        ]

        total_value = 0.0

        for currency_code, wallet in sorted(portfolio._wallets.items()):
            balance = wallet.balance

            # Конвертация в базовую валюту
            if currency_code == base_currency:
                value_in_base = balance
            else:
                rate_key = f"{currency_code}_{base_currency}"
                if rate_key in rates:
                    rate = rates[rate_key]
                    value_in_base = balance * rate
                else:
                    # Попробовать обратный курс
                    reverse_key = f"{base_currency}_{currency_code}"
                    if reverse_key in rates:
                        rate = 1.0 / rates[reverse_key]
                        value_in_base = balance * rate
                    else:
                        result.append(
                            f"- {currency_code}: {balance:.4f}  → курс недоступен"
                        )
                        continue

            total_value += value_in_base
            result.append(
                f"- {currency_code}: {balance:.4f}  → "
                f"{value_in_base:.2f} {base_currency}"
            )

        result.append("---------------------------------")
        result.append(f"ИТОГО: {total_value:,.2f} {base_currency}")

        return "\n".join(result)

    @log_action("BUY", verbose=True)
    def buy_currency(
        self, currency: str, amount: float, base_currency: str = None
    ) -> str:
        """
        Купить валюту.

        Args:
            currency: Код валюты
            amount: Количество
            base_currency: Базовая валюта для расчета стоимости
                (если None, берется из конфигурации)

        Returns:
            Сообщение об успешной покупке

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            NegativeValueError: Если количество отрицательное или ноль
            CurrencyNotFoundError: Если валюта не найдена в реестре
            RateUnavailableError: Если курс недоступен
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Валидация amount > 0
        if amount <= 0:
            raise NegativeValueError("amount")

        # Валидация currency_code через get_currency() - бросит CurrencyNotFoundError
        currency_code = currency.upper()
        get_currency(currency_code)  # Валидация существования валюты

        # Если базовая валюта не указана, берем из конфигурации
        if base_currency is None:
            base_currency = self.settings.get_default_base_currency()
        else:
            base_currency = base_currency.upper()

        # Получить курс для оценочной стоимости
        rate = self.database.get_rate(currency_code, base_currency)
        if rate is None:
            raise RateUnavailableError(currency_code, base_currency)

        # Безопасная операция: загрузить → модифицировать → сохранить
        portfolio = self.database.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        # Автосоздание кошелька при отсутствии валюты
        wallet = portfolio.get_or_create_wallet(currency_code)
        old_balance = wallet.balance

        # Пополнить баланс
        wallet.deposit(amount)

        # Сохранить портфель
        self.database.save_portfolio(portfolio)

        # Формирование ответа
        result = [f"Покупка выполнена: {amount:.4f} {currency_code}"]
        result[0] += f" по курсу {rate:.2f} {base_currency}/{currency_code}"

        result.append("Изменения в портфеле:")
        result.append(
            f"- {currency_code}: было {old_balance:.4f} → стало {wallet.balance:.4f}"
        )

        # Оценочная стоимость: amount * rate
        estimated_cost = amount * rate
        result.append(
            f"Оценочная стоимость покупки: {estimated_cost:,.2f} {base_currency}"
        )

        return "\n".join(result)

    @log_action("SELL", verbose=True)
    def sell_currency(
        self, currency: str, amount: float, base_currency: str = None
    ) -> str:
        """
        Продать валюту.

        Args:
            currency: Код валюты
            amount: Количество
            base_currency: Базовая валюта для расчета выручки
                (если None, берется из конфигурации)

        Returns:
            Сообщение об успешной продаже

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            NegativeValueError: Если количество отрицательное или ноль
            CurrencyNotFoundError: Если валюта не найдена в реестре
            WalletNotFoundError: Если кошелек не найден
            InsufficientFundsError: Если недостаточно средств
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Валидация amount > 0
        if amount <= 0:
            raise NegativeValueError("amount")

        # Валидация currency_code через get_currency() - бросит CurrencyNotFoundError
        currency_code = currency.upper()
        get_currency(currency_code)  # Валидация существования валюты

        # Безопасная операция: загрузить → модифицировать → сохранить
        portfolio = self.database.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        # Получить кошелёк - проверка существования
        wallet = portfolio.get_wallet(currency_code)

        if not wallet:
            raise WalletNotFoundError(currency_code)

        # Проверить достаточность средств - бросит InsufficientFundsError
        if wallet.balance < amount:
            raise InsufficientFundsError(currency_code, wallet.balance, amount)

        old_balance = wallet.balance

        # Снять средства (может выбросить InsufficientFundsError при проверке в модели)
        wallet.withdraw(amount)

        # Сохранить портфель
        self.database.save_portfolio(portfolio)

        # Если базовая валюта не указана, берем из конфигурации
        if base_currency is None:
            base_currency = self.settings.get_default_base_currency()
        else:
            base_currency = base_currency.upper()

        # Получить курс для оценочной выручки
        rate = self.database.get_rate(currency_code, base_currency)

        # Формирование ответа
        result = [f"Продажа выполнена: {amount:.4f} {currency_code}"]
        if rate:
            result[0] += f" по курсу {rate:.2f} {base_currency}/{currency_code}"

        result.append("Изменения в портфеле:")
        result.append(
            f"- {currency_code}: было {old_balance:.4f} → стало {wallet.balance:.4f}"
        )

        # Оценочная выручка в базовой валюте (если курс доступен)
        if rate:
            estimated_revenue = amount * rate
            result.append(
                f"Оценочная выручка: {estimated_revenue:,.2f} {base_currency}"
            )

        return "\n".join(result)


class RateUseCases:
    """Use cases для работы с курсами валют."""

    def __init__(
        self,
        session: Session,
        database: Database = None,
        settings: SettingsLoader = None,
    ):
        self.session = session
        self.database = database or get_database()
        self.settings = settings or get_settings()

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> str:
        """
        Получить курс обмена валют.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта

        Returns:
            Информация о курсе обмена

        Raises:
            EmptyValueError: Если коды валют пустые
            CurrencyNotFoundError: Если валюты не найдены в реестре
            RateUnavailableError: Если курс недоступен
            ApiRequestError: Если не удалось обновить устаревшие курсы
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Валидация пустых кодов
        if not from_currency or not to_currency:
            raise EmptyValueError("Коды валют")

        # Валидация кодов валют через get_currency() - бросит CurrencyNotFoundError
        get_currency(from_currency)  # Валидация существования валюты
        get_currency(to_currency)  # Валидация существования валюты

        # Получить TTL из настроек
        ttl_seconds = self.settings.get_rates_ttl()

        # Загрузить курсы
        rates = self.database.load_rates()
        rate_key = f"{from_currency}_{to_currency}"

        # Проверить существование курса
        rate_value = None
        updated_at = None

        if rate_key in rates and isinstance(rates[rate_key], dict):
            rate_value = rates[rate_key].get("rate")
            updated_at = rates[rate_key].get("updated_at")
        else:
            # Попробовать обратный курс
            reverse_key = f"{to_currency}_{from_currency}"
            if reverse_key in rates and isinstance(rates[reverse_key], dict):
                reverse_rate = rates[reverse_key].get("rate")
                if reverse_rate and reverse_rate != 0:
                    rate_value = 1.0 / reverse_rate
                    updated_at = rates[reverse_key].get("updated_at")

        if rate_value is None:
            raise RateUnavailableError(from_currency, to_currency)

        # Проверить актуальность кеша (TTL)
        is_stale = False
        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at)
                now = datetime.now()
                elapsed_seconds = (now - updated_dt).total_seconds()

                if elapsed_seconds > ttl_seconds:
                    is_stale = True
            except (ValueError, TypeError):
                is_stale = True

        if is_stale:
            raise ApiRequestError("Не удалось обновить курсы")

        # Форматирование метки времени
        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at)
                updated_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                updated_str = updated_at
        else:
            updated_str = "неизвестно"

        # Формирование ответа
        result = [
            f"Курс {from_currency}→{to_currency}: {rate_value:.8f} "
            f"(обновлено: {updated_str})"
        ]

        # Показать обратный курс
        if rate_value != 0:
            reverse_rate = 1.0 / rate_value
            result.append(
                f"Обратный курс {to_currency}→{from_currency}: {reverse_rate:.8f}"
            )

        return "\n".join(result)
