from operator import attrgetter
from typing import Union

import discord
from discord import app_commands
from discord.ext import commands

import pie.acl
from pie import check, i18n, logger, utils
from pie.acl.database import (
    ACDefault,
    ACLevel,
    ACLevelMappping,
    ChannelOverwrite,
    RoleOverwrite,
    UserOverwrite,
)
from pie.bot import Strawberry

_ = i18n.Translator("modules/base").translate
bot_log = logger.Bot.logger()
guild_log = logger.Guild.logger()


class ACL(commands.Cog):
    """Access control module."""

    def __init__(self, bot: Strawberry):
        self.bot = bot

    #

    @commands.guild_only()
    @check.acl2(check.ACLevel.SUBMOD)
    @commands.group(name="acl")
    async def acl_(self, ctx: commands.Context):
        """Permission control."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_.group(name="mapping")
    async def acl_mapping_(self, ctx: commands.Context):
        """Manage mapping of ACL levels to roles."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_mapping_.command(name="list")
    async def acl_mapping_list(self, ctx: commands.Context):
        """Display ACL level to role mappings."""

        class Item:
            def __init__(self, mapping: ACLevelMappping):
                self.level = mapping.level.name
                role = ctx.guild.get_role(mapping.role_id)
                self.role = getattr(role, "name", str(mapping.role_id))

        mappings: list[ACLevelMappping] = ACLevelMappping.get_all(ctx.guild.id)

        if not mappings:
            await ctx.reply(_(ctx, "No mappings have been set."))
            return

        mappings = sorted(mappings, key=lambda m: m.level.name)[::-1]
        items = [Item(mapping) for mapping in mappings]

        table: list[str] = utils.text.create_table(
            items,
            header={
                "role": _(ctx, "Role"),
                "level": _(ctx, "Level"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_mapping_.command(name="add")
    async def acl_mapping_add(
        self, ctx: commands.Context, role: discord.Role, level: str
    ):
        """Add ACL level to role mappings."""
        try:
            level: ACLevel = ACLevel[level]
        except KeyError:
            await ctx.reply(
                _(ctx, "Invalid level. Possible options are: {keys}.").format(
                    keys=ACLevel.get_valid_levels()
                )
            )
            return
        if level in (ACLevel.BOT_OWNER, ACLevel.GUILD_OWNER):
            await ctx.reply(_(ctx, "You can't assign OWNER levels."))
            return
        if level >= pie.acl.map_member_to_ACLevel(bot=self.bot, member=ctx.author):
            await ctx.reply(
                _(ctx, "Your ACLevel has to be higher than **{level}**.").format(
                    level=level.name
                )
            )
            return

        mapping = ACLevelMappping.add(ctx.guild.id, role.id, level)
        if mapping is None:
            await ctx.reply(_(ctx, "That role is already mapped to some level."))
            return

        await ctx.reply(
            _(ctx, "Role **{role}** will be mapped to **{level}**.").format(
                role=role.name, level=level.name
            )
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"New ACLevel mapping for role '{role.name}' set to level '{level.name}'.",
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_mapping_.command(name="remove")
    async def acl_mapping_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove ACL level to role mapping."""
        mapping = ACLevelMappping.get(ctx.guild.id, role.id)
        if not mapping:
            await ctx.reply(_(ctx, "That role is not mapped to any level."))
            return

        if mapping.level >= pie.acl.map_member_to_ACLevel(
            bot=self.bot, member=ctx.author
        ):
            await ctx.reply(
                _(ctx, "Your ACLevel has to be higher than **{level}**.").format(
                    level=mapping.level.name
                )
            )
            return

        ACLevelMappping.remove(ctx.guild.id, role.id)

        await ctx.reply(_(ctx, "Role mapping was sucessfully removed."))
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"ACLevel mapping for role '{role.name}' removed.",
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_.group(name="default")
    async def acl_default_(self, ctx: commands.Context):
        """Manage default (hardcoded) command ACLevels."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_default_.command("list")
    async def acl_default_list(self, ctx: commands.Context):
        """List currently applied default overwrites."""

        class Item:
            def __init__(self, bot: Strawberry, default: ACDefault):
                self.command = default.command
                self.level = default.level.name
                level = pie.acl.get_hardcoded_ACLevel(bot, self.command)
                self.default: str = getattr(level, "name", "?")

        defaults = ACDefault.get_all(ctx.guild.id)

        if not defaults:
            await ctx.reply(_(ctx, "No defaults have been set."))
            return

        defaults = sorted(defaults, key=lambda d: d.command)[::-1]
        items = [Item(self.bot, default) for default in defaults]

        table: list[str] = utils.text.create_table(
            items,
            header={
                "command": _(ctx, "Command"),
                "default": _(ctx, "Default level"),
                "level": _(ctx, "Custom level"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_default_.command("add")
    async def acl_default_add(self, ctx: commands.Context, command: str, level: str):
        """Add custom ACLevel for a command.

        You can only constraint commands that you are currently able to invoke.
        """
        try:
            level: ACLevel = ACLevel[level]
            if level == ACLevel.UNKNOWN:
                raise KeyError()
        except KeyError:
            await ctx.reply(
                _(ctx, "Invalid level. Possible options are: {keys}.").format(
                    keys=ACLevel.get_valid_levels()
                )
            )
            return
        if command not in self.bot.get_all_commands():
            await ctx.reply(_(ctx, "I don't know this command."))
            return

        command_level = pie.acl.get_true_ACLevel(self.bot, ctx.guild.id, command)
        if command_level is None:
            await ctx.reply(_(ctx, "This command can't be controlled by ACL."))
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        if command_level > pie.acl.map_member_to_ACLevel(
            bot=self.bot, member=ctx.author
        ):
            await ctx.reply(
                _(ctx, "Command's ACLevel is higher than your current ACLevel.")
            )
            return

        # Add the overwrite

        default = ACDefault.add(ctx.guild.id, command, level)
        if default is None:
            await ctx.reply(
                _(ctx, "Custom default for **{command}** already exists.").format(
                    command=command
                )
            )
            return

        await ctx.reply(
            _(ctx, "Custom default for **{command}** set.").format(command=command)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"ACLevel default for '{command}' set to '{level.name}'.",
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_default_.command("remove")
    async def acl_default_remove(self, ctx: commands.Context, command: str):
        """Remove custom ACLevel for a command."""
        if command not in self.bot.get_all_commands():
            await ctx.reply(_(ctx, "I don't know this command."))
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        removed = ACDefault.remove(ctx.guild.id, command)
        if not removed:
            await ctx.reply(
                _(ctx, "Command **{command}** does not have custom default.").format(
                    command=command
                )
            )
            return

        await ctx.reply(
            _(ctx, "Custom default for **{command}** removed.").format(command=command)
        )
        await guild_log.info(
            ctx.author, ctx.channel, f"ACLevel for '{command}' set to default."
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_default_.command("audit")
    async def acl_default_audit(self, ctx: commands.Context, *, query: str = ""):
        """Display all bot commands and their defaults."""
        if len(query):
            bot_commands = [
                command
                for name, command in self.bot.get_all_commands()
                if query in name
            ]
        else:
            bot_commands = list(self.bot.get_all_commands().values())

        bot_commands = sorted(bot_commands, key=lambda c: c.qualified_name.lower())

        default_overwrites = {}
        for default_overwrite in ACDefault.get_all(ctx.guild.id):
            default_overwrites[default_overwrite.command] = default_overwrite.level

        class Item:
            def __init__(
                self,
                bot: Strawberry,
                command: Union[
                    commands.Command, app_commands.Command, app_commands.ContextMenu
                ],
            ):
                self.command = command.qualified_name
                level = pie.acl.get_hardcoded_ACLevel(bot, command.qualified_name)
                self.level: str = getattr(level, "name", "?")
                try:
                    self.db_level = default_overwrites[self.command].name
                except KeyError:
                    self.db_level = ""

        items = [Item(self.bot, command) for command in bot_commands]
        # put commands with overwrites first
        items = sorted(items, key=lambda item: item.db_level, reverse=True)

        # make items unique - e.g. hybrid commands
        seen = set()
        items = [
            item
            for item in items
            if item.command not in seen and not seen.add(item.command)
        ]

        table: list[str] = utils.text.create_table(
            items,
            header={
                "command": _(ctx, "Command"),
                "level": _(ctx, "Default level"),
                "db_level": _(ctx, "Custom level"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_.group(name="overwrite")
    async def acl_overwrite_(self, ctx: commands.Context):
        """Manage role, channel and user overwrites."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_.command(name="list")
    async def acl_overwrite_list(self, ctx: commands.Context):
        """Display all active overwrites."""
        ros = RoleOverwrite.get_all(ctx.guild.id)
        cos = ChannelOverwrite.get_all(ctx.guild.id)
        uos = UserOverwrite.get_all(ctx.guild.id)

        class Item:
            def __init__(
                self, overwrite: Union[RoleOverwrite, ChannelOverwrite, UserOverwrite]
            ):
                self.overwrite: str
                self.value: str

                if type(overwrite) is RoleOverwrite:
                    self.overwrite = _(ctx, "role")
                    role = ctx.guild.get_role(overwrite.role_id)
                    self.value = getattr(role, "name", str(overwrite.role_id))
                elif type(overwrite) is ChannelOverwrite:
                    self.overwrite = _(ctx, "channel")
                    channel = ctx.guild.get_channel(overwrite.channel_id)
                    self.value = "#" + getattr(
                        channel, "name", str(overwrite.channel_id)
                    )
                elif type(overwrite) is UserOverwrite:
                    self.overwrite = _(ctx, "user")
                    member = ctx.guild.get_member(overwrite.user_id)
                    if member:
                        self.value = member.display_name.replace("`", "'")
                    else:
                        self.value = str(overwrite.user_id)
                else:
                    self.overwrite = _(ctx, "unsupported")
                    self.value = f"{type(overwrite).__name__}"

                self.command = overwrite.command
                self.allow = _(ctx, "yes") if overwrite.allow else _(ctx, "no")

        items = (
            [Item(ro) for ro in ros]
            + [Item(co) for co in cos]
            + [Item(uo) for uo in uos]
        )

        if not items:
            await ctx.reply(_(ctx, "No ACL overwrites have been set."))
            return

        # sorting priority: type, command, value
        items = sorted(items, key=attrgetter("value", "command", "overwrite"))

        table: list[str] = utils.text.create_table(
            items,
            header={
                "overwrite": _(ctx, "Overwrite type"),
                "command": _(ctx, "Command"),
                "value": _(ctx, "Value"),
                "allow": _(ctx, "Allow"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_.group(name="role")
    async def acl_overwrite_role_(self, ctx: commands.Context):
        """Manage role ACL overwrites."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_role_.command(name="add")
    async def acl_overwrite_role_add(
        self, ctx: commands.Context, command: str, role: discord.Role, allow: bool
    ):
        """Add ACL role overwrite."""
        if command not in self.bot.get_all_commands():
            await ctx.reply(_(ctx, "I don't know this command."))
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        ro = RoleOverwrite.add(ctx.guild.id, role.id, command, allow)
        if ro is None:
            await ctx.reply(
                _(
                    ctx,
                    "Overwrite for command **{command}** and "
                    "role **{role}** already exists.",
                ).format(command=command, role=role.name)
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "role **{role}** sucessfully created.",
            ).format(command=command, role=role.name)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Role overwrite created for command '{command}' "
            f"and role '{role}': " + ("allow." if allow else "deny."),
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_role_.command(name="remove")
    async def acl_overwrite_role_remove(
        self, ctx: commands.Context, command: str, role: discord.Role
    ):
        """Remove ACL role overwrite."""
        removed = RoleOverwrite.remove(ctx.guild.id, role.id, command)
        if not removed:
            await ctx.reply(
                _(ctx, "Overwrite for this command and role does not exist.")
            )
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "role **{role}** sucessfully removed.",
            ).format(command=command, role=role.name)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Role overwrite removed for command '{command}' and role '{role}'.",
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_role_.command(name="list")
    async def acl_overwrite_role_list(self, ctx: commands.Context):
        """List ACL role overwrites."""
        ros = RoleOverwrite.get_all(ctx.guild.id)

        class Item:
            def __init__(self, ro: RoleOverwrite):
                role = ctx.guild.get_role(ro.role_id)
                self.role = getattr(role, "name", str(ro.role_id))
                self.command = ro.command
                self.allow = _(ctx, "yes") if ro.allow else _(ctx, "no")

        items = [Item(ro) for ro in ros]

        if not items:
            await ctx.reply(_(ctx, "No role overwrites have been set."))
            return

        # sorting priority: command, role
        items = sorted(items, key=attrgetter("role", "command"))

        table: list[str] = utils.text.create_table(
            items,
            header={
                "command": _(ctx, "Command"),
                "role": _(ctx, "Role"),
                "allow": _(ctx, "Allow"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_.group(name="user")
    async def acl_overwrite_user_(self, ctx: commands.Context):
        """Manage user ACL overwrites."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_user_.command(name="add")
    async def acl_overwrite_user_add(
        self, ctx: commands.Context, command: str, user: discord.Member, allow: bool
    ):
        """Add ACL user overwrite."""
        if command not in self.bot.get_all_commands():
            await ctx.reply(_(ctx, "I don't know this command."))
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        uo = UserOverwrite.add(ctx.guild.id, user.id, command, allow)
        if uo is None:
            await ctx.reply(
                _(
                    ctx,
                    "Overwrite for command **{command}** and "
                    "user **{user}** already exists.",
                ).format(command=command, user=utils.text.sanitise(user.display_name))
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "user **{user}** sucessfully created.",
            ).format(command=command, user=utils.text.sanitise(user.display_name))
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"User overwrite created for command '{command}' "
            f"and user '{user.name}': " + ("allow." if allow else "deny."),
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_user_.command(name="remove")
    async def acl_overwrite_user_remove(
        self, ctx: commands.Context, command: str, user: discord.Member
    ):
        """Remove ACL user overwrite."""
        removed = UserOverwrite.remove(ctx.guild.id, user.id, command)
        if not removed:
            await ctx.reply(
                _(ctx, "Overwrite for this command and user does not exist.")
            )
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "user **{user}** sucessfully removed.",
            ).format(command=command, user=utils.text.sanitise(user.display_name))
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"User overwrite removed for command '{command}' and user '{user.name}'.",
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_user_.command(name="list")
    async def acl_overwrite_user_list(self, ctx: commands.Context):
        """List ACL role overwrites."""
        uos = UserOverwrite.get_all(ctx.guild.id)

        class Item:
            def __init__(self, uo: UserOverwrite):
                self.user: str
                member = ctx.guild.get_member(uo.user_id)
                if member:
                    self.user = member.display_name.replace("`", "'")
                else:
                    self.user = str(uo.user_id)

                self.command = uo.command
                self.allow = _(ctx, "yes") if uo.allow else _(ctx, "no")

        items = [Item(uo) for uo in uos]

        if not items:
            await ctx.reply(_(ctx, "No user overwrites have been set."))
            return

        # sorting priority: command, user
        items = sorted(items, key=attrgetter("user", "command"))

        table: list[str] = utils.text.create_table(
            items,
            header={
                "command": _(ctx, "Command"),
                "user": _(ctx, "User"),
                "allow": _(ctx, "Allow"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_.group(name="channel")
    async def acl_overwrite_channel_(self, ctx: commands.Context):
        """Manage channel ACL overwrites."""
        await utils.discord.send_help(ctx)

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_channel_.command(name="add")
    async def acl_overwrite_channel_add(
        self,
        ctx: commands.Context,
        command: str,
        channel: discord.TextChannel,
        allow: bool,
    ):
        """Add ACL channel overwrite."""
        if command not in self.bot.get_all_commands():
            await ctx.reply(_(ctx, "I don't know this command."))
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        co = ChannelOverwrite.add(ctx.guild.id, channel.id, command, allow)
        if co is None:
            await ctx.reply(
                _(
                    ctx,
                    "Overwrite for command **{command}** and "
                    "channel **#{channel}** already exists.",
                ).format(command=command, channel=channel.name)
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "channel **#{channel}** sucessfully created.",
            ).format(command=command, channel=channel.name)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Overwrite created for command '{command}' "
            f"and channel '#{channel.name}': " + ("allow." if allow else "deny."),
        )

    @check.acl2(check.ACLevel.GUILD_OWNER)
    @acl_overwrite_channel_.command(name="remove")
    async def acl_overwrite_channel_remove(
        self, ctx: commands.Context, command: str, channel: discord.TextChannel
    ):
        """Remove ACL channel overwrite."""
        removed = ChannelOverwrite.remove(ctx.guild.id, channel.id, command)
        if not removed:
            await ctx.reply(
                _(ctx, "Overwrite for this command and channel does not exist.")
            )
            return

        if not pie.acl.can_invoke_command(self.bot, ctx, command):
            await ctx.reply(
                _(
                    ctx,
                    "You don't have permission to run this command, "
                    "you can't alter its permissions.",
                )
            )
            return

        await ctx.reply(
            _(
                ctx,
                "Overwrite for command **{command}** and "
                "channel **#{channel}** sucessfully removed.",
            ).format(command=command, channel=channel.name)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Overwrite removed for command '{command}' and channel '{channel.name}'.",
        )

    @check.acl2(check.ACLevel.SUBMOD)
    @acl_overwrite_channel_.command(name="list")
    async def acl_overwrite_channel_list(self, ctx: commands.Context):
        """List ACL channel overwrites."""
        cos = ChannelOverwrite.get_all(ctx.guild.id)

        class Item:
            def __init__(self, co: ChannelOverwrite):
                channel = ctx.guild.get_channel(co.channel_id)
                self.channel = "#" + getattr(channel, "name", str(co.channel_id))
                self.command = co.command
                self.allow = _(ctx, "yes") if co.allow else _(ctx, "no")

        items = [Item(co) for co in cos]

        if not items:
            await ctx.reply(_(ctx, "No channel overwrites have been set."))
            return

        # sorting priority: command, channel
        items = sorted(items, key=attrgetter("channel", "command"))

        table: list[str] = utils.text.create_table(
            items,
            header={
                "command": _(ctx, "Command"),
                "channel": _(ctx, "Channel"),
                "allow": _(ctx, "Allow"),
            },
        )

        for page in table:
            await ctx.send("```" + page + "```")


async def setup(bot: Strawberry) -> None:
    await bot.add_cog(ACL(bot))
