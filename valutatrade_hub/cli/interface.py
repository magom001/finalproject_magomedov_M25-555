"""
Модуль interface.py содержит REPL интерфейс для ValutaTrade Hub.
Только парсинг команд - вся бизнес-логика в usecases.py.
"""

import readline  # noqa: F401
import shlex
from typing import Any, Dict

from ..core.exceptions import ValutaTradeError
from ..core.usecases import PortfolioUseCases, RateUseCases, Session, UserUseCases


# ANSI color codes
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"


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
        print(f"  {c.GREEN}help{c.RESET}")
        print(f"  {c.GREEN}exit{c.RESET}")

    def _execute_command(self, parsed: Dict[str, Any]):
        """Выполнить команду (только диспетчеризация)."""
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
            command_method(parsed)
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

        try:
            message = self.user_cases.register_user(username, password)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

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

        try:
            message = self.user_cases.login_user(username, password)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

    def _cmd_show_portfolio(self, args: Dict[str, Any]):
        """Обработчик команды show-portfolio."""
        base_currency = args.get("base", "USD")
        try:
            message = self.portfolio_cases.show_portfolio(base_currency)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

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

        try:
            message = self.portfolio_cases.buy_currency(currency, amount)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

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

        try:
            message = self.portfolio_cases.sell_currency(currency, amount)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

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

        try:
            message = self.rate_cases.get_exchange_rate(from_currency, to_currency)
            print(message)
        except ValutaTradeError as e:
            print(str(e))

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
