"""
Модуль usecases.py содержит всю бизнес-логику приложения.
"""

from datetime import datetime
from typing import Optional

from .exceptions import (
    AuthenticationError,
    EmptyValueError,
    InsufficientFundsError,
    InvalidPasswordError,
    NegativeValueError,
    RateUnavailableError,
    ShortPasswordError,
    UnauthenticatedError,
    UnknownCurrencyError,
    UsernameExistsError,
    UserNotFoundError,
    WalletNotFoundError,
)
from .models import User
from .services import get_data_service


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

    def __init__(self, session: Session):
        self.session = session
        self.data_service = get_data_service()

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
            user = self.data_service.create_user(username, password)
        except ValueError:
            raise UsernameExistsError(username)

        message = (
            f"Пользователь '{username}' зарегистрирован (id={user.user_id}). "
            f"Войдите: login --username {username} --password ****"
        )
        return message

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
        user = self.data_service.find_user_by_username(username)

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

    def __init__(self, session: Session):
        self.session = session
        self.data_service = get_data_service()

    def show_portfolio(self, base_currency: str = "USD") -> str:
        """
        Показать портфель пользователя.

        Args:
            base_currency: Базовая валюта для конвертации

        Returns:
            Отформатированный портфель

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            UnknownCurrencyError: Если базовая валюта неизвестна
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Валидация базовой валюты
        base_currency = base_currency.upper()

        # Получить курсы для проверки валюты
        rates = self.data_service.get_all_rates_dict()

        # Проверить существование базовой валюты в курсах
        base_currency_exists = False
        for rate_key in rates.keys():
            if base_currency in rate_key.split("_"):
                base_currency_exists = True
                break

        # Загрузить портфель
        portfolio = self.data_service.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        # Проверяем валюту еще раз с учетом портфеля
        if not base_currency_exists and (
            not portfolio or base_currency not in portfolio._wallets
        ):
            raise UnknownCurrencyError(base_currency)

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

    def buy_currency(self, currency: str, amount: float) -> str:
        """
        Купить валюту.

        Args:
            currency: Код валюты
            amount: Количество

        Returns:
            Сообщение об успешной покупке

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            NegativeValueError: Если количество отрицательное
            RateUnavailableError: Если курс недоступен
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Валидация
        currency = currency.upper()

        if amount <= 0:
            raise NegativeValueError("amount")

        # Проверить существование валюты через курс
        rate = self.data_service.get_rate(currency, "USD")
        if rate is None:
            raise RateUnavailableError(currency, "USD")

        # Загрузить портфель
        portfolio = self.data_service.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        # Получить или создать кошелёк
        wallet = portfolio.get_or_create_wallet(currency)
        old_balance = wallet.balance

        # Пополнить баланс
        wallet.deposit(amount)

        # Сохранить портфель
        self.data_service.save_portfolio(portfolio)

        result = [f"Покупка выполнена: {amount:.4f} {currency}"]
        result[0] += f" по курсу {rate:.2f} USD/{currency}"

        result.append("Изменения в портфеле:")
        result.append(
            f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}"
        )

        estimated_cost = amount * rate
        result.append(f"Оценочная стоимость покупки: {estimated_cost:,.2f} USD")

        return "\n".join(result)

    def sell_currency(self, currency: str, amount: float) -> str:
        """
        Продать валюту.

        Args:
            currency: Код валюты
            amount: Количество

        Returns:
            Сообщение об успешной продаже

        Raises:
            UnauthenticatedError: Если пользователь не залогинен
            NegativeValueError: Если количество отрицательное
            WalletNotFoundError: Если кошелек не найден
            InsufficientFundsError: Если недостаточно средств
        """
        # Проверка логина
        if not self.session.is_logged_in():
            raise UnauthenticatedError()

        # Валидация
        currency = currency.upper()

        if amount <= 0:
            raise NegativeValueError("amount")

        # Загрузить портфель
        portfolio = self.data_service.find_portfolio_by_user_id(
            self.session.current_user.user_id
        )

        # Получить кошелёк
        wallet = portfolio.get_wallet(currency)

        if not wallet:
            raise WalletNotFoundError(currency)

        # Проверить достаточность средств
        if wallet.balance < amount:
            raise InsufficientFundsError(currency, wallet.balance, amount)

        old_balance = wallet.balance

        # Снять средства (может выбросить InsufficientFundsError)
        wallet.withdraw(amount)

        # Сохранить портфель
        self.data_service.save_portfolio(portfolio)

        # Получить курс для отчёта
        rate = self.data_service.get_rate(currency, "USD")

        result = [f"Продажа выполнена: {amount:.4f} {currency}"]
        if rate:
            result[0] += f" по курсу {rate:.2f} USD/{currency}"

        result.append("Изменения в портфеле:")
        result.append(
            f"- {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}"
        )

        if rate:
            estimated_revenue = amount * rate
            result.append(f"Оценочная выручка: {estimated_revenue:,.2f} USD")

        return "\n".join(result)


class RateUseCases:
    """Use cases для работы с курсами валют."""

    def __init__(self, session: Session):
        self.session = session
        self.data_service = get_data_service()

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
            RateUnavailableError: Если курс недоступен
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Валидация
        if not from_currency or not to_currency:
            raise EmptyValueError("Коды валют")

        # Получить курс
        rate = self.data_service.get_rate(from_currency, to_currency)

        if rate is None:
            raise RateUnavailableError(from_currency, to_currency)

        # Получить метку времени
        rates = self.data_service.load_rates()
        rate_key = f"{from_currency}_{to_currency}"

        if rate_key in rates and isinstance(rates[rate_key], dict):
            updated_at = rates[rate_key].get("updated_at", "неизвестно")
            try:
                dt = datetime.fromisoformat(updated_at)
                updated_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                updated_str = updated_at
        else:
            updated_str = "неизвестно"

        result = [
            f"Курс {from_currency}→{to_currency}: {rate:.8f} (обновлено: {updated_str})"
        ]

        # Показать обратный курс
        if rate != 0:
            reverse_rate = 1.0 / rate
            result.append(
                f"Обратный курс {to_currency}→{from_currency}: {reverse_rate:.8f}"
            )

        return "\n".join(result)
