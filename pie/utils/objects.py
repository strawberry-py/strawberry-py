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
        utx: commands.Context | discord.Interaction,
        iterable: Iterable[discord.Embed],
        timeout: int = 300,
        delete_message: bool = False,
        locked: bool = False,
        as_reply: bool = True,
        ephemeral: bool = True,
    ) -> ScrollableEmbed:
        super().__init__(timeout=timeout)
        self.pages: Iterable[discord.Embed] = self._pages_from_iter(utx, iterable)
        self.utx: commands.Context = utx
        self.pagenum: int = 0
        self.delete_message: bool = delete_message
        self.locked: bool = locked
        self.as_reply: bool = as_reply
        self.ephemeral: bool = ephemeral

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
        self,
        utx: commands.Context | discord.Interaction,
        iterable: Iterable[discord.Embed],
    ) -> list[discord.Embed]:
        pages = []
        for idx, embed in enumerate(iterable):
            if not isinstance(embed, discord.Embed):
                raise ValueError("Items in iterable must be of type discord.Embed")
            embed.add_field(
                name=_(utx, "Page"),
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

    async def scroll(self, stop: bool = True):
        """Make embeds move.

        Sends the first page to the context.
        """
        utx: discord.Interaction | commands.Context = self.utx
        if self.pages == []:
            self.clear_items()
            if isinstance(utx, commands.Context):
                await utx.reply(_(utx, "No results were found."))
            else:
                self.message = await self._respond(
                    itx=utx,
                    message=_(utx, "No results were found."),
                    ephemeral=self.ephemeral,
                )
            if stop:
                self.stop()
            return

        if len(self.pages) == 1:
            self.clear_items()
            if isinstance(utx, commands.Context):
                await utx.reply(embed=self.pages[0])
            else:
                await self._respond(
                    itx=utx, embed=self.pages[0], ephemeral=self.ephemeral
                )
            self.stop()
            return

        if isinstance(utx, commands.Context):
            send = utx.reply if self.as_reply else utx.send
            self.message = await send(
                embed=self.pages[0], view=self, mention_author=False
            )
        else:
            self.message = await self._respond(
                itx=utx, embed=self.pages[0], view=self, ephemeral=self.ephemeral
            )

    async def _respond(
        self,
        itx: discord.Interaction,
        message: str = discord.interactions.MISSING,
        embed: discord.Embed = discord.interactions.MISSING,
        view: ScrollableEmbed = discord.interactions.MISSING,
        ephemeral: bool = True,
    ) -> discord.Message:
        if itx.response.is_done():
            if message:
                return await itx.edit_original_response(content=message)
            elif embed:
                return await itx.edit_original_response(embed=embed, view=view)
        else:
            if message:
                await itx.response.send_message(content=message, ephemeral=ephemeral)
            elif embed:
                return await itx.response.send_message(
                    embed=embed, view=view, ephemeral=ephemeral
                )
            return await itx.original_response()

    async def interaction_check(self, itx: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        if itx.data["custom_id"] not in [
            "lock-button",
            "left-button",
            "right-button",
        ]:
            # In case of unknown interaction (eg: decorated functions in child class)
            await super().interaction_check(itx)
            return

        author_id: int = (
            self.utx.user.id
            if isinstance(self.utx, discord.Interaction)
            else self.utx.author.id
        )

        if itx.data["custom_id"] == "lock-button":
            if itx.user.id is author_id:
                self._toggle_lock()
                await itx.response.edit_message(view=self)
                return
            else:
                await itx.response.send_message(
                    _(itx, "Only command issuer can toggle the lock."), ephemeral=True
                )
                return
        elif itx.user.id != author_id and self.locked:
            await itx.response.send_message(
                _(itx, "Only command issuer can scroll."), ephemeral=True
            )
            return

        if itx.data["custom_id"] == "left-button":
            self.pagenum -= 1
        else:
            self.pagenum += 1

        if self.pagenum < 0:
            self.pagenum = len(self.pages) - 1

        if self.pagenum >= len(self.pages):
            self.pagenum = 0

        await itx.response.edit_message(embed=self.pages[self.pagenum])

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
            except Exception:  # nosec
                pass

            try:
                if self.message and not self.delete:
                    self.clear_items()
                    await self.message.edit(embed=self.embed)
                elif self.message and self.delete:
                    await self.message.delete()
            except Exception:  # nosec
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

    async def on_confirm(self, itx: discord.Interaction):
        """Gets called on confirmation."""
        pass

    async def on_reject(self, itx: discord.Interaction):
        """Gets called on confirmation."""
        pass

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        author_id: int = (
            self.utx.user.id
            if isinstance(self.utx, discord.Interaction)
            else self.utx.author.id
        )

        if interaction.user.id != author_id:
            await interaction.response.send_message(
                _(self.utx, "Only the author can confirm the action."), ephemeral=True
            )
            return

        self.stop()

        if interaction.data["custom_id"] == "confirm-button":
            self.value = True
            await self.on_confirm(interaction)
        else:
            self.value = False
            await self.on_reject(interaction)

        # Save interaction for future use
        self.itx = interaction

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
    async def vote_up(itx: discord.Interaction):
        """
        Callback when user votes UP. Must be overriden.
        """
        pass

    @abstractmethod
    async def vote_neutral(itx: discord.Interaction):
        """
        Callback when user votes NEUTRAL. Must be overriden.
        """
        pass

    @abstractmethod
    async def vote_down(itx: discord.Interaction):
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
        return await super().scroll(False)

    async def interaction_check(self, itx: discord.Interaction) -> None:
        """
        Gets called when interaction with any of the Views buttons happens.
        If custom ID is not recognized, it's passed to parent.
        """
        if itx.data["custom_id"] == "vote_up":
            await self.pages[self.pagenum].vote_up(itx)
        elif itx.data["custom_id"] == "vote_neutral":
            await self.pages[self.pagenum].vote_neutral(itx)
        elif itx.data["custom_id"] == "vote_down":
            await self.pages[self.pagenum].vote_down(itx)
        else:
            await super().interaction_check(itx)


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
        utx: commands.Context | discord.Interaction,
        embed: discord.Embed,
        limit: int,
        timeout: Union[int, float, None] = 300,
        delete: bool = True,
        vote_author: bool = False,
        ephemeral: bool = True,
    ):
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.utx = utx
        self.embed = embed
        self.limit = limit
        self.voted = []
        self.delete = delete
        self.ephemeral = ephemeral

        if vote_author:
            author_id: int = (
                self.utx.user.id
                if isinstance(self.utx, discord.Interaction)
                else self.utx.author.id
            )
            self.voted.append(author_id)

    async def send(self):
        """Sends message to channel defined by command context.
        Returns:
            True if confirmed in time, None if timed out
        """

        self.button = discord.ui.Button(
            label=_(self.utx, "Yes") + " ({})".format(len(self.voted)),
            style=discord.ButtonStyle.green,
            custom_id="yes-button",
        )

        self.add_item(self.button)

        if isinstance(self.utx, commands.Context):
            self.message = await self.utx.send(embed=self.embed, view=self)
        else:
            if self.utx.response.is_done():
                self.message = await self.utx.edit_original_response(
                    embed=self.embed, view=self
                )
            else:
                self.message = await self.utx.response.send_message(
                    embed=self.embed, view=self.view, ephemeral=self.ephemeral
                )
        await self.wait()

        if not self.delete:
            self.clear_items()
            await self.message.edit(embed=self.embed, view=self)
        else:
            with contextlib.suppress(Exception):
                await self.message.delete()
        return self.value

    async def interaction_check(self, itx: discord.Interaction) -> None:
        """Gets called when interaction with any of the Views buttons happens."""
        if itx.user.id in self.voted:
            await itx.response.send_message(
                _(itx, "You have already voted!"), ephemeral=True
            )
            return

        self.voted.append(itx.user.id)

        if len(self.voted) >= self.limit:
            self.value = True
            self.stop()
            return

        await itx.response.send_message(
            _(itx, "Your vote has been casted."), ephemeral=True
        )

        self.button.label = _(itx, "Yes") + " ({})".format(len(self.voted))

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
