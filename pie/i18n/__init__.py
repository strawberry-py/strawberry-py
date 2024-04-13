from pathlib import Path
from typing import Dict, Optional, Union

import ring

import discord

from pie.database.config import Config
from pie.i18n.database import GuildLanguage, MemberLanguage

LANGUAGES = ("cs", "sk")


class TranslationContext:
    """Fake class used for translation.

    There are some situations where there is no command context, e.g. when a
    reaction is added, especially when it is
    :class:`discord.RawReactionActionEvent`. This may be used to get around.

    See :class:`Translator` for more details.
    """

    __slots__ = ("guild_id", "user_id")

    def __init__(self, guild_id: Optional[int], user_id: Optional[int]):
        self.guild_id = guild_id
        self.user_id = user_id

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"guild_id='{self.guild_id}' user_id='{self.user_id}'>"
        )


class Translator:
    """Class for getting translations from PoPie text files.

    .. code-block:: python
        :linenos:

        from pie import i18n

        _ = i18n.Translator("modules/base").translate
    """

    def __init__(self, dirname: str):
        self._dir = Path(dirname)

        self.strings: Dict[str, Dict[str, Optional[str]]] = {}
        for language in LANGUAGES:
            pofile: Path = self._dir / "po" / f"{language}.popie"
            if not pofile.exists():
                continue
            self.strings[language] = self.parse_po_file(pofile)

    def parse_po_file(self, pofile: Path) -> Dict[str, str]:
        """Get translation dictionary from .po file."""
        data: Dict[str, str] = {}
        with open(pofile, "r") as handle:
            for line in handle.readlines():
                line = line.strip()

                if line.startswith("msgid"):
                    msgid: str = line[len("msgid") :].strip()
                if line.startswith("msgstr"):
                    msgstr: str = line[len("msgstr") :].strip()
                    if len(msgstr):
                        data[msgid] = msgstr
        return data

    def __repr__(self) -> str:
        """Return representation of the class."""
        languages: str = ", ".join(self.strings.keys())
        return f"<Translator _dir='{self._dir!s}' languages='{languages}'>"

    def __str__(self) -> str:
        """Return human-friendly representation of the class."""
        return self.__repr__()

    def translate(
        self,
        utx: Union[
            discord.ext.commands.Context, TranslationContext, discord.Interaction
        ],
        string: str,
    ) -> str:
        """Get translation for requested key.

        :param utx: Translation context or interaction. Used to determine preferred language.
        :param string: String to be translated.
        :return: Translated string.

        If the string is not found, the input is returned.

        .. code-block:: python
            :linenos:

            # Standard commands
            await ctx.reply(_(ctx, "You are {name}".format(user=ctx.author.name)))

            # Slash commands / interactionsy
            await itx.response.send_message(_(itx, "You are {name}".format(user=itx.user.name)))
        """
        # get language preference
        langcode: str = self.get_language_preference(utx)

        if langcode not in self.strings.keys():
            return string
        if string not in self.strings[langcode].keys():
            return string
        return self.strings[langcode][string]

    def get_language_preference(
        self,
        utx: Union[
            discord.ext.commands.Context, discord.Interaction, TranslationContext
        ],
    ) -> str:
        """Get language for the string.

        Preference hierarchy:

        * Try to get user information: if they have language preference, return it.
        * Try to get guild information: if it has language preference, return it.
        * Return the bot default.
        """
        # Default value = None
        guild_id: Optional[int] = None
        user_id: Optional[int] = None

        # Fake class for translation
        if isinstance(utx, TranslationContext):
            guild_id, user_id = utx.guild_id, utx.user_id
        # Private chat (DMs)
        elif isinstance(utx.channel, discord.abc.PrivateChannel):
            # Interaction vs Context - different user variable
            if isinstance(utx, discord.Interaction):
                guild_id, user_id = None, utx.user.id
            else:
                guild_id, user_id = None, utx.author.id
        # Servers
        elif not isinstance(utx.channel, discord.abc.PrivateChannel):
            # Interaction vs Context - different user variable
            if isinstance(utx, discord.Interaction):
                guild_id, user_id = utx.guild.id, utx.user.id
            else:
                guild_id, user_id = utx.guild.id, utx.author.id

        if guild_id is not None and user_id is not None:
            user_language: Optional[str] = self._get_user_language(guild_id, user_id)
            if user_language is not None:
                return user_language

        if guild_id is not None:
            guild_language: Optional[str] = self._get_guild_language(guild_id)
            if guild_language is not None:
                return guild_language

        return Config.get().language

    # While we could be using just functools.lru_cache(), using ring
    # is a better option, because it allows us to add automatic deletion
    # into the mix. Because the member can change their preferred language
    # dynamically, invalidation is a preferred behavior.
    # In case this expiration value gets changed you should also change
    # the text in the language module under '[caching]' section.
    @ring.lru(expire=120)
    def _get_user_language(self, guild_id: int, user_id: int) -> Optional[str]:
        """Get user's language preference.

        This value may be out-of-sync for two minues after change because of
        caching.
        """
        user = MemberLanguage.get(guild_id, user_id)
        if getattr(user, "language", None) is not None:
            return user.language

    @ring.lru(expire=120)
    def _get_guild_language(self, guild_id: int) -> Optional[str]:
        """Get guild's language preference.

        This value may be out-of-sync for two minues after change because of
        caching.
        """
        guild = GuildLanguage.get(guild_id)
        if getattr(guild, "language", None) is not None:
            return guild.language
