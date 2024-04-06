from __future__ import annotations

import argparse
import contextlib
from abc import ABCMeta, abstractmethod
from typing import Iterable, Optional, Union

import discord
from discord.ext import commands

from pie import i18n

_ = i18n.Translator("pie").translate


class ScrollableEmbed(discord.ui.View):
    """Button-controllable scrolling embed.

    :param ctx: Command context for translation purposes.
    :param iterable: List of embeds to show.
    :param timeout:
        How long to wait after last interaction to disable scrolling,
        in seconds.
    :param delete_message:
        Whether to remove full message after timeout,
        or just remove the buttons.
    :param as_reply: Whether to send the message as reply.
    """

    def __init__(
        self,
        ctx: commands.Context,
        iterable: Iterable[discord.Embed],
        timeout: int = 300,
        delete_message: bool = False,
        locked: bool = False,
        as_reply: bool = True,
    ) -> ScrollableEmbed:
        super().__init__(timeout=timeout)
        self.pages: Iterable[discord.Embed] = self._pages_from_iter(ctx, iterable)
        self.ctx: commands.Context = ctx
        self.pagenum: int = 0
        self.delete_message: bool = delete_message
        self.locked: bool = locked
        self.as_reply: bool = as_reply

        self.add_item(
            discord.ui.Button(
                label="\u25c1",
                style=discord.ButtonStyle.green,
                custom_id="left-button",
            )
        )

        if self.locked:
            self.lock_button = discord.ui.Button(
                label="🔒",
                style=discord.ButtonStyle.red,
                custom_id="lock-button",
            )
        else:
            self.lock_button = discord.ui.Button(
                label="🔓",
                style=discord.ButtonStyle.green,
                custom_id="lock-button",
            )
        self.add_item(self.lock_button)

        self.add_item(
            discord.ui.Button(
                label="\u25b7",
                style=discord.ButtonStyle.green,
                custom_id="right-button",
            )
        )

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"page_count='{len(self.pages)}' pages='[{self.pages}]'>"
        )

    def _pages_from_iter(
        self, ctx: commands.Context, iterable: Iterable[discord.Embed]
    ) -> list[discord.Embed]:
        pages = []
        for idx, embed in enumerate(iterable):
            if not isinstance(embed, discord.Embed):
                raise ValueError("Items in iterable must be of type discord.Embed")
            embed.add_field(
                name=_(ctx, "Page"),
                value="{curr}/{total}".format(curr=idx + 1, total=len(iterable)),
                inline=False,
            )
            pages.append(embed)
        return pages

    def _toggle_lock(self) -> None:
        if self.locked:
            self.locked = False
            self.lock_button.label = "🔓"
            self.lock_button.style = discord.ButtonStyle.green
        else:
            self.locked = True
            self.lock_button.label = "🔒"
            self.lock_button.style = discord.ButtonStyle.red

    def __get_gtx(
        self,
        interaction: discord.Interaction,
    ) -> i18n.TranslationContext:
        if self.ctx.guild is not None:
            gtx = i18n.TranslationContext(self.ctx.guild.id, interaction.user.id)
        else:
            # TranslationContext does not know how to use user without guild,
            # this will result in bot preference being used.
            gtx = i18n.TranslationContext(None, interaction.user.id)
        return gtx

    async def scroll(self):
        """Make embeds move.

        Sends the first page to the context.
        """
        ctx = self.ctx
        if self.pages == []:
            self.clear_items()
            await ctx.reply(_(ctx, "No results were found."))
            self.stop()
            return

        if len(self.pages) == 1:
            self.clear_items()
            await ctx.send(embed=self.pages[0])
            self.stop()
            return

        send = ctx.reply if self.as_reply else ctx.send
        self.message = await send(embed=self.pages[0], view=self, mention_author=False)

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        if interaction.data["custom_id"] not in [
            "lock-button",
            "left-button",
            "right-button",
        ]:
            # In case of unknown interaction (eg: decorated functions in child class)
            await super().interaction_check(interaction)
            return
        if interaction.data["custom_id"] == "lock-button":
            if interaction.user.id is self.ctx.author.id:
                self._toggle_lock()
                await interaction.response.edit_message(view=self)
                return
            else:
                gtx = self.__get_gtx(interaction)
                await interaction.response.send_message(
                    _(gtx, "Only command issuer can toggle the lock."), ephemeral=True
                )
                return
        elif interaction.user.id != self.ctx.author.id and self.locked:
            gtx = self.__get_gtx(interaction)
            await interaction.response.send_message(
                _(gtx, "Only command issuer can scroll."), ephemeral=True
            )
            return

        if interaction.data["custom_id"] == "left-button":
            self.pagenum -= 1
        else:
            self.pagenum += 1

        if self.pagenum < 0:
            self.pagenum = len(self.pages) - 1

        if self.pagenum >= len(self.pages):
            self.pagenum = 0

        await interaction.response.edit_message(embed=self.pages[self.pagenum])

    async def on_timeout(self) -> None:
        """Gets called when the view timeouts."""
        if not self.delete_message:
            self.clear_items()
            await self.message.edit(embed=self.pages[self.pagenum], view=None)
        else:
            with contextlib.suppress(Exception):
                await self.message.delete()


