"""
Демонстрация работы паттерна Singleton для SettingsLoader.

Этот скрипт показывает:
1. Гарантию единственного экземпляра
2. Использование синглтона в разных частях приложения
3. Доступ к конфигурации через get()
4. Перезагрузку конфигурации
"""

from valutatrade_hub.infra.settings import SettingsLoader, get_settings


def demonstrate_singleton():
    """Демонстрация паттерна Singleton."""

    print("=" * 60)
    print("ДЕМОНСТРАЦИЯ ПАТТЕРНА SINGLETON")
    print("=" * 60)

    # 1. Создание первого экземпляра
    print("\n1. Создание первого экземпляра:")
    settings1 = SettingsLoader()
    print(f"   settings1 id: {id(settings1)}")
    print(f"   settings1: {settings1}")

    # 2. Попытка создать второй экземпляр
    print("\n2. Попытка создать второй экземпляр:")
    settings2 = SettingsLoader()
    print(f"   settings2 id: {id(settings2)}")
    print(f"   settings2: {settings2}")

    # 3. Проверка что это один и тот же объект
    print("\n3. Проверка идентичности:")
    print(f"   settings1 is settings2: {settings1 is settings2}")
    print(f"   id(settings1) == id(settings2): {id(settings1) == id(settings2)}")

    # 4. Использование через функцию-хелпер
    print("\n4. Использование через get_settings():")
    settings3 = get_settings()
    print(f"   settings3 id: {id(settings3)}")
    print(f"   settings3 is settings1: {settings3 is settings1}")

    print("\n" + "=" * 60)
    print("ДОСТУП К КОНФИГУРАЦИИ")
    print("=" * 60)

    # 5. Получение параметров конфигурации
    settings = get_settings()

    print("\n5. Основные параметры:")
    print(f"   Data directory: {settings.get_data_dir()}")
    print(f"   Users file: {settings.get_users_file_path()}")
    print(f"   Portfolios file: {settings.get_portfolios_file_path()}")
    print(f"   Rates file: {settings.get_rates_file_path()}")

    print("\n6. Параметры курсов:")
    print(f"   Rates TTL: {settings.get_rates_ttl()} секунд")
    print(f"   Default base currency: {settings.get_default_base_currency()}")

    print("\n7. Параметры логирования:")
    log_config = settings.get_log_config()
    print(f"   Log format: {log_config['format']}")
    print(f"   Log level: {log_config['level']}")
    print(f"   Log file: {log_config['file']}")

    print("\n8. Использование get() с дефолтными значениями:")
    print(f"   Существующий ключ: {settings.get('data_dir')}")
    print(f"   Несуществующий ключ: {settings.get('nonexistent_key', 'default_value')}")

    print("\n" + "=" * 60)
    print("ИСПОЛЬЗОВАНИЕ В РАЗНЫХ МОДУЛЯХ")
    print("=" * 60)

    # 9. Симуляция использования в разных модулях
    print("\n9. Симуляция импорта в разных модулях:")

    # Модуль 1
    settings_module1 = get_settings()
    print(f"   Модуль 1 - id: {id(settings_module1)}")

    # Модуль 2
    settings_module2 = get_settings()
    print(f"   Модуль 2 - id: {id(settings_module2)}")

    # Модуль 3
    settings_module3 = SettingsLoader()
    print(f"   Модуль 3 - id: {id(settings_module3)}")

    print(
        f"\n   Все модули используют один экземпляр: "
        f"{settings_module1 is settings_module2 is settings_module3}"
    )

    print("\n" + "=" * 60)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("=" * 60)

    print("\nВыводы:")
    print("✓ Singleton гарантирует единственный экземпляр класса")
    print("✓ Все импорты получают один и тот же объект")
    print("✓ Конфигурация загружается один раз при первом обращении")
    print("✓ Предоставляется удобный API для доступа к параметрам")


if __name__ == "__main__":
    demonstrate_singleton()
