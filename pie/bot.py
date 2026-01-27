from __future__ import annotations

import datetime
import importlib
import os
import signal
import sys
import traceback
from enum import Enum
from functools import partial
from typing import Optional

import sqlalchemy

import discord
from discord import app_commands
from discord.ext import commands

from modules.base.admin.database import BaseAdminModule
from pie import database, logger
from pie.cli import COLOR
from pie.database.config import Config
from pie.help import Help

# Constants
MODULE_PATH_TEMPLATE = "modules.{}.module"
CORE_MODULES = (
    "base.acl",
    "base.admin",
    "base.baseinfo",
    "base.errors",
    "base.language",
    "base.logging",
)


class ModuleStatus(Enum):
    """Enum representing possible module loading statuses."""

    LOADED = ("loaded", COLOR.green, "loaded")
    DISABLED = ("disabled", COLOR.yellow, "found, but is disabled")
    NOT_FOUND = ("not_found", COLOR.red, "not found")

    def __init__(self, key: str, color: str, message_suffix: str):
        self.key = key
        self.color = color
        self.message_suffix = message_suffix


class Strawberry(commands.Bot):
    """Main bot class implementing singleton pattern for Discord bot instance.

    Manages bot lifecycle, module loading, error handling, and database integration.
    """

    config: Config
    loaded: bool = False
    _instance: Optional[Strawberry] = None
    exit_code: int = 0

    def __new__(cls):
        """Singleton pattern implementation ensuring only one bot instance exists."""
        if cls._instance is None:
            # Init database before creating instance
            database.init_core()
            database.init_modules()
            cls._instance = super(Strawberry, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the bot with configuration and required intents."""
        # Skip initialization if already initialized
        if hasattr(self, "config"):
            return

        self.token = os.getenv("TOKEN")
        if not self.token:
            raise ValueError("TOKEN environment variable is not set")

        # Load or create config object
        self.config = database.config.Config.get()

        super().__init__(
            allowed_mentions=discord.AllowedMentions(
                roles=False, everyone=False, users=True
            ),
            command_prefix=self.config.prefix,
            help_command=Help(),
            intents=discord.Intents.all(),
        )

        # Setup logging
        self.bot_log = logger.Bot.logger(self)
        self.guild_log = logger.Guild.logger(self)

    async def setup_hook(self):
        """Add asyncio signal handlers (Unix only) and call parent method."""
        # Signal handlers are only available on Unix-like systems
        if sys.platform != "win32":
            self.loop.add_signal_handler(
                signal.SIGINT, partial(self.handle_signal, "received SIGINT")
            )
            self.loop.add_signal_handler(
                signal.SIGTERM, partial(self.handle_signal, "received SIGTERM")
            )
        await super().setup_hook()

    def handle_signal(self, signal_name: str) -> None:
        """Create task to close the bot when interrupt signals are raised.

        :param signal_name: Name of the signal received (e.g., "received SIGINT")
        """
        self.loop.create_task(self.close(signal_name))

    async def update_app_info(self) -> None:
        """Update bot owner information from Discord application info."""
        app: discord.AppInfo = await self.application_info()
        if app.team:
            self.owner_ids = {m.id for m in app.team.members}
        else:
            self.owner_ids = {app.owner.id}

    async def close(self, reason: str = "unknown") -> None:
        """Overrides parent to add logging info on shutdown / close.

        :param reason: Reason for shutting down / closing.
        """
        await self.bot_log.critical(
            None, None, f"The pie is shutting down! Reason: {reason}."
        )
        await super().close()

    async def change_presence(
        self,
        *,
        activity: discord.BaseActivity | None = None,
        status: discord.Status | None = None,
    ) -> None:
        await super().change_presence(
            status=getattr(
                discord.Status, self.config.status if status is None else status
            ),
            activity=discord.Game(
                start=datetime.datetime.now(datetime.UTC),
                name=self.config.prefix + "help",
            ),
        )

    async def on_ready(self) -> None:
        """Handle bot ready event - runs on login and reconnect."""
        # Update information about bot owners
        await self.update_app_info()

        # If the status is set to "auto", let the loop in Admin module take care of it
        status = "invisible" if self.config.status == "auto" else self.config.status
        await self.change_presence(status=status)

        await self.tree.sync()

        if self.loaded:
            await self.bot_log.info(None, None, "Reconnected")
        else:
            print(
                "\n"
                "     (     \n"
                "  (   )  ) \n"
                "   )  ( )  \n"
                "   .....   \n"
                ".:::::::::.\n"
                "~\\_______/~\n"
            )
            await self.bot_log.critical(None, None, "The pie is ready.")
            self.loaded = True

    async def handle_error(
        self, error: Exception, source: Optional[str] = None
    ) -> None:
        """Handle and log uncaught errors with appropriate context.

        :param error: The exception that was raised
        :param source: Optional source identifier where the error occurred
        """
        if isinstance(error, sqlalchemy.exc.SQLAlchemyError):
            database.session.rollback()
            database.session.commit()
            await self.bot_log.critical(
                None,
                None,
                "strawberry.py database session rolled back. The bubbled-up cause is:\n"
                + "\n".join([f"| {line}" for line in str(error).split("\n")]),
            )
        else:
            await self.bot_log.critical(
                None,
                None,
                (
                    "Uncaught error bubbled-up.\n"
                    + (f"Source: {source}.\n" if source else "")
                    + "Traceback: \n"
                    + str(error)
                    + "\n"
                    + "\n".join(traceback.format_tb(error.__traceback__))
                ),
            )

    async def on_error(self, event, *args, **kwargs):
        error_type, error, tb = sys.exc_info()

        await self.handle_error(error)

    async def load_extension(self, name: str, *, package: str | None = None) -> None:
        """We have to override the load_extension function as the default
        implementation causes ModuleNotFoundError in importlib instead of
        expected ExtensionNotFound.
        """
        name = self._resolve_name(name, package)
        if name in self.extensions:
            raise commands.ExtensionAlreadyLoaded(name)

        parts = name.split(".")
        path = parts[0]

        spec = importlib.util.find_spec(path)
        if spec is None:
            raise commands.ExtensionNotFound(name)

        for part in parts[1:]:
            path += f".{part}"
            spec = importlib.util.find_spec(path)
            if spec is None:
                raise commands.ExtensionNotFound(name)
        await self._load_from_module_spec(spec, name)

    def _log_module_status(self, module_name: str, status: ModuleStatus) -> None:
        """Log module loading status with color coding.

        :param module_name: Name of the module
        :param status: ModuleStatus enum indicating the module's loading status
        """
        message = (
            f"Module {status.color}{module_name}{COLOR.none} {status.message_suffix}."
        )
        print(message, file=sys.stdout)

    async def load_modules(self) -> None:
        """Load all core and database-managed modules."""
        db_modules = BaseAdminModule.get_all()
        db_module_names = [m.name for m in db_modules]

        # Load core modules
        for module in CORE_MODULES:
            if module in db_module_names:
                # This module is managed by database
                continue
            try:
                await self.load_extension(MODULE_PATH_TEMPLATE.format(module))
                self._log_module_status(module, ModuleStatus.LOADED)
            except Exception as e:
                await self.bot_log.error(
                    None,
                    None,
                    f"Failed to load core module {module}: {e}\n{''.join(traceback.format_tb(e.__traceback__))}",
                )
                self._log_module_status(module, ModuleStatus.NOT_FOUND)

        # Load database-managed modules
        for module in db_modules:
            if not module.enabled:
                self._log_module_status(module.name, ModuleStatus.DISABLED)
                continue
            try:
                await self.load_extension(MODULE_PATH_TEMPLATE.format(module.name))
                self._log_module_status(module.name, ModuleStatus.LOADED)
            except (ImportError, ModuleNotFoundError, commands.ExtensionNotFound) as e:
                await self.bot_log.warning(
                    None, None, f"Module {module.name} not found: {e}"
                )
                self._log_module_status(module.name, ModuleStatus.NOT_FOUND)
        for command in self.walk_commands():
            if type(command) is not commands.Group:
                command.ignore_extra = False

    async def start(self) -> None:
        await self.load_modules()
        await super().start(self.token)

    def get_all_commands(
        self,
    ) -> dict[str, commands.Command | app_commands.Command | app_commands.ContextMenu]:
        """Get all available bot commands including prefix and app commands.

        :return: Dictionary mapping command names to command objects
        """
        bot_commands = {c.qualified_name: c for c in self.walk_commands()}
        for cmd_type in discord.AppCommandType:
            bot_commands = bot_commands | {
                c.qualified_name: c
                for c in self.tree.walk_commands(type=cmd_type)
                if not isinstance(c, app_commands.Group)
            }

        return bot_commands

    def __ring_key__(self) -> str:
        """Return a hashable key for ring's LRU cache.

        Required to make the bot object compatible with ring caching.
        See pie/acl/__init__.py:map_member_to_ACLevel()

        :return: Static key identifying the bot instance
        """
        return "bot"
