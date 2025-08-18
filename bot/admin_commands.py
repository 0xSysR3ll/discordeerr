import asyncio
import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.commands import SeerrCommands
from config import Config
from database.database import Database
from seerr.api import SeerrAPI

logger = logging.getLogger(__name__)


def is_admin():
    """Check if user is a Seerr admin"""

    async def predicate(interaction: discord.Interaction):
        admin_cog = None
        for _cog_name, cog in interaction.client.cogs.items():
            if isinstance(cog, AdminCommands):
                admin_cog = cog
                break

        if not admin_cog:
            await interaction.response.send_message("Admin system not available.", ephemeral=True)
            return False

        is_admin = admin_cog.database.is_user_admin(str(interaction.user.id))

        if not is_admin:
            await interaction.response.send_message(
                "You need to be a Seerr admin to use admin commands. Contact a server administrator.",
                ephemeral=True,
            )
        return is_admin

    return app_commands.check(predicate)


class AdminCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, seerr_api: SeerrAPI):
        self.bot = bot
        self.database = database
        self.seerr_api = seerr_api

    @app_commands.command(
        name="health",
        description="Check bot health and configuration",
    )
    @is_admin()
    async def health(self, interaction: discord.Interaction):
        """Check bot status and configuration"""
        try:
            embed = discord.Embed(
                title="Bot Status",
                description="Current bot configuration and status",
                color=discord.Color.blue(),
            )

            seerr_status = "Connected" if self.seerr_api.test_connection() else "Disconnected"
            embed.add_field(name="Seerr API", value=seerr_status, inline=True)

            try:
                self.database.get_admin_setting("test")
                db_status = "Connected"
            except Exception:
                db_status = "Error"

            embed.add_field(name="Database", value=db_status, inline=True)

            embed.add_field(
                name="Bot Latency",
                value=f"{round(self.bot.latency * 1000)}ms",
                inline=True,
            )

            if Config.NOTIFICATION_CHANNEL_ID:
                channel = self.bot.get_channel(Config.NOTIFICATION_CHANNEL_ID)
                if channel:
                    channel_status = f"<#{Config.NOTIFICATION_CHANNEL_ID}>"
                else:
                    channel_status = "Channel not found"
            else:
                channel_status = "Not configured"

            embed.add_field(name="Notification Channel", value=channel_status, inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in health command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while checking bot health.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="users", description="List all linked users and their Seerr accounts"
    )
    @is_admin()
    async def admin_users(self, interaction: discord.Interaction):
        """List all linked users"""
        try:
            with self.database.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT ja.*, u.username as discord_username
                    FROM seerr_accounts ja
                    JOIN users u ON ja.discord_id = u.discord_id
                    WHERE ja.discord_id IS NOT NULL
                    ORDER BY ja.linked_at DESC
                """
                )
                users = cursor.fetchall()

            if not users:
                embed = discord.Embed(
                    title="No Linked Users",
                    description="No users have linked their accounts yet.",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="Linked Users",
                description=f"**{len(users)}** user(s) linked to Seerr",
                color=discord.Color.blue(),
            )

            for _i, user in enumerate(users[:10]):
                linked_time = datetime.datetime.fromisoformat(
                    user["linked_at"].replace("Z", "+00:00")
                )

                embed.add_field(
                    name="Seerr Username",
                    value=user["seerr_username"],
                    inline=True,
                )

                embed.add_field(
                    name="Discord Username",
                    value=f"<@{user['discord_id']}>",
                    inline=True,
                )

                embed.add_field(
                    name="Linked",
                    value=f"<t:{int(linked_time.timestamp())}:R>",
                    inline=True,
                )

            if len(users) > 10:
                embed.set_footer(text=f"Showing 10 of {len(users)} users")
            else:
                embed.set_footer(text="All linked users shown")

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in admin_users command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while fetching users.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="force-link-member",
        description="Force link a Discord member to a Seerr account",
    )
    @app_commands.guild_only()
    @is_admin()
    async def admin_force_link_member(
        self, interaction: discord.Interaction, user: discord.Member, seerr_user_id: int
    ):
        """Force link a Discord member to a Seerr account"""
        if seerr_user_id <= 0:
            embed = discord.Embed(
                title="Invalid Input",
                description="Seerr user ID must be a positive number.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            existing_account = self.database.get_seerr_account_by_discord_id(str(user.id))
            if existing_account:
                embed = discord.Embed(
                    title="User Already Linked",
                    description=f"{user.mention} is already linked to Seerr user: **{existing_account['seerr_username']}**",
                    color=discord.Color.orange(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            logger.debug(f"Fetching Seerr user with ID: {seerr_user_id}")
            seerr_user = self.seerr_api.get_user_by_id(seerr_user_id)
            if not seerr_user:
                embed = discord.Embed(
                    title="Seerr User Not Found",
                    description=f"Seerr user with ID {seerr_user_id} was not found.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            logger.debug(f"Seerr user data: {seerr_user}")
            seerr_username = (
                seerr_user.get("username")
                or seerr_user.get("plexUsername")
                or seerr_user.get("jellyfinUsername")
                or seerr_user.get("displayName")
                or seerr_user.get("email")
                or f"User-{seerr_user_id}"
            )
            logger.debug(f"Extracted username: {seerr_username}")

            if not seerr_username or seerr_username.strip() == "":
                embed = discord.Embed(
                    title="Invalid Seerr User",
                    description=f"Seerr user {seerr_user_id} has no valid username.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            self.database.add_user(str(user.id), user.display_name)

            logger.debug(
                f"Attempting to link account: discord_id={user.id}, seerr_user_id={seerr_user_id}, seerr_username={seerr_username}"
            )
            success = self.database.link_seerr_account(
                discord_id=str(user.id),
                seerr_user_id=seerr_user_id,
                seerr_username=seerr_username,
            )
            logger.debug(f"Link result: {success}")

            if success:
                logger.info(
                    f"Admin {interaction.user.id} force-linked Discord user {user.id} to Seerr user {seerr_user_id}"
                )

                embed = discord.Embed(
                    title="Force Link Successful",
                    description=f"{user.mention} has been linked to Seerr user: **{seerr_username}**",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Force Link Failed",
                    description="Failed to link the account. Please try again.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in admin_force_link_member command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while force linking the account.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unlink-member", description="Unlink a Discord member from their Seerr account"
    )
    @app_commands.guild_only()
    @is_admin()
    async def admin_unlink_member(self, interaction: discord.Interaction, user: discord.Member):
        """Unlink a Discord member from Seerr"""
        try:
            existing_account = self.database.get_seerr_account_by_discord_id(str(user.id))
            if not existing_account:
                embed = discord.Embed(
                    title="No Linked Account",
                    description=f"{user.mention} doesn't have a linked Seerr account.",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            success = self.database.unlink_seerr_account(str(user.id))

            if success:
                logger.info(
                    f"Admin {interaction.user.id} unlinked Discord member {user.id} from Seerr user {existing_account['seerr_user_id']}"
                )

                embed = discord.Embed(
                    title="Unlink Successful",
                    description=f"{user.mention} has been unlinked from Seerr user: **{existing_account['seerr_username']}**",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Unlink Failed",
                    description="Failed to unlink the account. Please try again.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in admin_unlink_member command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while unlinking the account.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unlink-user", description="Unlink a Discord user from their Seerr account"
    )
    @app_commands.describe(discord_id="The Discord ID to unlink")
    @is_admin()
    async def admin_unlink(self, interaction: discord.Interaction, discord_id: str):
        """Unlink a Discord user from Seerr"""
        if not discord_id.isdigit() or len(discord_id) < 17:
            embed = discord.Embed(
                title="Invalid Discord ID",
                description="Discord ID must be a numeric value with at least 17 digits.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            existing_account = self.database.get_seerr_account_by_discord_id(discord_id)
            if not existing_account:
                embed = discord.Embed(
                    title="No Linked Account",
                    description=f"Discord ID `{discord_id}` doesn't have a linked Seerr account.",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            success = self.database.unlink_seerr_account(discord_id)

            if success:
                logger.info(
                    f"Admin {interaction.user.id} unlinked Discord ID {discord_id} from Seerr user {existing_account['seerr_user_id']}"
                )

                embed = discord.Embed(
                    title="Unlink Successful",
                    description=f"Discord ID `{discord_id}` has been unlinked from Seerr user: **{existing_account['seerr_username']}**",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Unlink Failed",
                    description="Failed to unlink the account. Please try again.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in admin_unlink command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while unlinking the account.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="sync", description="Sync bot commands with Discord")
    @is_admin()
    async def sync_commands(self, interaction: discord.Interaction):
        """Sync bot commands with Discord"""
        try:
            embed = discord.Embed(
                title="Syncing Commands",
                description="Syncing commands with Discord...",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            max_retries = 3

            for attempt in range(max_retries):
                try:
                    if Config.DISCORD_GUILD_ID:
                        await asyncio.wait_for(
                            self.bot.tree.sync(guild=discord.Object(id=Config.DISCORD_GUILD_ID)),
                            timeout=60.0,
                        )
                        sync_type = f"guild {Config.DISCORD_GUILD_ID}"
                    else:
                        await asyncio.wait_for(self.bot.tree.sync(), timeout=60.0)
                        sync_type = "globally"

                    break

                except TimeoutError:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                    else:
                        raise
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(5)
                    else:
                        raise

            embed = discord.Embed(
                title="Commands Synced",
                description=f"Commands have been synced {sync_type} successfully!",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except TimeoutError:
            logger.error("Command sync timed out")
            embed = discord.Embed(
                title="Sync Timeout",
                description="Command sync timed out. Please try again or check Discord's status.",
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            embed = discord.Embed(
                title="Sync Failed",
                description=f"Failed to sync commands: {str(e)}",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="force-link",
        description="Force link a Seerr account to a Discord ID",
    )
    @app_commands.describe(
        seerr_username="The Seerr username to link",
        discord_id="The Discord ID to link to",
    )
    @is_admin()
    async def force_link(
        self, interaction: discord.Interaction, seerr_username: str, discord_id: str
    ):
        """Force link a Seerr account to a Discord ID, overriding any existing links"""
        if not seerr_username.strip():
            embed = discord.Embed(
                title="Invalid Input",
                description="Seerr username cannot be empty.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not discord_id.isdigit() or len(discord_id) < 17:
            embed = discord.Embed(
                title="Invalid Discord ID",
                description="Discord ID must be a numeric value with at least 17 digits.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            if not self.seerr_api.test_connection():
                embed = discord.Embed(
                    title="Connection Error",
                    description="Unable to connect to Seerr. Please check your configuration.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            seerr_user = self.seerr_api.get_user_by_username(seerr_username)
            if not seerr_user:
                embed = discord.Embed(
                    title="User Not Found",
                    description=f"Seerr user '{seerr_username}' was not found.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            existing_link = self.database.get_seerr_account_by_discord_id(discord_id)
            if existing_link:
                embed = discord.Embed(
                    title="Discord ID Already Linked",
                    description=f"Discord ID {discord_id} is already linked to Seerr user: **{existing_link['seerr_username']}**\n\nThis will override the existing link.",
                    color=discord.Color.orange(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            username = (
                seerr_user.get("username")
                or seerr_user.get("plexUsername")
                or seerr_user.get("jellyfinUsername")
                or seerr_user.get("displayName")
                or seerr_user.get("email")
                or f"User-{seerr_user['id']}"
            )

            if not username or username.strip() == "":
                embed = discord.Embed(
                    title="Invalid Seerr User",
                    description=f"Seerr user '{seerr_username}' has no valid username.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            success = self.database.force_link_seerr_account(
                discord_id=discord_id,
                seerr_user_id=seerr_user["id"],
                seerr_username=username,
            )

            if success:
                logger.info(
                    f"Admin {interaction.user.id} force-linked Seerr user {seerr_user['id']} to Discord ID {discord_id}"
                )

                embed = discord.Embed(
                    title="Account Force-Linked Successfully!",
                    description=f"Seerr user **{username}** has been force-linked to Discord ID: **{discord_id}**",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Force-Linking Failed",
                    description="Failed to force-link the account. Please try again.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in force_link command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while force-linking the account.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="check-discord-id",
        description="Check if a Discord ID is linked to a Seerr account",
    )
    @app_commands.describe(discord_id="The Discord ID to check")
    @is_admin()
    async def check_discord_id(self, interaction: discord.Interaction, discord_id: str):
        """Check if a Discord ID is linked and show details"""
        if not discord_id.isdigit() or len(discord_id) < 17:
            embed = discord.Embed(
                title="Invalid Discord ID",
                description="Discord ID must be a numeric value with at least 17 digits.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            linked_account = self.database.get_seerr_account_by_discord_id(discord_id)

            embed = discord.Embed(
                title="Discord ID Check",
                description=f"Checking Discord ID: `{discord_id}`",
                color=discord.Color.blue(),
            )

            if linked_account:
                embed.add_field(
                    name="Status",
                    value=" Linked",
                    inline=True,
                )
                embed.add_field(
                    name="Seerr User",
                    value=linked_account["seerr_username"],
                    inline=True,
                )
                embed.add_field(
                    name="Seerr User ID",
                    value=str(linked_account["seerr_user_id"]),
                    inline=True,
                )
                embed.add_field(
                    name="Linked At",
                    value=linked_account["linked_at"],
                    inline=True,
                )
            else:
                embed.add_field(
                    name="Status",
                    value="Not Linked",
                    inline=True,
                )
                embed.add_field(
                    name="Note",
                    value="This Discord ID is not linked to any Seerr account",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error checking Discord ID: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while checking the Discord ID.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reset-commands", description="Completely reset all commands")
    @is_admin()
    async def reset_commands(self, interaction: discord.Interaction):
        """Completely reset all commands"""
        try:
            embed = discord.Embed(
                title="Resetting Commands",
                description="Completely clearing and resetting all commands...",
                color=discord.Color.blue(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

            self.bot.tree.clear_commands()

            if Config.DISCORD_GUILD_ID:
                await self.bot.tree.sync(guild=discord.Object(id=Config.DISCORD_GUILD_ID))
                reset_type = f"guild {Config.DISCORD_GUILD_ID}"
            else:
                await self.bot.tree.sync()
                reset_type = "globally"

            await asyncio.sleep(2)

            await self.bot.add_cog(SeerrCommands(self.bot, self.database, self.seerr_api))
            await self.bot.add_cog(AdminCommands(self.bot, self.database, self.seerr_api))

            if Config.DISCORD_GUILD_ID:
                await self.bot.tree.sync(guild=discord.Object(id=Config.DISCORD_GUILD_ID))
            else:
                await self.bot.tree.sync()

            embed = discord.Embed(
                title="Commands Reset",
                description=f"All commands have been completely reset {reset_type}!",
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error resetting commands: {e}")
            embed = discord.Embed(
                title="Reset Failed",
                description="Failed to reset commands. Please restart the bot.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
