import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

import git
import git.exc
import sqlalchemy

import discord
from discord import app_commands
from discord.ext import commands

import pie.exceptions
from pie import check, database, i18n, logger, utils

from .database import LastError, Subscription

_ = i18n.Translator("modules/base").translate
bot_log = logger.Bot.logger()
guild_log = logger.Guild.logger()


IGNORED_EXCEPTIONS = [
    commands.CommandNotFound,
    app_commands.CommandNotFound,
    # See pie/spamchannel/
    # This function ensures that the check function fails AND YET does not return
    # information that the user does not have permission to invoke the command.
    # They most likely do, but they have exceeded the limit for spam channel controlled
    # commands (soft version), or are not allowed to run this kind of command in general
    # (hard version).
    pie.exceptions.SpamChannelException,
]


class ReportTraceback:
    """Whether to send traceback to log channel or not.

    The values are "flipped", because the boolean decides if the traceback
    should be ignored or not.
    """

    YES = False
    NO = True


class Errors(commands.Cog):
    """Error handling module."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_tree_error
        discord.ui.View.on_error = self.on_ui_error
        discord.ui.Modal.on_error = self.on_ui_error

    async def on_ui_error(
        self, itx: discord.Interaction, error: Exception, item=None
    ) -> None:
        await self.on_tree_error(itx=itx, error=error)

    @commands.guild_only()
    @check.acl2(check.ACLevel.SUBMOD)
    @commands.group(name="error-meme")
    async def error_meme_(self, ctx):
        """Manage traceback meme."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.MOD)
    @error_meme_.command(name="subscribe")
    async def error_meme_subscribe(self, ctx):
        """Subscribe current channel to traceback meme."""
        result = Subscription.add(ctx.guild.id, ctx.channel.id)
        if not result:
            await ctx.reply(_(ctx, "This channel is already subscribed."))
            return

        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"#{ctx.channel.name} subscribed to the error meme.",
        )
        await ctx.reply(_(ctx, "Channel subscribed."))

    @check.acl2(check.ACLevel.MOD)
    @error_meme_.command(name="unsubscribe")
    async def error_meme_unsubscribe(self, ctx):
        """Unsubscribe current channel from traceback meme."""
        result = Subscription.remove(ctx.guild.id, ctx.channel.id)
        if not result:
            await ctx.reply(_(ctx, "This channel is not subscribed."))
            return

        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"#{ctx.channel.name} unsubscribed from the error meme.",
        )
        await ctx.reply(_(ctx, "Channel unsubscribed."))

    @check.acl2(check.ACLevel.SUBMOD)
    @error_meme_.command(name="list")
    async def error_meme_list(self, ctx):
        """List channels that are subscribed to the traceback meme."""
        results = Subscription.get_all(ctx.guild.id)
        if not results:
            await ctx.reply(_(ctx, "No channel is subscribed."))
            return

        class Item:
            def __init__(self, result: Subscription):
                channel = ctx.guild.get_channel(result.channel_id)
                if channel:
                    self.channel = f"#{channel.name}"
                else:
                    self.channel = f"#{result.channel_id}"

        channels = [Item(result) for result in results]
        table: List[str] = utils.text.create_table(
            channels,
            header={"channel": _(ctx, "Channel")},
        )
        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.BOT_OWNER)
    @error_meme_.command(name="trigger")
    async def error_meme_trigger(self, ctx):
        """Test the error meme functionality.

        This command skips the date check and will trigger the embed even if
        the last embed occured today.
        """
        await self.send_error_meme(test=True)

    async def send_error_meme(self, *, test: bool = False):
        today = datetime.date.today()
        last = LastError.get()
        if last and today <= last.date and not test:
            # Last error occured today, do not announce anything
            return
        if last is not None:
            last = last.dump()
        else:
            last = {"date": today}
        count: int = (today - last["date"]).days

        if not test:
            await bot_log.debug(self.bot.user, None, "Updating day of last error.")
            LastError.set()

        image_path = Path(__file__).parent / "accident.jpg"
        with image_path.open("rb") as handle:
            data = BytesIO(handle.read())

        for subscriber in Subscription.get_all(None):
            channel = self.bot.get_channel(subscriber.channel_id)
            if not channel:
                continue

            gtx = i18n.TranslationContext(guild_id=subscriber.guild_id, user_id=None)
            embed = utils.discord.create_embed(
                error=True,
                title=_(gtx, "{count} days without an accident.").format(count=count),
                description=_(
                    gtx, "Previous error occured on **{date}**. Resetting counter..."
                ).format(date=last["date"].strftime("%Y-%m-%d")),
            )
            if test:
                embed.add_field(
                    name="\u200b",
                    value=_(gtx, "*This is a test embed, no error has occured yet.*"),
                )
            embed.set_image(url="attachment://accident.jpg")
            data.seek(0)

            await channel.send(
                file=discord.File(fp=data, filename="accident.jpg"),
                embed=embed,
            )

    async def on_tree_error(
        self, itx: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle bot exceptions."""
        # Recursion prevention
        if getattr(itx.command, "on_error", None):
            print(itx.command.on_error)
            return

        error: Exception = self.get_correct_error(error)

        if type(error) in IGNORED_EXCEPTIONS:
            return

        # Exception handling
        title, content, ignore_traceback = await Errors.handle_exceptions(itx, error)

        # Exception logging
        await Errors.handle_log(
            itx,
            error,
            title=title,
            content=content,
            ignore_traceback=ignore_traceback,
        )

        if not ignore_traceback:
            await self.send_error_meme()

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """Handle bot exceptions."""
        # Recursion prevention
        if getattr(ctx.command, "on_error", None) or getattr(
            ctx.command, "on_command_error", None
        ):
            return

        error: Exception = self.get_correct_error(error)

        # Getting the *original* exception is difficult.
        # Because of how the library is built, walking up the stacktrace gets messy
        # by entering '_run_event' and other internal functions. This means that this
        # 'error' is the last line that raised an exception, not the initial cause.
        # Tracebacks are logged, this is good enough.

        if type(error) in IGNORED_EXCEPTIONS:
            return

        # Exception handling
        title, content, ignore_traceback = await Errors.handle_exceptions(ctx, error)

        # Exception logging
        await Errors.handle_log(
            ctx,
            error,
            title=title,
            content=content,
            ignore_traceback=ignore_traceback,
        )

        if not ignore_traceback:
            await self.send_error_meme()

    @staticmethod
    async def handle_exceptions(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles creating embed titles and descriptions of various exceptions

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, pie.exceptions.StrawberryException):
            return await Errors.handle_StrawberryException(utx, error)

        # Discord errors
        if isinstance(error, discord.DiscordException):
            return await Errors.handle_DiscordException(utx, error)

        if isinstance(error, sqlalchemy.exc.SQLAlchemyError):
            return await Errors.handle_DatabaseException(utx, error)

        if isinstance(error, git.exc.GitError):
            return await Errors.handle_GitException(utx, error)

        # Other errors
        return (
            type(error).__name__,
            _(utx, "An unexpected error occurred"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_GitException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by strawberry-py

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        return (
            type(error).__name__,
            str(error),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_StrawberryException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by strawberry-py

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        error_messages = {
            "StrawberryException": _(utx, "strawberry.py exception"),
            "DotEnvException": _(utx, "An environment variable is missing"),
            "ModuleException": _(utx, "Module exception"),
            "BadTranslation": _(utx, "Translation error"),
        }
        title = error_messages.get(
            type(error).__name__,
            _(utx, "An unexpected error occurred"),
        )
        return (
            title,
            str(error),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_DatabaseException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by SQLAlchemy

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        database.session.rollback()
        database.session.commit()
        await bot_log.critical(
            None,
            None,
            "strawberry.py database session rolled back. The bubbled-up cause is:\n"
            + "\n".join([f"| {line}" for line in str(error).split("\n")]),
        )

        return (
            _(utx, "Database error!"),
            _(utx, "Database has been restored, changes were rolled back.").format(),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_DiscordException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by Discord

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, discord.GatewayNotFound):
            return (
                _(utx, "Error"),
                _(utx, "Gateway not found"),
                ReportTraceback.YES,
            )

        # Exception raised when error 429 occurs and the timeout is greater than
        # configured maximum in `max_ratelimit_timeout`
        if isinstance(error, discord.RateLimited) or isinstance(
            error, app_commands.CommandOnCooldown
        ):
            return (
                _(utx, "Slow down"),
                _(utx, "Request has to be sent at least {delay} seconds later").format(
                    delay=round(error.retry_after)
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, discord.ClientException):
            return await Errors.handle_ClientException(utx, error)

        if isinstance(error, discord.HTTPException):
            return await Errors.handle_HTTPException(utx, error)

        if isinstance(error, commands.ExtensionError):
            return await Errors.handle_ExtensionError(utx, error)

        if isinstance(error, app_commands.AppCommandError):
            return await Errors.handle_AppCommandError(utx, error)

        if isinstance(error, commands.CommandError):
            return await Errors.handle_CommandError(utx, error)

        return (
            _(utx, "Error"),
            _(utx, "Internal error"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_ClientException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by the Client

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, discord.InvalidData):
            return (
                _(utx, "Client error"),
                _(utx, "Invalid data"),
                ReportTraceback.YES,
            )

        if isinstance(error, discord.LoginFailure):
            return (
                _(utx, "Client error"),
                _(utx, "Login failure"),
                ReportTraceback.YES,
            )

        if isinstance(error, discord.ConnectionClosed):
            return (
                _(utx, "Client error"),
                _(utx, "Connection closed"),
                ReportTraceback.YES,
            )

        if isinstance(error, discord.PrivilegedIntentsRequired):
            return (
                _(utx, "Client error"),
                _(utx, "Privileged intents required"),
                ReportTraceback.YES,
            )

        # Interaction sent multiple responses for one event
        if isinstance(error, discord.InteractionResponded):
            return (
                _(utx, "Client error"),
                _(utx, "Response from **{interaction}** was already received").format(
                    interaction=error.command.name if error.command else "unknown"
                ),
                ReportTraceback.YES,
            )

        if isinstance(error, commands.CommandRegistrationError):
            return (
                _(utx, "Client error"),
                _(utx, "Error on registering the command **{cmd}**").format(
                    cmd=error.name
                ),
                ReportTraceback.NO,
            )

        return (
            _(utx, "Error"),
            _(utx, "Client error"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_HTTPException(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by the HTTP connection to the Discord API.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """

        if isinstance(error, discord.Forbidden):
            return (
                _(utx, "HTTP Exception"),
                _(utx, "Forbidden"),
                ReportTraceback.NO,
            )

        if isinstance(error, discord.NotFound):
            return (
                _(utx, "HTTP Exception"),
                _(utx, "NotFound"),
                ReportTraceback.NO,
            )

        if isinstance(error, discord.DiscordServerError):
            return (
                _(utx, "HTTP Exception"),
                _(utx, "Discord Server Error"),
                ReportTraceback.NO,
            )

        return (
            _(utx, "Internal error"),
            _(utx, "Network error"),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_ExtensionError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by strawberry-py extensions

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        # return friendly name: strip "modules." prefix and ".module" suffix
        extension_name = error.name[8:-7]

        if isinstance(error, commands.ExtensionAlreadyLoaded):
            return (
                _(utx, "User input error"),
                _(utx, "Extension **{extension}** is already loaded").format(
                    extension=extension_name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ExtensionNotLoaded):
            return (
                _(utx, "User input error"),
                _(utx, "The extension **{extension}** is not loaded").format(
                    extension=extension_name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.NoEntryPointError):
            return (
                _(utx, "Extension error"),
                _(utx, "Extension **{extension}** does not have an entry point").format(
                    extension=extension_name
                ),
                ReportTraceback.YES,
            )

        if isinstance(error, commands.ExtensionFailed):
            return (
                _(utx, "Extension error"),
                _(utx, "**{extension}** failed").format(extension=extension_name),
                ReportTraceback.YES,
            )

        if isinstance(error, commands.ExtensionNotFound):
            return (
                _(utx, "User input error"),
                _(utx, "The extension **{extension}** could not be found").format(
                    extension=extension_name,
                ),
                ReportTraceback.NO,
            )

        return (
            _(utx, "Internal error"),
            _(utx, "Extension error"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_AppCommandError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by app commands

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """

        if isinstance(error, app_commands.CheckFailure):
            return await Errors.handle_CheckFailure(utx, error)

        if isinstance(error, app_commands.CommandInvokeError):
            return (
                _(utx, "Command error"),
                _(utx, "Command invoke error"),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.TranslationError):
            return (
                _(utx, "Command translation error"),
                _(utx, "Command translation error"),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.TransformerError):
            return (
                _(utx, "AppCommand transformer error"),
                _(
                    utx,
                    "Transformer `{transformer}` failed to transform value `{value}` into type `{type}`.",
                ).format(
                    transformer=type(error.transformer).__name__,
                    value=error.value,
                    type=error.type.name,
                )
                + (
                    _(utx, "Cause: {cause}").format(
                        cause=type(error.__cause__).__name__
                    )
                    if getattr(error, "__cause__ ", None)
                    else ""
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, app_commands.CommandLimitReached):
            return (
                _(utx, "Command limit reached"),
                _(utx, "Discord command limit for bot reached"),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.CommandAlreadyRegistered):
            return (
                _(utx, "Command already registered"),
                _(
                    utx, "Command {name} is already registered. Guild ID: {guild_id}."
                ).format(name=error.name, guild_id=getattr(error, "guild_id", 0)),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.CommandSignatureMismatch):
            return (
                _(utx, "Command error"),
                _(utx, "Command definition differs from the one provided to Discord."),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.MissingApplicationID):
            return (
                _(utx, "Command error"),
                _(utx, "Client is missing application ID"),
                ReportTraceback.YES,
            )

        if isinstance(error, app_commands.CommandSyncFailure):
            return (
                _(utx, "Command error"),
                _(utx, "Command sync failure"),
                ReportTraceback.YES,
            )

    @staticmethod
    async def handle_CommandError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by commands

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """

        if isinstance(error, commands.ConversionError):
            return (
                _(utx, "Command error"),
                _(utx, "Conversion to **{name}** resulted in **{exception}**").format(
                    name=error.converter.__name__.rstrip("Converter"),
                    exception=type(error.original).__name__,
                ),
                ReportTraceback.YES,
            )

        if isinstance(error, commands.CommandNotFound):
            return (
                _(utx, "Command error"),
                _(utx, "Command not found"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.DisabledCommand):
            return (
                _(utx, "Command error"),
                _(utx, "The command is not available"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.CommandInvokeError):
            return (
                _(utx, "Command error"),
                _(utx, "Command invoke error"),
                ReportTraceback.YES,
            )

        if isinstance(error, commands.CommandOnCooldown):
            time: str = utils.time.format_seconds(error.retry_after)
            return (
                _(utx, "Command error"),
                _(utx, "Slow down. Wait **{time}**").format(time=time),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MaxConcurrencyReached):
            return (
                _(utx, "Command error"),
                _(utx, "This command is already running multiple times")
                + "\n"
                + _(utx, "The limit is **{num}**/**{per}**").format(
                    num=error.number,
                    per=error.per.name,
                ),
                ReportTraceback.NO,
            )

        # HybridCommand raises an AppCommandError derived exception that could
        # not be sufficiently converted to an equivalent CommandError exception.
        if isinstance(error, commands.HybridCommandError):
            return await Errors.handle_AppCommandError(utx, error.original)
        if isinstance(error, commands.UserInputError):
            return await Errors.handle_UserInputError(utx, error)

        if isinstance(error, commands.CheckFailure):
            return await Errors.handle_CheckFailure(utx, error)

        return (
            _(utx, "Internal error"),
            _(utx, "Command error"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_CheckFailure(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by command checks.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """

        if isinstance(error, pie.exceptions.NegativeUserOverwrite):
            return (
                _(utx, "Check failure"),
                _(utx, "You have been denied the invocation of this command"),
                ReportTraceback.NO,
            )

        if isinstance(error, pie.exceptions.NegativeChannelOverwrite):
            return (
                _(utx, "Check failure"),
                _(utx, "This command cannot be used in this channel"),
                ReportTraceback.NO,
            )

        if isinstance(error, pie.exceptions.NegativeRoleOverwrite):
            return (
                _(utx, "Check failure"),
                _(utx, "This command cannot be used by the role **{role}**").format(
                    role=error.role.name
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, pie.exceptions.InsufficientACLevel):
            return (
                _(utx, "Check failure"),
                _(
                    utx,
                    "You need access permissions at least at level **{required}**, "
                    "you only have **{actual}**",
                ).format(required=error.required.name, actual=error.actual.name),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.CheckAnyFailure):
            return (
                _(utx, "Check failure"),
                _(
                    utx,
                    "You do not have any of the possible permissions to access this command",
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.PrivateMessageOnly):
            return (
                _(utx, "Check failure"),
                _(utx, "This command can only be used in private messages"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.NoPrivateMessage) or isinstance(
            error, app_commands.NoPrivateMessage
        ):
            return (
                _(utx, "Check failure"),
                _(utx, "This command cannot be used in private messages"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.NotOwner):
            return (
                _(utx, "Check failure"),
                _(utx, "You are not the bot owner"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingPermissions) or isinstance(
            error, app_commands.MissingPermissions
        ):
            return (
                _(utx, "Check failure"),
                _(utx, "You need all of the following permissions: {perms}").format(
                    perms=", ".join(f"**{p}**" for p in error.missing_perms)
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BotMissingPermissions) or isinstance(
            error, app_commands.BotMissingPermissions
        ):
            return (
                _(utx, "Check failure"),
                _(utx, "I need all of the following permissions: {perms}").format(
                    perms=", ".join(f"`{p}`" for p in error.missing_perms)
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingRole) or isinstance(
            error, app_commands.MissingRole
        ):
            return (
                _(utx, "Check failure"),
                _(utx, "You need to have role **{role}**").format(
                    role=error.missing_role.name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BotMissingRole):
            return (
                _(utx, "Check failure"),
                _(utx, "I need to have role **{role}**").format(
                    role=error.missing_role.name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingAnyRole) or isinstance(
            error, app_commands.MissingAnyRole
        ):
            return (
                _(utx, "Check failure"),
                _(utx, "You need some of the following roles: {roles}").format(
                    roles=", ".join(f"**{r.name}**" for r in error.missing_roles)
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BotMissingAnyRole):
            return (
                _(utx, "Check failure"),
                _(utx, "I need some of the following roles: {roles}").format(
                    roles=", ".join(f"**{r.name}**" for r in error.missing_roles)
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.NSFWChannelRequired):
            return (
                _(utx, "Check failure"),
                _(utx, "This command can be used only in NSFW channels"),
                ReportTraceback.NO,
            )

        return (
            _(utx, "Check failure"),
            _(utx, "You don't have permission for this"),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_UserInputError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by user input.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, commands.MissingRequiredArgument):
            return (
                _(utx, "User input error"),
                _(utx, "The command has to have an argument **{param}**").format(
                    param=error.param.name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingRequiredAttachment):
            return (
                _(utx, "User input error"),
                _(utx, "Argument **{param}** must include an attachment").format(
                    param=error.param
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.TooManyArguments):
            return (
                _(utx, "User input error"),
                _(utx, "The command doesn't have that many arguments"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadUnionArgument):
            classes: str = "/".join([f"**{cls.__name__}**" for cls in error.converters])
            return (
                _(utx, "User input error"),
                _(utx, "Argument **{argument}** must be {classes}").format(
                    argument=error.param.name, classes=classes
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadLiteralArgument):
            return (
                _(utx, "User input error"),
                _(
                    utx,
                    "Argument **{argument}** only takes one of the following values:",
                ).format(argument=error.param)
                + " "
                + "/".join(f"**{literal}**" for literal in error.literals),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadArgument):
            return await Errors.handle_BadArgument(utx, error)

        if isinstance(error, commands.ArgumentParsingError):
            return await Errors.handle_ArgumentParsingError(utx, error)

        return (
            _(utx, "Internal error"),
            _(utx, "User input error"),
            ReportTraceback.YES,
        )

    @staticmethod
    async def handle_BadArgument(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by bad user input.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        argument: str = getattr(error, "argument", "?")
        argument = discord.utils.escape_markdown(argument)
        # prevent attacker abuse
        argument = argument[:256]

        if isinstance(error, commands.MessageNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Message **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MemberNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Member **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.GuildNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Server **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.UserNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "User **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ChannelNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Channel **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ChannelNotReadable):
            return (
                _(utx, "Bad argument"),
                _(utx, "Channel **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadColourArgument):
            return (
                _(utx, "Bad argument"),
                _(utx, "Color **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.RoleNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Role **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadInviteArgument):
            return (
                _(utx, "Bad argument"),
                _(utx, "Invitation **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.EmojiNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Emoji **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.PartialEmojiConversionFailure):
            return (
                _(utx, "Bad argument"),
                _(utx, "Emoji **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.GuildStickerNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Sticker **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ScheduledEventNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Event **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.BadBoolArgument):
            return (
                _(utx, "Bad argument"),
                _(utx, "**{argument}** is not boolean").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.RangeError):
            brackets: Tuple[str, str] = ("\u27e8", "\u27e9")
            infinity: str = "\u221e"
            return (
                _(utx, "Bad argument"),
                _(
                    utx,
                    "**{value}** is not from interval "
                    "**{lbr}{minimum}, {maximum}{rbr}**",
                ).format(
                    value=error.value,  # FIXME This may need escaping
                    lbr=brackets[0],
                    minimum=error.minimum or infinity,
                    maximum=error.maximum or infinity,
                    rbr=brackets[1],
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ThreadNotFound):
            return (
                _(utx, "Bad argument"),
                _(utx, "Thread **{argument}** not found").format(argument=argument),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.FlagError):
            return Errors.handle_FlagError(utx, error)

        return (
            _(utx, "User input error"),
            _(utx, "Bad argument"),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_ArgumentParsingError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by bad user input.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, commands.UnexpectedQuoteError):
            return (
                _(utx, "Argument parsing error"),
                _(utx, "Unexpected quote error"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.InvalidEndOfQuotedStringError):
            return (
                _(utx, "Argument parsing error"),
                _(utx, "Invalid end of quoted string error"),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.ExpectedClosingQuoteError):
            return (
                _(utx, "Argument parsing error"),
                _(utx, "Unexpected quote error"),
                ReportTraceback.NO,
            )

        return (
            _(utx, "User input error"),
            _(utx, "Argument parsing error"),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_FlagError(
        utx: discord.Interaction | commands.Context, error
    ) -> Tuple[str, str, bool]:
        """Handles exceptions raised by bad user input.

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.

        Returns:
            Tuple[str, str, bool]:
                Translated error name,
                Translated description,
                Whether to ignore traceback in the log.
        """
        if isinstance(error, commands.BadFlagArgument):
            return (
                _(utx, "Bad argument"),
                _(
                    utx,
                    "Argument **{argument}** could not be converted to **{flag}**: {exception}",
                ).format(
                    argument=error.argument,
                    flag=error.flag.name,
                    exception=type(error.original).__name__,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingFlagArgument):
            return (
                _(utx, "Bad argument"),
                _(utx, "Argument **{flag}** must have value").format(
                    flag=error.flag.name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.TooManyFlags):
            return (
                _(utx, "Bad argument"),
                _(utx, "Argument **{flag}** cannot take that many values").format(
                    flag=error.flag.name,
                ),
                ReportTraceback.NO,
            )

        if isinstance(error, commands.MissingRequiredFlag):
            return (
                _(utx, "Bad argument"),
                _(utx, "Argument **{flag}** must be specified").format(
                    flag=error.flag.name,
                ),
                ReportTraceback.NO,
            )

        return (
            _(utx, "User input error"),
            _(utx, "Bad argument"),
            ReportTraceback.NO,
        )

    @staticmethod
    async def handle_log(
        utx: discord.Interaction | commands.Context,
        error,
        title: str,
        content: str,
        ignore_traceback: bool = False,
    ):
        """Handles the exception logging

        Args:
            utx: The invocation context / interaction.
            error: Detected exception.
            title: Translated error name
            content: Translated description
            ignore_traceback: Whether to ignore traceback in the log. Defaults to False.
        """

        author = utx.author if isinstance(utx, commands.Context) else utx.user

        embed = utils.discord.create_embed(
            author=author, error=True, title=title, description=content
        )
        if not ignore_traceback:
            embed.add_field(
                name=_(utx, "Error content"),
                value=str(error),
                inline=False,
            )

        if isinstance(utx, commands.Context):
            await utx.send(embed=embed)
        elif utx.response.is_done():
            await utx.followup.send(embed=embed)
        else:
            await utx.response.send_message(embed=embed, ephemeral=True)

        # Log the error
        if not ignore_traceback:
            await bot_log.error(
                author,
                utx.channel,
                f"{type(error).__name__}: {str(error)}",
                content=(
                    utx.message.content if isinstance(utx, commands.Context) else None
                ),
                exception=error,
            )

    def get_correct_error(self, error):
        # Getting the *original* exception is difficult.
        # Because of how the library is built, walking up the stacktrace gets messy
        # by entering '_run_event' and other internal functions. This means that this
        # 'error' is the last line that raised an exception, not the initial cause.
        # Tracebacks are logged, this is good enough.
        original_error = None

        if getattr(error, "original", None):
            original_error = error.original
        elif getattr(error, "__cause__", None):
            original_error = error.__cause__

        if original_error:
            if not isinstance(error, discord.DiscordException):
                error = original_error
            elif isinstance(original_error, git.exc.GitError):
                error = original_error
            elif isinstance(original_error, commands.errors.ExtensionAlreadyLoaded):
                error = original_error
            elif isinstance(original_error, commands.errors.ExtensionNotFound):
                error = original_error
            elif isinstance(original_error, commands.errors.ExtensionNotLoaded):
                error = original_error

        return error


async def setup(bot) -> None:
    await bot.add_cog(Errors(bot))
