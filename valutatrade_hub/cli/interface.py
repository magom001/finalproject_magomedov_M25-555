"""
Модуль interface.py содержит REPL интерфейс для ValutaTrade Hub.
Только парсинг команд - вся бизнес-логика в usecases.py.
"""

import readline  # noqa: F401
import shlex
from typing import Any, Dict

from ..core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    ValidationError,
    ValutaTradeError,
)
from ..core.usecases import PortfolioUseCases, RateUseCases, Session, UserUseCases


# ANSI-коды цветов
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"


SOURCE_ALIASES = {
    "coingecko": "CoinGecko",
    "coin": "CoinGecko",
    "gecko": "CoinGecko",
    "exchangerate": "ExchangeRate-API",
    "exchange": "ExchangeRate-API",
    "exchange-rate": "ExchangeRate-API",
    "exchange_rate": "ExchangeRate-API",
}

SOURCE_DISPLAY = {
    "coingecko": "CoinGecko",
    "exchangerate": "ExchangeRate-API",
}


class CLI:
    """REPL интерфейс для ValutaTrade Hub."""

    def __init__(self):
        self.session = Session()
        self.user_cases = UserUseCases(self.session)
        self.portfolio_cases = PortfolioUseCases(self.session)
        self.rate_cases = RateUseCases(self.session)
        self.running = True

    def _parse_command_line(self, line: str) -> Dict[str, Any]:
        """Парсинг строки команды с использованием shlex."""
        try:
            args = shlex.split(line)
        except ValueError as e:
            raise ValueError(f"Ошибка парсинга команды: {e}")

        if not args:
            return {"command": None}

        command = args[0]
        params = {}

        i = 1
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    params[key] = args[i + 1]
                    i += 2
                else:
                    params[key] = True
                    i += 1
            else:
                i += 1

        return {"command": command, **params}

    def _print_help(self):
        """Вывести справку по командам."""
        c = Colors
        print(
            f"\n{c.BOLD}{c.CYAN}╔══════════════════════════════════════════════════════════╗"
            f"{c.RESET}"
        )
        print(
            f"{c.BOLD}{c.CYAN}║{c.RESET}  {c.BOLD}ValutaTrade Hub{c.RESET} "
            f"- Управление валютными операциями  {c.CYAN}║{c.RESET}"
        )
        print(
            f"{c.BOLD}{c.CYAN}╚══════════════════════════════════════════════════════════╝"
            f"{c.RESET}\n"
        )

        print(f"{c.BOLD}{c.YELLOW}Команды:{c.RESET}")
        print(
            f"  {c.GREEN}register{c.RESET}       {c.DIM}--username <имя> "
            f"--password <пароль>{c.RESET}"
        )
        print(
            f"  {c.GREEN}login{c.RESET}          {c.DIM}--username <имя> "
            f"--password <пароль>{c.RESET}"
        )
        print(f"  {c.GREEN}show-portfolio{c.RESET} {c.DIM}[--base <валюта>]{c.RESET}")
        print(
            f"  {c.GREEN}buy{c.RESET}            {c.DIM}--currency <код> "
            f"--amount <кол-во>{c.RESET}"
        )
        print(
            f"  {c.GREEN}sell{c.RESET}           {c.DIM}--currency <код> "
            f"--amount <кол-во>{c.RESET}"
        )
        print(
            f"  {c.GREEN}get-rate{c.RESET}       {c.DIM}--from <код> "
            f"--to <код>{c.RESET}"
        )
        print(
            f"  {c.GREEN}update-rates{c.RESET}   {c.DIM}[--source "
            f"{'|'.join(SOURCE_DISPLAY.keys())}]{c.RESET}"
        )
        print(
            f"  {c.GREEN}show-rates{c.RESET}     {c.DIM}[--currency <код>] "
            f"[--base <код>] [--top <N>]{c.RESET}"
        )
        print(f"  {c.GREEN}help{c.RESET}")
        print(f"  {c.GREEN}exit{c.RESET}")

    def _handle_currency_not_found_error(self, error: CurrencyNotFoundError):
        """
        Обработать ошибку CurrencyNotFoundError с подсказками.

        Args:
            error: Исключение CurrencyNotFoundError
        """
        print(f"{error.short}")
        print(f"   {error.detail}")
        print(self._get_supported_currencies())

    def _handle_api_request_error(self, error: ApiRequestError):
        """
        Обработать ошибку ApiRequestError с подсказками.

        Args:
            error: Исключение ApiRequestError
        """
        print(f"{error.short}")
        print(f"   {error.detail}")
        print("\nРекомендации:")
        print("   - Проверьте подключение к интернету")
        print("   - Повторите попытку позже")

    def _execute_command(self, parsed: Dict[str, Any]):
        """Выполнить команду (только диспетчеризация) с глобальной обработкой ошибок."""
        command = parsed.get("command")

        if not command:
            return

        if command in ["exit"]:
            self.running = False
            print("До свидания!")
            return

        if command == "help":
            self._print_help()
            return

        command_method = getattr(self, f"_cmd_{command.replace('-', '_')}", None)
        if command_method:
            try:
                command_method(parsed)
            except CurrencyNotFoundError as e:
                self._handle_currency_not_found_error(e)
            except ApiRequestError as e:
                self._handle_api_request_error(e)
            except ValutaTradeError as e:
                print(str(e))
        else:
            print(f"Неизвестная команда: {command}")
            print("Введите 'help' для списка доступных команд")

    def _cmd_register(self, args: Dict[str, Any]):
        """Обработчик команды register."""
        username = args.get("username")
        password = args.get("password")

        if not username:
            print("Ошибка: Не указан параметр --username")
            return
        if not password:
            print("Ошибка: Не указан параметр --password")
            return

        message = self.user_cases.register_user(username, password)
        print(message)

    def _cmd_login(self, args: Dict[str, Any]):
        """Обработчик команды login."""
        username = args.get("username")
        password = args.get("password")

        if not username:
            print("Ошибка: Не указан параметр --username")
            return
        if not password:
            print("Ошибка: Не указан параметр --password")
            return

        message = self.user_cases.login_user(username, password)
        print(message)

    def _cmd_show_portfolio(self, args: Dict[str, Any]):
        """Обработчик команды show-portfolio."""
        base_currency = args.get("base", "USD")
        message = self.portfolio_cases.show_portfolio(base_currency)
        print(message)

    def _cmd_buy(self, args: Dict[str, Any]):
        """Обработчик команды buy."""
        currency = args.get("currency")
        amount_str = args.get("amount")

        if not currency:
            print("Ошибка: Не указан параметр --currency")
            return
        if not amount_str:
            print("Ошибка: Не указан параметр --amount")
            return

        try:
            amount = float(amount_str)
        except ValueError:
            print(f"Ошибка: Неверный формат числа '{amount_str}'")
            return

        message = self.portfolio_cases.buy_currency(currency, amount)
        print(message)

    def _cmd_sell(self, args: Dict[str, Any]):
        """Обработчик команды sell."""
        currency = args.get("currency")
        amount_str = args.get("amount")

        if not currency:
            print("Ошибка: Не указан параметр --currency")
            return
        if not amount_str:
            print("Ошибка: Не указан параметр --amount")
            return

        try:
            amount = float(amount_str)
        except ValueError:
            print(f"Ошибка: Неверный формат числа '{amount_str}'")
            return

        message = self.portfolio_cases.sell_currency(currency, amount)
        print(message)

    def _cmd_get_rate(self, args: Dict[str, Any]):
        """Обработчик команды get-rate."""
        from_currency = args.get("from")
        to_currency = args.get("to")

        if not from_currency:
            print("Ошибка: Не указан параметр --from")
            return
        if not to_currency:
            print("Ошибка: Не указан параметр --to")
            return

        message = self.rate_cases.get_exchange_rate(from_currency, to_currency)
        print(message)

    def _cmd_update_rates(self, args: Dict[str, Any]):
        """Обработчик команды update-rates."""
        source_arg = args.get("source")
        source_filter = None

        if source_arg:
            normalized = source_arg.lower()
            source_filter = SOURCE_ALIASES.get(normalized)
            if source_filter is None:
                available = ", ".join(sorted(SOURCE_DISPLAY.keys()))
                print(
                    "Ошибка: неизвестный источник. Доступны значения: "
                    f"{available}"
                )
                return

        message = self.rate_cases.update_rates(source_filter)
        print(message)

    def _cmd_show_rates(self, args: Dict[str, Any]):
        """Обработчик команды show-rates."""
        currency_filter = args.get("currency")
        base_filter = args.get("base")
        top_filter = args.get("top")

        top_n = None
        if top_filter is not None:
            try:
                top_n = int(top_filter)
            except ValueError as exc:
                raise ValidationError(
                    "Некорректный параметр",
                    f"Некорректное значение для --top: '{top_filter}'",
                ) from exc

            if top_n <= 0:
                raise ValidationError(
                    "Некорректный параметр",
                    "Параметр --top должен быть положительным целым числом",
                )

        message = self.rate_cases.list_cached_rates(
            currency_filter=currency_filter,
            base_filter=base_filter,
            top_n=top_n,
        )
        print(message)

    def run_repl(self):
        """Запустить REPL цикл."""
        self._print_help()

        while self.running:
            try:
                if self.session.is_logged_in():
                    prompt = f"[{self.session.current_user.username}] > "
                else:
                    prompt = "> "

                line = input(prompt).strip()

                if not line:
                    continue

                parsed = self._parse_command_line(line)
                self._execute_command(parsed)

            except Exception as e:
                print(f"Неожиданная ошибка: {e}")


def main():
    """Точка входа в CLI."""
    cli = CLI()

    cli.run_repl()


if __name__ == "__main__":
    main()
