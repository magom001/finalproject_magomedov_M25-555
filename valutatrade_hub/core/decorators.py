"""Декораторы для логирования действий и расширения поведения use case."""

import functools
import inspect
from typing import Any, Callable

from ..infra.logging_config import format_action_log, get_action_logger


def log_action(action_type: str, verbose: bool = False):
    """
    Декоратор для логирования доменных операций (BUY/SELL/REGISTER/LOGIN).

    Args:
        action_type: Тип операции (BUY, SELL, REGISTER, LOGIN)
        verbose: Если True, добавляет дополнительный контекст
                 (например, состояние кошелька до/после)

    Пример записи в лог:
        INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC' amount=0.0500
             rate=59300.00 base='USD' result=OK
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_action_logger()

            # Получаем self (первый аргумент метода)
            self_obj = args[0] if args else None

            # Извлекаем информацию о пользователе
            username = None
            user_id = None

            if self_obj and hasattr(self_obj, "session"):
                current_user = getattr(self_obj.session, "current_user", None)
                if current_user:
                    username = getattr(current_user, "username", None)
                    user_id = getattr(current_user, "user_id", None)

            # Получаем параметры функции
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            params = bound_args.arguments

            # Извлекаем параметры для логирования
            currency = params.get("currency") or params.get("from_currency")
            amount = params.get("amount")
            password_param = params.get("password")

            # Для операций REGISTER/LOGIN извлекаем username из параметров
            if action_type in ["REGISTER", "LOGIN"] and not username:
                username = params.get("username")

            # Скрываем пароль
            if password_param:
                params["password"] = "****"

            # Дополнительный контекст для verbose режима
            extra_context = {}
            if verbose and action_type in ["BUY", "SELL"]:
                # Попытка получить состояние кошелька до операции
                if self_obj and hasattr(self_obj, "database"):
                    try:
                        portfolio = self_obj.database.find_portfolio_by_user_id(user_id)
                        if portfolio and currency:
                            wallet = portfolio.get_wallet(currency)
                            if wallet:
                                extra_context["balance_before"] = (
                                    f"{wallet.balance:.4f}"
                                )
                    except Exception:
                        pass  # Игнорируем ошибки при получении контекста

            try:
                # Выполняем функцию
                result = func(*args, **kwargs)

                # Пытаемся извлечь rate из результата или базы данных
                rate = None
                base_currency = "USD"  # По умолчанию

                if (
                    action_type in ["BUY", "SELL"]
                    and self_obj
                    and hasattr(self_obj, "database")
                ):
                    try:
                        rate = self_obj.database.get_rate(currency, base_currency)
                    except Exception:
                        pass

                # Для verbose режима добавляем состояние после
                if verbose and action_type in ["BUY", "SELL"] and extra_context:
                    if self_obj and hasattr(self_obj, "database"):
                        try:
                            portfolio = self_obj.database.find_portfolio_by_user_id(
                                user_id
                            )
                            if portfolio and currency:
                                wallet = portfolio.get_wallet(currency)
                                if wallet:
                                    extra_context["balance_after"] = (
                                        f"{wallet.balance:.4f}"
                                    )
                        except Exception:
                            pass

                # Логируем успешную операцию
                log_message = format_action_log(
                    action=action_type,
                    username=username,
                    user_id=user_id,
                    currency=currency,
                    amount=amount,
                    rate=rate,
                    base_currency=base_currency if rate else None,
                    result="OK",
                    extra_context=extra_context if extra_context else None,
                )
                logger.info(log_message)

                return result

            except Exception as e:
                # Логируем ошибку
                error_type = type(e).__name__
                error_message = str(e)

                log_message = format_action_log(
                    action=action_type,
                    username=username,
                    user_id=user_id,
                    currency=currency,
                    amount=amount,
                    result="ERROR",
                    error_type=error_type,
                    error_message=error_message,
                    extra_context=extra_context if extra_context else None,
                )
                logger.error(log_message)

                # Пробрасываем исключение дальше
                raise

        return wrapper

    return decorator
