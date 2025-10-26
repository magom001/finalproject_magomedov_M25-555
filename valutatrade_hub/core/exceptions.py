"""
Модуль exceptions.py содержит пользовательские исключения.
"""


class ValutaTradeError(Exception):
    """Базовое исключение для приложения ValutaTrade Hub."""

    def __init__(self, short: str, detail: str):
        """
        Args:
            short: Короткое описание ошибки
            detail: Детальное описание ошибки
        """
        self.short = short
        self.detail = detail
        super().__init__(detail)

    def __str__(self) -> str:
        """Форматировать ошибку."""
        return f"{self.short} →\n{self.detail}"


class ValidationError(ValutaTradeError):
    """Исключение для ошибок валидации входных данных."""

    pass


class AuthenticationError(ValutaTradeError):
    """Исключение для ошибок аутентификации."""

    pass


class BusinessLogicError(ValutaTradeError):
    """Исключение для ошибок бизнес-логики."""

    pass


# Специфичные ошибки аутентификации
class UnauthenticatedError(AuthenticationError):
    """Пользователь не залогинен."""

    def __init__(self):
        super().__init__("Не залогинен", "Сначала выполните login")


class UserNotFoundError(AuthenticationError):
    """Пользователь не найден."""

    def __init__(self, username: str):
        super().__init__(
            "Пользователь не найден", f"Пользователь '{username}' не найден"
        )


class InvalidPasswordError(AuthenticationError):
    """Неверный пароль."""

    def __init__(self):
        super().__init__("Неверный пароль", "Неверный пароль")


# Специфичные ошибки валидации
class EmptyValueError(ValidationError):
    """Пустое значение."""

    def __init__(self, field: str):
        super().__init__(f"Пустое поле {field}", f"{field} не может быть пустым")


class ShortPasswordError(ValidationError):
    """Короткий пароль."""

    def __init__(self):
        super().__init__("Короткий пароль", "Пароль должен быть не короче 4 символов")


class UsernameExistsError(ValidationError):
    """Имя пользователя уже занято."""

    def __init__(self, username: str):
        super().__init__(
            "Имя занято", f"Пользователь с именем '{username}' уже существует"
        )


class NegativeValueError(ValidationError):
    """Отрицательное значение."""

    def __init__(self, field: str):
        super().__init__(
            "Некорректная сумма", f"'{field}' должен быть положительным числом"
        )


class UnknownCurrencyError(ValidationError):
    """Неизвестная валюта."""

    def __init__(self, currency: str):
        super().__init__(
            "Неизвестная базовая валюта", f"Неизвестная базовая валюта '{currency}'"
        )


# Специфичные ошибки бизнес-логики
class WalletNotFoundError(BusinessLogicError):
    """Кошелёк не найден."""

    def __init__(self, currency: str):
        super().__init__(
            "Кошелёк не найден",
            f"У вас нет кошелька '{currency}'. "
            f"Добавьте валюту: она создаётся автоматически при первой покупке.",
        )


class InsufficientFundsError(BusinessLogicError):
    """Недостаточно средств."""

    def __init__(self, currency: str, available: float, required: float):
        super().__init__(
            "Недостаточно средств",
            f"Недостаточно средств: доступно {available:.4f} {currency}, "
            f"требуется {required:.4f} {currency}",
        )


class RateUnavailableError(BusinessLogicError):
    """Курс недоступен."""

    def __init__(self, from_currency: str, to_currency: str):
        super().__init__(
            "Не удалось получить курс",
            f"Не удалось получить курс для {from_currency}→{to_currency}",
        )
