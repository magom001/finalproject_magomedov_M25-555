"""
Модуль usecases.py содержит всю бизнес-логику приложения.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from ..infra.database import Database, get_database
from ..infra.logging_config import get_parser_logger
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
        logger: Optional[logging.Logger] = None,
    ):
        self.session = session
        self.database = database or get_database()
        self.settings = settings or get_settings()
        self.logger = logger or get_parser_logger()

    def _log_info(self, message: str) -> None:
        self.logger.info(message)
        print(f"INFO: {message}")

    def _log_error(self, message: str) -> None:
        self.logger.error(message)
        print(f"ERROR: {message}")

    def _load_pair_rate(
        self, from_currency: str, to_currency: str
    ) -> Optional[Tuple[float, Optional[str]]]:
        payload = self.database.load_rates()
        pairs = payload.get("pairs", {}) if isinstance(payload, dict) else {}

        direct_key = f"{from_currency}_{to_currency}"
        direct_entry = pairs.get(direct_key)
        if isinstance(direct_entry, dict):
            rate_raw = direct_entry.get("rate")
            try:
                rate_value = float(rate_raw)
            except (TypeError, ValueError):
                rate_value = None
            if rate_value is not None:
                updated_at = direct_entry.get("updated_at")
                return rate_value, updated_at if isinstance(updated_at, str) else None

        reverse_key = f"{to_currency}_{from_currency}"
        reverse_entry = pairs.get(reverse_key)
        if isinstance(reverse_entry, dict):
            rate_raw = reverse_entry.get("rate")
            try:
                rate_value = float(rate_raw) if rate_raw is not None else None
            except (TypeError, ValueError):
                rate_value = None
            if rate_value and rate_value != 0:
                updated_at = reverse_entry.get("updated_at")
                return 1.0 / rate_value, updated_at if isinstance(
                    updated_at, str
                ) else None

        return None

    @staticmethod
    def _is_stale(updated_at: Optional[str], ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            return False

        if not updated_at:
            return True

        try:
            normalized = updated_at.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(normalized)
        except (AttributeError, ValueError, TypeError):
            return True

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = (now - timestamp).total_seconds()
        return delta > ttl_seconds

    def _refresh_rates(self) -> bool:
        from ..parser_service.api_clients import (
            CoinGeckoClient,
            ExchangeRateApiClient,
        )
        from ..parser_service.config import ParserConfig
        from ..parser_service.storage import RatesStorage
        from ..parser_service.updater import RatesUpdater

        config = ParserConfig.load(self.settings)
        storage = RatesStorage(config)
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
        updater = RatesUpdater(clients=clients, storage=storage, config=config)

        try:
            updater.run_update()
        except ApiRequestError:
            return False
        return True

    def update_rates(self, source_filter: Optional[str] = None) -> str:
        """Обновить курсы через сервис парсинга."""

        from ..parser_service.api_clients import (
            CoinGeckoClient,
            ExchangeRateApiClient,
        )
        from ..parser_service.config import ParserConfig
        from ..parser_service.storage import RatesStorage
        from ..parser_service.updater import RatesUpdater

        config = ParserConfig.load(self.settings)
        storage = RatesStorage(config)
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]

        updater = RatesUpdater(clients=clients, storage=storage, config=config)
        self._log_info("Запускаем обновление курсов")
        result = updater.run_update(source_filter=source_filter)

        if source_filter:
            active_clients: List[str] = [source_filter]
        else:
            active_clients = [client.name for client in clients]

        error_map = {
            err.get("source"): err.get("message")
            for err in result.errors
            if isinstance(err, dict) and err.get("source")
        }

        for client_name in active_clients:
            processed = result.source_stats.get(client_name, 0)
            if processed:
                self._log_info(f"Источник {client_name} → получено {processed} курсов")
                continue

            error_msg = error_map.get(client_name)
            if error_msg:
                self._log_error(f"Источник {client_name} не ответил: {error_msg}")
            else:
                self._log_info(f"Источник {client_name} → нет новых данных")

        total_processed = sum(
            result.source_stats.get(name, 0) for name in active_clients
        )
        self._log_info(f"Сохраняем {total_processed} курсов в {config.rates_file_path}")

        failing_sources = [name for name in active_clients if error_map.get(name)]

        if failing_sources:
            details = "; ".join(
                f"{name}: {error_map.get(name)}" for name in failing_sources
            )
            raise ApiRequestError(f"Источники недоступны ({details})")

        last_refresh = result.last_refresh or "н/д"
        return (
            f"Обновление успешно. Всего обновлено: {total_processed}. "
            f"Последнее обновление: {last_refresh}"
        )

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> str:
        """
        Получить курс обмена валют.

        Args:
            from_currency: Исходная валюта
            to_currency: Целевая валюта

        Returns:
            Отформатированное сообщение с курсом

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
        pair_data = self._load_pair_rate(from_currency, to_currency)

        if pair_data is None:
            if not self._refresh_rates():
                raise RateUnavailableError(from_currency, to_currency)
            pair_data = self._load_pair_rate(from_currency, to_currency)
            if pair_data is None:
                raise RateUnavailableError(from_currency, to_currency)

        rate_value, updated_at = pair_data

        if self._is_stale(updated_at, ttl_seconds):
            if not self._refresh_rates():
                raise ApiRequestError("Не удалось обновить курсы")
            pair_data = self._load_pair_rate(from_currency, to_currency)
            if pair_data is None:
                raise RateUnavailableError(from_currency, to_currency)
            rate_value, updated_at = pair_data
            if self._is_stale(updated_at, ttl_seconds):
                raise ApiRequestError("Не удалось обновить курсы")

        updated_display = "неизвестно"
        if updated_at:
            try:
                normalized = updated_at.replace("Z", "+00:00")
                dt = datetime.fromisoformat(normalized)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc)
                updated_display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError, AttributeError):
                updated_display = updated_at

        lines = [
            f"    Курс {from_currency}→{to_currency}: {rate_value:.8f} "
            f"(обновлено: {updated_display})"
        ]

        if rate_value is not None and rate_value != 0:
            reverse_rate = 1.0 / rate_value
            lines.append(
                f"    Обратный курс {to_currency}→{from_currency}: {reverse_rate:.2f}"
            )

        return "\n".join(lines)

    def list_cached_rates(
        self,
        currency_filter: Optional[str] = None,
        base_filter: Optional[str] = None,
        top_n: Optional[int] = None,
    ) -> str:
        payload = self.database.load_rates()
        pairs = payload.get("pairs", {})

        if not pairs:
            return (
                "Локальный кеш курсов пуст. Выполните 'update-rates', чтобы "
                "загрузить данные."
            )

        currency_code = None
        pair_code = None
        if currency_filter:
            normalized = currency_filter.upper()
            if "_" in normalized:
                pair_code = normalized
            else:
                currency_code = normalized
                get_currency(currency_code)

        base_code = None
        if base_filter:
            base_code = base_filter.upper()
            get_currency(base_code)

        entries: List[Tuple[str, float]] = []

        for pair_name, info in pairs.items():
            if not isinstance(info, dict):
                continue

            rate_value = info.get("rate")
            try:
                rate_float = float(rate_value)
            except (TypeError, ValueError):
                continue

            from_code, sep, to_code = pair_name.partition("_")
            if not sep:
                continue

            if pair_code and pair_name != pair_code:
                continue

            if currency_code and from_code != currency_code:
                continue

            if base_code and to_code != base_code:
                continue

            entries.append((pair_name, rate_float))

        if not entries:
            if pair_code:
                return f"Курс для '{pair_code}' не найден в кеше."
            if currency_code:
                return f"Курс для '{currency_code}' не найден в кеше."
            return "По заданным фильтрам курсы не найдены."

        if top_n is not None:
            entries.sort(key=lambda item: item[1], reverse=True)
            entries = entries[:top_n]
        else:
            entries.sort(key=lambda item: item[0])

        last_refresh = payload.get("last_refresh") or "н/д"
        lines = [f"Курсы из кеша (обновление {last_refresh}):"]

        for pair_name, rate_value in entries:
            if rate_value >= 1:
                formatted_rate = f"{rate_value:.2f}"
            else:
                formatted_rate = f"{rate_value:.5f}".rstrip("0").rstrip(".")
            lines.append(f"- {pair_name}: {formatted_rate}")

        return "\n".join(lines)
