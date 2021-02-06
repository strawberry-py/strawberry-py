import datetime
from typing import Union

import discord
from discord.ext import commands

from core import text

tr = text.Translator(__file__).translate


class Text:
    """Text manipulation functions"""

    @staticmethod
    def sanitise(string: str, *, limit: int = 2000, escape: bool = True) -> str:
        """Sanitise string.

        Arguments
        ---------
        string: A text string to sanitise.
        limit: How many characters should be processed.
        allow_markdown: Whether to escape characters (to prevent unwanted markdown)
        """
        if escape:
            string = discord.utils.escape_markdown(string)
        return string.replace("@", "@\u200b")[:limit]


class Time:
    """Time manipulation functions"""

    @staticmethod
    def id_to_datetime(snowflake_id: int) -> datetime.datetime:
        """Convert snowflake ID to timestamp."""
        return datetime.fromtimestamp(((snowflake_id >> 22) + 1420070400000) / 1000)

    @staticmethod
    def date(timestamp: datetime.datetime) -> str:
        """Convert timestamp to date."""
        return timestamp.strftime("%Y-%m-%d")

    @staticmethod
    def datetime(timestamp: datetime.datetime) -> str:
        """Convert timestamp to date and time."""
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def seconds(time: int) -> str:
        """Convert seconds to time."""
        time = int(time)
        D = 3600 * 24
        H = 3600
        M = 60

        d = int((time - (time % D)) / D)
        h = int((time - (time % H)) / H)
        m = int((time - (time % M)) / M)
        s = time % 60

        if d > 0:
            return f"{d} d, {h:02}:{m:02}:{s:02}"
        if h > 0:
            return f"{h}:{m:02}:{s:02}"
        return f"{m:02}:{s:02}"


class Discord:
    """Discord object utils"""

    @staticmethod
    def create_embed(
        *, error: bool = False, author: Union[discord.Member, discord.User] = None, **kwargs
    ) -> discord.Embed:
        """Create discord embed

        Arguments
        ---------
        error: Whether the embed reports an error.
        author: Event author.
        kwargs: Additional parameters.

        Returns
        -------
        The created embed.
        """
        embed = discord.Embed(
            title=kwargs.get("title", None),
            description=kwargs.get("description", None),
            color=kwargs.get(
                "color",
                discord.Color.red() if error else discord.Color.green(),
            ),
        )

        # footer
        footer = tr("create_embed", "footer") + " " + author.display_name
        if kwargs.get("footer", None):
            footer += " | " + kwargs.get("footer")
        embed.set_footer(
            icon_url=author.avatar_url,
            text=footer,
        )
        embed.timestamp = datetime.datetime.now(tz=datetime.timezone.utc)

        return embed

    @staticmethod
    async def send_help(ctx: commands.Context) -> bool:
        """Send help if no subcommand has been invoked.

        Arguments
        ---------
        ctx: The command context

        Returns
        -------
        True if the help was sent, else False.
        """
        if not hasattr(ctx, "command") or not hasattr(ctx.command, "qualified_name"):
            return False
        if ctx.invoked_subcommand is not None:
            return False

        await ctx.send_help(ctx.command.qualified_name)
        return True

    @staticmethod
    async def delete_message(message: discord.Message, delay: float = 0.0) -> bool:
        """Try to remove message.

        Arguments
        ---------
        message: The message to be deleted.
        delay: How long to wait, in seconds.

        Returns
        -------
        True if the action was successful, else False.
        """
        try:
            await message.delete(delay=delay)
        except discord.HTTPException:
            return False
        return True

    @staticmethod
    async def remove_reaction(message: discord.Message, emoji, member: discord.Member) -> bool:
        """Try to remove reaction.

        Arguments
        ---------
        message: The message of the reaction.
        emoji: Emoji, Reaction, PartialEmoji or string.
        member: The author of the reaction.

        Returns
        -------
        True if the action was successful, else False.
        """
        try:
            await message.remove_reaction(emoji, member)
        except discord.HTTPException:
            return False
        return True
