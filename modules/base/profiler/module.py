import os
import tempfile
import zipfile
from datetime import datetime

import dotenv

import discord
from discord import app_commands
from discord.ext import commands, tasks

from pie import check, i18n, logger, utils
from pie.bot import Strawberry

_ = i18n.Translator(__file__).translate
bot_log = logger.Bot.logger()

RESULT_PATH = "profiler_results.html"


class Profiler(
    commands.GroupCog,
    name="profiler",
    description="Configure profiler and download the results.",
):
    def __init__(self, bot: Strawberry):
        self.bot = bot
        self.log.start()

    @property
    def profiler_running(self):
        return "PROFILER_RUNNING" in os.environ

    @property
    def profiler_enabled(self):
        return os.getenv("PROFILER_ENABLED", "False") == "True"

    @tasks.loop(seconds=2.0, count=1)
    async def log(self) -> None:
        if self.profiler_running:
            await bot_log.critical(
                None,
                None,
                "The profiler is running! Restart bot to stop the profiler and gather the results!",
            )

    @log.before_loop
    async def before_log(self):
        await self.bot.wait_until_ready()

    @check.acl2(check.ACLevel.BOT_OWNER)
    @app_commands.command(name="status", description="Show profiler status.")
    async def profiler_status(self, itx: discord.Interaction):
        if self.profiler_running:
            await itx.response.send_message(
                _(
                    itx,
                    "Profiler is running. The results will be available after bot restart.",
                ),
                ephemeral=True,
            )
            return

        if self.profiler_enabled:
            await itx.response.send_message(
                _(
                    itx,
                    "Profiler is enabled. The profiling will start after bot restart.",
                ),
                ephemeral=True,
            )
            return

        await itx.response.send_message(
            _(itx, "Profiler is disabled and is not running."), ephemeral=True
        )

    @check.acl2(check.ACLevel.BOT_OWNER)
    @app_commands.command(
        name="enable",
        description="Enable profiler. The profiler will be run after bot restart.",
    )
    async def profiler_enable(self, itx: discord.Interaction):
        if self.profiler_running:
            await itx.response.send_message(
                _(itx, "Profiler is already enabled and running."), ephemeral=True
            )
            return

        if self.profiler_enabled:
            await itx.response.send_message(
                _(
                    itx,
                    "Profiler is already enabled. The profiling will start after bot restart.",
                ),
                ephemeral=True,
            )
            return

        await itx.response.defer(thinking=True, ephemeral=True)

        dotenv.set_key(
            dotenv_path=".env",
            key_to_set="PROFILER_ENABLED",
            value_to_set="True",
            quote_mode="never",
            export=False,
        )
        os.environ["PROFILER_ENABLED"] = "True"

        message = _(
            itx, "Profiler is enabled. The profiling will start after bot restart."
        )
        report_exists: bool = os.path.isfile(RESULT_PATH)
        if report_exists:
            message += "\n" + _(itx, "**Profiler results found!**")
            message += "\n" + _(
                itx,
                "Please make sure that you download them before restart, otherwise it will be overwriten!",
            )

        await (await itx.original_response()).edit(content=message)
        await bot_log.info(itx.user, itx.channel, "Profiler was enabled.")

    @check.acl2(check.ACLevel.BOT_OWNER)
    @app_commands.command(name="disable", description="Disable profiler.")
    async def profiler_disable(self, itx: discord.Interaction):
        if self.profiler_running:
            await itx.response.send_message(
                _(
                    itx,
                    "Profiler is currently running and will be automatically disabled after bot restart.",
                ),
                ephemeral=True,
            )
            return

        if not self.profiler_enabled:
            await itx.response.send_message(
                _(itx, "Profiler is already disabled."), ephemeral=True
            )
            return

        dotenv.set_key(
            dotenv_path=".env",
            key_to_set="PROFILER_ENABLED",
            value_to_set="False",
            quote_mode="never",
            export=False,
        )
        os.environ["PROFILER_ENABLED"] = "False"

        await itx.response.send_message(_(itx, "Profiler is disabled."), ephemeral=True)
        await bot_log.info(itx.user, itx.channel, "Profiler was disabled.")

    @check.acl2(check.ACLevel.BOT_OWNER)
    @app_commands.command(
        name="download", description="Download profiler results as ZIP file."
    )
    async def profiler_download(self, itx: discord.Interaction):
        report_exists: bool = os.path.isfile(RESULT_PATH)
        if not report_exists:
            await itx.response.send_message(
                _(
                    itx,
                    "No report found. You must enable the profiler, "
                    "restart the bot, let it gather the data and "
                    "restart the bot again to get the results.",
                ),
                ephemeral=True,
            )
            return

        await itx.response.defer(ephemeral=True, thinking=True)

        created = utils.time.format_datetime(
            datetime.fromtimestamp(os.path.getmtime(RESULT_PATH))
        )

        with tempfile.TemporaryFile() as tmpfile:
            with zipfile.ZipFile(tmpfile, "w", zipfile.ZIP_LZMA) as archive:
                archive.write(RESULT_PATH)
            print(tmpfile.tell())

            tmpfile.seek(0)

            await (await itx.original_response()).edit(
                content=_(itx, "Here's the latest report from {created}.").format(
                    created=created
                ),
                attachments=[discord.File(tmpfile, "result.zip")],
            )
        await bot_log.info(itx.user, itx.channel, "Profiler results were sent to user.")


async def setup(bot: Strawberry) -> None:
    await bot.add_cog(Profiler(bot))
