from __future__ import annotations

import datetime
import importlib
import os
import sys
import traceback

import sqlalchemy

import discord
from discord.ext import commands

from modules.base.admin.database import BaseAdminModule
from pie import database, logger
from pie.cli import COLOR
from pie.database.config import Config
from pie.help import Help


class Strawberry(commands.Bot):
    config: Config
    loaded: bool = False
    bot: Strawberry

    def __new__(cls):
        if not hasattr(cls, "bot"):
            # Init database
            database.init_core()
            database.init_modules()
            cls.bot = super(Strawberry, cls).__new__(cls)
        return cls.bot

    def __init__(self):
        self.token = os.getenv("TOKEN")

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

    async def update_app_info(self):
        # Update bot information
        app: discord.AppInfo = await self.application_info()
        if app.team:
            self.owner_ids = {m.id for m in app.team.members}
        else:
            self.owner_ids = {app.owner.id}

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

    async def on_ready(self):
        """This is run on login and on reconnect."""

        # Update information about user's owners
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

    async def handle_error(self, error: Exception, source: str = None):
        # Make sure we rollback the database session if we encounter an error
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
        #  if name in self._BotBase__extensions:
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

    async def load_modules(self):
        modules = (
            "base.acl",
            "base.admin",
            "base.baseinfo",
            "base.errors",
            "base.language",
            "base.logging",
        )
        db_modules = BaseAdminModule.get_all()
        db_module_names = [m.name for m in db_modules]

        for module in modules:
            if module in db_module_names:
                # This module is managed by database
                continue
            await self.load_extension(f"modules.{module}.module")
            print(
                f"Module {COLOR.green}{module}{COLOR.none} loaded.",
                file=sys.stdout,
            )  # noqa: T001

        for module in db_modules:
            if not module.enabled:
                print(
                    f"Module {COLOR.yellow}{module.name}{COLOR.none} found, but is disabled.",
                    file=sys.stdout,
                )  # noqa: T001
                continue
            try:
                await self.load_extension(f"modules.{module.name}.module")
            except (ImportError, ModuleNotFoundError, commands.ExtensionNotFound):
                print(
                    f"Module {COLOR.red}{module.name}{COLOR.none} not found.",
                    file=sys.stdout,
                )  # noqa: T001
                continue
            print(
                f"Module {COLOR.green}{module.name}{COLOR.none} loaded.",
                file=sys.stdout,
            )  # noqa: T001

        for command in self.walk_commands():
            if type(command) is not commands.Group:
                command.ignore_extra = False

    async def start(self) -> None:
        await self.load_modules()
        await super().start(self.token)

    # This is required to make the 'bot' object hashable by ring's LRU cache
    # See pie/acl/__init__.py:map_member_to_ACLevel()
    def __ring_key__(self):
        return "bot"