class ConfirmView(discord.ui.View):
    """Class for making confirmation embeds easy.
    The right way of getting response is first calling wait() on instance,
    then checking instance attribute `value`.

    Attributes:
        value: True if confirmed, False if declined, None if timed out
        ctx: Context of command
        message: Confirmation message

    Args:
        utx: The context for translational and sending purposes.
        embed: Embed to send.
        timeout: Number of seconds before timeout. `None` if no timeout
        delete: Delete message after answering / timeout


    To use import this object and create new instance:
    .. code-block:: python
        :linenos:

        from pie.utils.objects import ConfirmView

        ...

        embed = utils.discord.create_embed(
            author=reminder_user,
            title=Confirm your action.",
        )
        view = ConfirmView(ctx, embed)

        value = await view.send()

        if value is None:
            await ctx.send(_(ctx, "Confirmation timed out."))
        elif value:
            await ctx.send(_(ctx, "Confirmed."))
        else:
            await ctx.send(_(ctx, "Aborted."))
    """

    def __init__(
        self,
        utx: Union[commands.Context, discord.Interaction],
        embed: discord.Embed,
        timeout: Union[int, float, None] = 300,
        delete: bool = True,
        ephemeral: bool = True,
    ):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.utx = utx
        self.embed = embed
        self.delete = delete
        self.ephemeral = ephemeral
        self.itx = None

    async def send(self):
        """Sends message to channel defined by command context.
        Returns:
            True if confirmed, False if declined, None if timed out
        """
        self.add_item(
            discord.ui.Button(
                label=_(self.utx, "Confirm"),
                style=discord.ButtonStyle.green,
                custom_id="confirm-button",
            )
        )
        self.add_item(
            discord.ui.Button(
                label=_(self.utx, "Reject"),
                style=discord.ButtonStyle.red,
                custom_id="reject-button",
            )
        )

        # Interactions have different limitations
        if isinstance(self.utx, discord.Interaction):
            await self.utx.response.send_message(
                embed=self.embed, view=self, ephemeral=self.ephemeral
            )
            await self.wait()

            try:
                self.message = await self.utx.original_response()
            except Exception:
                pass

            try:
                if self.message and not self.delete:
                    self.clear_items()
                    await self.message.edit(embed=self.embed)
                elif self.message and self.delete:
                    await self.message.delete()
            except Exception:
                # There's nothing much to do with the exceptions
                # We either don't have permissions or the message does not exist.
                pass

            return self.value

        # Keep the original functionality for ctx
        self.message = await self.utx.reply(embed=self.embed, view=self)
        await self.wait()

        if not self.delete:
            self.clear_items()
            await self.message.edit(embed=self.embed, view=None)
        else:
            with contextlib.suppress(Exception):
                await self.message.delete()
        return self.value

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        author_id: int = (
            self.utx.user.id
            if isinstance(self.utx, discord.Interaction)
            else self.ctx.author.id
        )

        if interaction.user.id != author_id:
            await interaction.response.send_message(
                _(self.utx, "Only the author can confirm the action."), ephemeral=True
            )
            return

        if interaction.data["custom_id"] == "confirm-button":
            self.value = True
        else:
            self.value = False

        # Save interaction for future use
        self.itx = interaction

        self.stop()

    async def on_timeout(self) -> None:
        """Gets called when the view timeouts."""
        self.value = None
        self.stop()


class VotableEmbed(discord.Embed, metaclass=ABCMeta):
    """
    Abrstract class extendindg Embed functionality
    so it can be used in ScollableVotingEmbed.

    Functions `vote_up`, `vote_neutral` and `vote_down`
    must be overriden. Init takes same arguments,
    as :class:`discord.Embed`.

    Example of usage can be found in School.Review module.
    """

    def __init__(self, *args, **kwargs):
        super(VotableEmbed, self).__init__(*args, **kwargs)

    @abstractmethod
    async def vote_up(interaction: discord.Interaction):
        """
        Callback when user votes UP. Must be overriden.
        """
        pass

    @abstractmethod
    async def vote_neutral(interaction: discord.Interaction):
        """
        Callback when user votes NEUTRAL. Must be overriden.
        """
        pass

    @abstractmethod
    async def vote_down(interaction: discord.Interaction):
        """
        Callback when user votes DOWNs. Must be overriden.
        """
        pass


