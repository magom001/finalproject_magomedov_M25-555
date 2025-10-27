"""Инструменты настройки и получения логгеров приложения ValutaTrade Hub."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .settings import get_settings


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Настройка системы логирования приложения.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Если None, берется из конфигурации.
        log_file: Путь к файлу логов. Если None, берется из конфигурации.
        log_format: Формат лог-сообщений. Если None, берется из конфигурации.

    Returns:
        Настроенный logger для доменных операций
    """
    # Получаем настройки
    settings = get_settings()

    if log_level is None:
        log_level = settings.get("log_level", "INFO")

    if log_file is None:
        log_file = settings.get("log_file", "logs/actions.log")

    if log_format is None:
        log_format = settings.get(
            "log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Создаем директорию для логов если не существует
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Создаем logger
    logger = logging.getLogger("valutatrade.actions")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Удаляем существующие handlers чтобы избежать дублирования
    logger.handlers.clear()

    # Formatter для логов
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%dT%H:%M:%S")

    # File handler с ротацией (максимум 10MB, хранить 5 резервных копий)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # Файл захватывает все уровни
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler (только для WARNING и выше, чтобы не захламлять консоль)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Предотвращаем передачу логов в root logger
    logger.propagate = False

    return logger


def get_action_logger() -> logging.Logger:
    """
    Получить или создать logger для доменных операций.

    Returns:
        Logger для логирования действий пользователей
    """
    logger = logging.getLogger("valutatrade.actions")

    # Если logger еще не настроен, настраиваем его
    if not logger.handlers:
        setup_logging()

    return logger


def get_parser_logger() -> logging.Logger:
    """Получить logger для сервиса парсинга курсов."""
    settings = get_settings()

    log_level = settings.get("parser_log_level", settings.get("log_level", "INFO"))
    log_format = settings.get(
        "log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file = settings.get_parser_log_file_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("valutatrade.parser")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%dT%H:%M:%S")

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False

    return logger


def format_action_log(
    action: str,
    username: str = None,
    user_id: int = None,
    currency: str = None,
    amount: float = None,
    rate: float = None,
    base_currency: str = None,
    result: str = "OK",
    error_type: str = None,
    error_message: str = None,
    extra_context: dict = None,
) -> str:
    """
    Форматирование лог-сообщения для доменных операций.

    Args:
        action: Тип операции (BUY, SELL, REGISTER, LOGIN)
        username: Имя пользователя
        user_id: ID пользователя
        currency: Код валюты
        amount: Количество
        rate: Курс обмена
        base_currency: Базовая валюта
        result: Результат операции (OK/ERROR)
        error_type: Тип ошибки
        error_message: Сообщение об ошибке
        extra_context: Дополнительный контекст (например, состояние кошелька)

    Returns:
        Отформатированная строка для логирования
    """
    parts = [f"{action}"]

    if username:
        parts.append(f"user='{username}'")
    elif user_id:
        parts.append(f"user_id={user_id}")

    if currency:
        parts.append(f"currency='{currency}'")

    if amount is not None:
        parts.append(f"amount={amount:.4f}")

    if rate is not None:
        parts.append(f"rate={rate:.2f}")

    if base_currency:
        parts.append(f"base='{base_currency}'")

    parts.append(f"result={result}")

    if error_type:
        parts.append(f"error_type='{error_type}'")

    if error_message:
        # Экранируем кавычки в сообщении об ошибке
        escaped_message = error_message.replace("'", "\\'")
        parts.append(f"error_message='{escaped_message}'")

    if extra_context:
        for key, value in extra_context.items():
            if isinstance(value, str):
                parts.append(f"{key}='{value}'")
            else:
                parts.append(f"{key}={value}")

    return " ".join(parts)
