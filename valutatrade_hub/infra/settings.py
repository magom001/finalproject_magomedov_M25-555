import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import dotenv_values, load_dotenv


class SettingsLoader:
    """
    Singleton класс для загрузки и кеширования конфигурации проекта.

    Отвечает за:
    - Загрузку конфигурации из config.json
    - Кеширование конфигурации
    - Предоставление доступа к параметрам через метод get()
    - Перезагрузку конфигурации по требованию

    Реализация через __new__:
    Выбран метод __new__ вместо метакласса по следующим причинам:
    - Простота и читабельность кода
    - Нет необходимости в сложной метаклассовой магии
    - Достаточно для гарантии единственного экземпляра
    - Легче понимать и поддерживать для других разработчиков
    """

    _instance: Optional["SettingsLoader"] = None
    _initialized: bool = False

    def __new__(cls) -> "SettingsLoader":
        """
        Создает или возвращает единственный экземпляр класса.

        Returns:
            Единственный экземпляр SettingsLoader
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Инициализирует настройки (выполняется только один раз).
        """
        # Предотвращаем повторную инициализацию
        if SettingsLoader._initialized:
            return

        # Определяем пути
        self._project_root = Path(__file__).parent.parent.parent
        self._config_path = self._project_root / "config.json"
        self._env_path = self._project_root / ".env"

        # Словарь для хранения конфигурации
        self._config: Dict[str, Any] = {}
        self._env_cache: Dict[str, str] = {}

        # Дефолтные значения
        self._defaults = {
            "data_dir": str(self._project_root / "data"),
            "users_file": "users.json",
            "portfolios_file": "portfolios.json",
            "rates_file": "rates.json",
            "exchange_rates_file": "exchange_rates.json",
            "rates_ttl_seconds": 3600,  # 1 час
            "default_base_currency": "USD",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "log_level": "INFO",
            "log_file": str(self._project_root / "logs" / "app.log"),
            "parser_log_file": str(self._project_root / "logs" / "parser.log"),
        }

        # Загружаем переменные среды
        self._load_env()

        # Загружаем конфигурацию
        self._load_config()

        # Отмечаем что инициализация завершена
        SettingsLoader._initialized = True

    def _load_env(self):
        """Загружает переменные окружения из файла .env."""
        self._env_cache.clear()

        if not self._env_path.exists():
            load_dotenv()
            return

        try:
            load_dotenv(self._env_path, override=False)
            values = dotenv_values(self._env_path)
            for key, value in values.items():
                if value is None:
                    continue
                self._env_cache[key] = value
        except OSError as exc:
            print(f"Предупреждение: не удалось загрузить .env: {exc}")

    def _load_config(self):
        """
        Загружает конфигурацию из config.json.

        Если файл не существует, создает его с дефолтными значениями.
        """
        # Начинаем с дефолтных значений
        self._config = self._defaults.copy()

        # Пытаемся загрузить из config.json
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)

                # Объединяем с дефолтными значениями
                self._config.update(user_config)

            except (FileNotFoundError, json.JSONDecodeError) as e:
                # Если файл невалиден, используем дефолты
                print(f"Предупреждение: не удалось загрузить config.json: {e}")
                print("Используются дефолтные настройки")
        else:
            # Создаем config.json с дефолтными значениями
            self._save_config()

    def _save_config(self):
        """
        Сохраняет текущую конфигурацию в config.json.
        """
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Предупреждение: не удалось сохранить config.json: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Получить значение конфигурации по ключу.

        Args:
            key: Ключ конфигурации
            default: Значение по умолчанию, если ключ не найден

        Returns:
            Значение конфигурации или default

        Examples:
            >>> settings = SettingsLoader()
            >>> data_dir = settings.get("data_dir")
            >>> ttl = settings.get("rates_ttl_seconds", 3600)
        """
        return self._config.get(key, default)

    def reload(self):
        """
        Перезагружает конфигурацию из pyproject.toml.

        Полезно если конфигурация была изменена в runtime.

        Examples:
            >>> settings = SettingsLoader()
            >>> # ... изменения в pyproject.toml ...
            >>> settings.reload()
        """
        self._load_env()
        self._load_config()

    def get_data_dir(self) -> Path:
        """
        Получить путь к директории с данными.

        Returns:
            Path объект директории данных
        """
        return Path(self.get("data_dir"))

    def get_users_file_path(self) -> Path:
        """
        Получить полный путь к файлу пользователей.

        Returns:
            Path объект файла пользователей
        """
        return self.get_data_dir() / self.get("users_file")

    def get_portfolios_file_path(self) -> Path:
        """
        Получить полный путь к файлу портфелей.

        Returns:
            Path объект файла портфелей
        """
        return self.get_data_dir() / self.get("portfolios_file")

    def get_rates_file_path(self) -> Path:
        """
        Получить полный путь к файлу курсов валют.

        Returns:
            Path объект файла курсов
        """
        return self.get_data_dir() / self.get("rates_file")

    def get_exchange_rates_file_path(self) -> Path:
        """
        Получить путь к файлу истории курсов валют.

        Returns:
            Path объект файла истории курсов
        """
        return self.get_data_dir() / self.get("exchange_rates_file")

    def get_rates_ttl(self) -> int:
        """
        Получить время жизни курсов в секундах.

        Returns:
            Время жизни курсов (TTL) в секундах
        """
        return self.get("rates_ttl_seconds", 3600)

    def get_default_base_currency(self) -> str:
        """
        Получить дефолтную базовую валюту.

        Returns:
            Код базовой валюты (например, "USD")
        """
        return self.get("default_base_currency", "USD")

    def get_log_config(self) -> Dict[str, str]:
        """
        Получить конфигурацию логирования.

        Returns:
            Словарь с параметрами логирования
        """
        return {
            "format": self.get("log_format"),
            "level": self.get("log_level"),
            "file": self.get("log_file"),
        }

    def get_parser_log_file_path(self) -> Path:
        """Получить путь к файлу логов сервиса парсинга."""
        return Path(self.get("parser_log_file"))

    def get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Получить значение переменной окружения, учитывая кэш .env."""
        if key in self._env_cache:
            return self._env_cache[key]
        return os.getenv(key, default)

    def get_exchangerate_api_key(self) -> Optional[str]:
        """Вернуть API ключ сервиса ExchangeRate-API из окружения."""
        return self.get_env("EXCHANGERATE_API_KEY")

    def __repr__(self) -> str:
        """Строковое представление конфигурации."""
        return f"<SettingsLoader(config_keys={list(self._config.keys())})>"


def get_settings() -> SettingsLoader:
    """
    Получить экземпляр SettingsLoader.

    Функция-хелпер для удобного доступа к синглтону.

    Returns:
        Единственный экземпляр SettingsLoader

    Examples:
        >>> settings = get_settings()
        >>> data_dir = settings.get_data_dir()
    """
    return SettingsLoader()
