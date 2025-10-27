# ValutaTrade Hub

ValutaTrade Hub — консольное приложение для отслеживания портфеля валют и криптоактивов. Пользователь регистрируется, ведёт кошельки в разных валютах, получает биржевые курсы и может симулировать сделки покупки и продажи.

## Структура проекта

```
valutatrade_hub/
  cli/            # REPL-интерфейс и командный парсер
  core/           # доменные модели, use case и исключения
  infra/          # инфраструктура: БД, настройки, логирование
  parser_service/ # сервис обновления курсов из внешних API
data/             # JSON-хранилище пользователей, портфелей и курсов
logs/             # файлы логов приложения и парсера
Makefile          # основные команды для разработки
```

## Установка

1. Убедитесь, что установлен Python 3.10+ и Poetry.
2. Выполните установку зависимостей (создаст виртуальную среду Poetry):

```bash
make install
```

## Запуск CLI

После установки активируйте REPL интерфейс одной из команд:

```bash
make project
```

CLI стартует с подсказкой по доступным командам и поддерживает историю ввода.

### Примеры команд

```
register --username alice --password secret
login --username alice --password secret
buy --currency BTC --amount 0.01
sell --currency EUR --amount 100
show-portfolio --base USD
get-rate --from BTC --to USD
update-rates --source coingecko
show-rates --currency BTC --top 5
```

Каждая команда сообщает об успехе или выводит дружелюбное описание ошибки.

## Кэш курсов и TTL

- Актуальные курсы сохраняются в `data/rates.json` c полем `last_refresh`.
- История обновлений накапливается в `data/exchange_rates.json`.
- Время жизни (TTL) кэша задаётся ключом `rates_ttl_seconds` в `config.json` (по умолчанию 3600 секунд) и читается через `SettingsLoader`.

При запросе курса (`get-rate`) система проверяет, не устарели ли данные; при необходимости автоматически инициирует обновление.

## Parser Service

Сервис `parser_service` объединяет несколько источников (CoinGecko, ExchangeRate-API) и обновляет локальный кэш.

1. Пропишите токен ExchangeRate-API в файле `.env` или переменной окружения:

	```
	EXCHANGERATE_API_KEY=<ВАШ ТОКЕН>
	```

2. Запуск команды:

	```bash
	update-rates          # опрос всех источников
	update-rates --source coingecko
	```

3. Логи парсера пишутся в `logs/parser.log` с ротацией.

## Дополнительно

- Настройки приложения находятся в `config.json`; `SettingsLoader` подставляет разумные значения по умолчанию.
- Для проверки кода используйте `make lint` или `make lint-fix`.
- Сборка wheel-пакета: `make build`.
