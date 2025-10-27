"""
Пакет ValutaTrade Hub - система управления валютными портфелями.
"""

from .core.currencies import initialize_default_currencies

# Инициализируем реестр валют при импорте пакета
initialize_default_currencies()