class ScrollableVotingEmbed(ScrollableEmbed):
    """Class for making scrollable embeds with voting easy.

    Args:
        ctx (:class:`discord.ext.commands.Context`): The context for translational purposes.
        iterable (:class:`Iterable[VotableEmbed]`): Iterable which to build the ScrollableVotingEmbed from.
        timeout (:class:'int'): Timeout (in seconds, default 300) from last interaction with the UI before no longer accepting input. If None then there is no timeout.
        delete_message (:class:'bool'): True - remove message after timeout. False - remove only View controls.
        locked: (:class:'bool'): True if only author can scroll, False otherwise
    """

    def __init__(self, *args, **kwagrs) -> ScrollableVotingEmbed:
        super().__init__(*args, **kwagrs)

        if len(self.pages) == 1:
            self.clear_items()

        self.add_item(
            discord.ui.Button(
                label="👍",
                style=discord.ButtonStyle.green,
                custom_id="vote_up",
                row=1,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="🤷‍",
                style=discord.ButtonStyle.gray,
                custom_id="vote_neutral",
                row=1,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="👎",
                style=discord.ButtonStyle.red,
                custom_id="vote_down",
                row=1,
            )
        )

    async def scroll(self):
        """Make embeds move. Overrides original function which
        was stopping View when there were only 1 page.

        Sends the first page to the context.
        """
        ctx = self.ctx
        if self.pages == []:
            self.clear_items()
            await ctx.reply(_(ctx, "No results were found."))
            self.stop()
            return

        send = ctx.reply if self.as_reply else ctx.send
        self.message = await send(embed=self.pages[0], view=self, mention_author=False)

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """
        Gets called when interaction with any of the Views buttons happens.
        If custom ID is not recognized, it's passed to parent.
        """
        if interaction.data["custom_id"] == "vote_up":
            await self.pages[self.pagenum].vote_up(interaction)
        elif interaction.data["custom_id"] == "vote_neutral":
            await self.pages[self.pagenum].vote_neutral(interaction)
        elif interaction.data["custom_id"] == "vote_down":
            await self.pages[self.pagenum].vote_down(interaction)
        else:
            await super().interaction_check(interaction)


class VoteEmbed(discord.ui.View):
    """Class for making voting embeds easy.
    The right way of getting response is first calling send() on instance,
    then checking instance attribute `value`.

    Attributes:
        value: True if confirmed, False if declined, None if timed out
        ctx: Context of command
        message: Vote message

    Args:
        ctx: The context for translational and sending purposes.
        embed: Embed to send.
        limit: Minimal votes.
        timeout: Number of seconds before timeout. `None` if no timeout
        delete: Delete message after answering / timeout
        vote_author: Auto vote for author


    To use import this object and create new instance:
    .. code-block:: python
        :linenos:

        from pie.utils.objects import VoteEmbed

        ...

        embed = utils.discord.create_embed(
            author=reminder_user,
            title=Vote for your action.",
        )
        view = VoteEmbed(ctx, embed)

        value = await view.send()

        if value is None:
            await ctx.send(_(ctx, "Voted timed out."))
        elif value:
            await ctx.send(_(ctx, "Vote passed."))
    """

    def __init__(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        limit: int,
        timeout: Union[int, float, None] = 300,
        delete: bool = True,
        vote_author: bool = False,
    ):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.ctx = ctx
        self.embed = embed
        self.limit = limit
        self.voted = []
        self.delete = delete

        if vote_author:
            self.voted.append(ctx.author.id)

    async def send(self):
        """Sends message to channel defined by command context.
        Returns:
            True if confirmed in time, None if timed out
        """

        self.button = discord.ui.Button(
            label=_(self.ctx, "Yes") + " ({})".format(len(self.voted)),
            style=discord.ButtonStyle.green,
            custom_id="yes-button",
        )

        self.add_item(self.button)

        self.message = await self.ctx.send(embed=self.embed, view=self)
        await self.wait()

        if not self.delete:
            self.clear_items()
            await self.message.edit(embed=self.embed, view=self)
        else:
            with contextlib.suppress(Exception):
                await self.message.delete()
        return self.value

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        if interaction.user.id in self.voted:
            await interaction.response.send_message(
                _(self.ctx, "You have already voted!"), ephemeral=True
            )
            return

        self.voted.append(interaction.user.id)

        if len(self.voted) >= self.limit:
            self.value = True
            self.stop()
            return

        await interaction.response.send_message(
            _(self.ctx, "Your vote has been casted."), ephemeral=True
        )

        self.button.label = _(self.ctx, "Yes") + " ({})".format(len(self.voted))

        await self.message.edit(embed=self.embed, view=self)

    async def on_timeout(self) -> None:
        """Gets called when the view timeouts."""
        self.value = None
        self.stop()


class CommandParser(argparse.ArgumentParser):
    """Patch ArgumentParser.

    ArgumentParser calls sys.exit(2) on incorrect command,
    which would take down the bot. This subclass catches the errors
    and saves them in 'error_message' attribute.
    """

    error_message: Optional[str] = None

    def error(self, message: str):
        """Save the error message."""
        self.error_message = message

    def exit(self):
        """Make sure the program _does not_ exit."""
        pass

    def parse_args(self, args: Iterable):
        """Catch exceptions that do not occur when CLI program exits."""
        returned = self.parse_known_args(args)
        try:
            args, argv = returned
        except TypeError:
            # There was an error and it is saved in 'error_message'
            return None
        return args
