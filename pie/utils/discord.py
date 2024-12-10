import datetime
from typing import Optional, Union

import discord
from discord.ext import commands


async def get_message(
    bot: commands.Bot,
    guild_or_user_id: int,
    channel_id: int,
    message_id: int,
    use_cache: bool = True,
) -> Optional[discord.Message]:
    """Get message.

    By default if the message is contained in bot cache,
    it is returned from it, to save API calls.
    Otherwise (if not found or use_cache is False) it is fetched.

    :param bot: The :class:`~discord.ext.commands.Bot` object.
    :param guild_or_user_id: Guild ID or User ID (if the message is in DMs).
    :param channel_id: Channel ID.
    :param message_id: Message ID.
    :param use_cache: When False, always fetches the message (default: True).
    :return: Found message or ``None``.
    """
    if use_cache:
        query = [m for m in bot.cached_messages if m.id == message_id]
        if len(query) == 1:
            return query[0]

    try:
        guild = bot.get_guild(guild_or_user_id)
        if guild is not None:
            channel = guild.get_channel(channel_id)
            if channel is None:
                # The 'channel' may also be a thread
                channel = discord.utils.get(guild.threads, id=channel_id)
            if channel is None:
                return None
        else:
            # DMs?
            channel = bot.get_user(guild_or_user_id)
            if channel is None:
                return
        return await channel.fetch_message(message_id)
    except discord.errors.HTTPException:
        return None


def split_message_url(bot: commands.Bot, message_url: str):
    """Get message.

    Extracts Guild, Channel and Message ID from URL

    :param bot: The :class:`~discord.ext.commands.Bot` object.
    :param message_url: URL of the message
    :return: Touple containing Guild, Channel and Message IDs or ``None`` if URL is not correct.
    """
    try:
        parts = message_url.split("/")
        guild_id = int(parts[-3])
        channel_id = int(parts[-2])
        message_id = int(parts[-1])
    except (ValueError, IndexError):
        return None

    return (guild_id, channel_id, message_id)


def message_url_from_reaction_payload(payload: discord.RawReactionActionEvent):
    guild_id = payload.guild_id if payload.guild_id is not None else "@me"
    return f"https://discord.com/channels/{guild_id}/{payload.channel_id}/{payload.message_id}"


def create_embed(
    *,
    error: bool = False,
    author: Union[discord.Member, discord.User] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    footer: Optional[str] = None,
    color: Optional[Union[int, discord.Colour]] = None,
    url: Optional[str] = None,
) -> discord.Embed:
    """Create discord embed.

    :param error: Whether the embed reports an error.
    :param author: Event author.
    :param title: Title for embed, max 256 characters.
    :param description: Description, max 4096 characters.
    :param footer: Footer, max 2048 characters.
    :param color: Embed color. Must be an int for a RGB color or Discord Colour class.
    :param url: The URL of the embed.
    :return: The created embed.

    If you supply ``title``, ``description``, ``color`` or ``footer``, they
    will be included in the embed.
    """
    if color is None:
        color = discord.Color.red() if error else discord.Color.green()

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        url=url,
    )

    # footer
    base_footer = "📩 "
    if author is not None:
        base_footer += f" {author.display_name}"
    if footer is not None:
        base_footer += " | " + footer
    embed.set_footer(
        icon_url=getattr(author, "avatar_url", None),
        text=base_footer,
    )
    embed.timestamp = datetime.datetime.now(tz=datetime.timezone.utc)

    return embed


async def send_help(ctx: commands.Context) -> bool:
    """Send help if no subcommand has been invoked.

    :param ctx: The command context.
    :return: ``True`` if the help was sent, ``False`` otherwise.
    """
    if not hasattr(ctx, "command") or not hasattr(ctx.command, "qualified_name"):
        return False
    if ctx.invoked_subcommand is not None:
        return False

    await ctx.send_help(ctx.command.qualified_name)
    return True


async def delete_message(message: discord.Message, delay: float = 0.0) -> bool:
    """Try to remove message.

    :param message: The message to be deleted.
    :param delay: How long to wait, in seconds.
    :return: ``True`` if the action was successful, ``False`` otherwise.
    """
    try:
        await message.delete(delay=delay)
    except discord.HTTPException:
        return False
    return True


async def remove_reaction(
    message: discord.Message, emoji, member: discord.Member
) -> bool:
    """Try to remove reaction.

    :param message: The message of the reaction.
    :param emoji: Emoji, Reaction, PartialEmoji or string.
    :param member: The author of the reaction.
    :return: ``True`` if the action was successful, ``False`` otherwise.
    """
    try:
        await message.remove_reaction(emoji, member)
    except discord.HTTPException:
        return False
    return True


async def send_dm(
    user: Union[discord.Member, discord.User],
    text: Optional[str] = None,
    *,
    embed: Optional[discord.Embed] = None,
) -> bool:
    if text is None and embed is None:
        raise ValueError("Could not send an empty message.")
    try:
        await user.send(text, embed=embed)
        return True
    except discord.HTTPException:
        return False
