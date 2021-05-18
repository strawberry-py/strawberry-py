import os
import sys
from typing import List

import discord
from discord.ext import commands

import database
import database.config
from core import logging
from modules.base.admin.database import BaseAdminModule


# Setup checks


def test_dotenv() -> None:
    if type(os.getenv("DB_STRING")) != str:
        logger.critical("Environment variable DB_STRING is not set.")
        sys.exit(1)
    if type(os.getenv("TOKEN")) != str:
        logger.critical("Environment variable TOKEN is not set.")
        sys.exit(1)


test_dotenv()


# Move to the script's home directory


root_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(root_path)
del root_path


# Database


database.init_core()
database.init_modules()


# Load or create config object


config = database.config.Config.get()


# Setup discord.py


def _prefix_callable(bot, message) -> List[str]:
    """Get bot prefix with optional mention function"""
    # TODO This should be extended for per-guild prefixes as dict
    # See https://github.com/Rapptz/RoboDanny/blob/rewrite/bot.py:_prefix_callable()
    base = []
    if config.mention_as_prefix:
        user_id = bot.user.id
        base += [f"<@!{user_id}> ", f"<@{user_id}> "]
    # TODO guild condition
    base.append(config.prefix)
    return base


intents = discord.Intents.all()

from core import utils
from core.help import Help

bot = commands.Bot(
    allowed_mentions=discord.AllowedMentions(roles=False, everyone=False, users=True),
    command_prefix=_prefix_callable,
    help_command=Help(),
    intents=intents,
)


# Setup logging


logger = logging.Bot.logger(bot)


# Setup listeners

already_loaded: bool = False


@bot.event
async def on_ready():
    """This is run on login and on reconnect."""
    global already_loaded

    # If the status is set to "auto", let the loop in Admin module take care of it
    status = "invisible" if config.status == "auto" else config.status
    await utils.Discord.update_presence(bot, status=status)

    if already_loaded:
        logger.info(None, None, "Reconnected")
    else:
        logger.info(None, None, "The pie is ready.")
        already_loaded = True


# Add required modules


modules = {
    "base.base",
    "base.errors",
    "base.admin",
}
db_modules = BaseAdminModule.get_all()
db_module_names = [m.name for m in db_modules]

for module in modules:
    if module in db_module_names:
        # This module is managed by database
        continue
    bot.load_extension(f"modules.{module}.module")
    logger.info(None, None, "Loaded module " + module)

for module in db_modules:
    if not module.enabled:
        logger.debug(None, None, "Skipping module " + module.name)
        continue
    bot.load_extension(f"modules.{module.name}.module")
    logger.info(None, None, "Loaded module " + module.name)


# Run the bot

bot.run(os.getenv("TOKEN"))
