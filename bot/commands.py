import logging

import discord
from discord import app_commands
from discord.ext import commands

from database.database import Database
from seerr.api import SeerrAPI

logger = logging.getLogger(__name__)


class SeerrCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, database: Database, seerr_api: SeerrAPI):
        self.bot = bot
        self.database = database
        self.seerr_api = seerr_api

    @app_commands.command(
        name="link-account",
        description="Link your Discord account to your Seerr account",
    )
    async def link_account(self, interaction: discord.Interaction):
        """Link Discord account to Seerr account"""
        try:
            existing_account = self.database.get_seerr_account_by_discord_id(
                str(interaction.user.id)
            )
            if existing_account:
                embed = discord.Embed(
                    title="Account Already Linked",
                    description=f"Your Discord account is already linked to Seerr user: **{existing_account['seerr_username']}**",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            existing_discord_link = self.database.get_seerr_account_by_discord_id(
                str(interaction.user.id)
            )
            if existing_discord_link:
                embed = discord.Embed(
                    title="Discord ID Already in Use",
                    description="This Discord ID is already linked to another Seerr account. Contact an admin if this is incorrect.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            if not self.seerr_api.test_connection():
                embed = discord.Embed(
                    title="Connection Error",
                    description="Unable to connect to Seerr. Please check your configuration.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            logger.info(f"Attempting to link account for Discord user: {interaction.user.id}")
            seerr_user = self.seerr_api.verify_user_discord_id(str(interaction.user.id))

            if not seerr_user:
                embed = discord.Embed(
                    title="Account Not Found",
                    description="Your Discord ID was not found in Seerr. Please make sure you have added your Discord ID to your Seerr profile first.",
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name="How to add Discord ID",
                    value="1. Go to your Seerr profile\n2. Add your Discord ID to your profile\n3. Try linking again",
                    inline=False,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            seerr_username = (
                seerr_user.get("username")
                or seerr_user.get("plexUsername")
                or seerr_user.get("jellyfinUsername")
                or seerr_user.get("displayName")
                or seerr_user.get("email", "Unknown")
            )

            is_seerr_admin = seerr_user.get("id") == 1

            self.database.add_user(str(interaction.user.id), interaction.user.name)
            if is_seerr_admin:
                self.database.set_user_admin(str(interaction.user.id), True)
                logger.info(
                    f"User {seerr_username} is a Seerr admin (ID: 1) - setting as bot admin"
                )

            success = self.database.link_seerr_account(
                discord_id=str(interaction.user.id),
                seerr_user_id=seerr_user["id"],
                seerr_username=seerr_username,
            )

            if success:
                embed = discord.Embed(
                    title="Account Linked Successfully!",
                    description=f"Your Discord account has been linked to Seerr user: **{seerr_username}**",
                    color=discord.Color.green(),
                )

                if is_seerr_admin:
                    embed.add_field(
                        name="Admin Access",
                        value="You have been automatically granted admin access to the bot.",
                        inline=False,
                    )

                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Link Failed",
                    description="Failed to link your account. Please try again or contact an administrator.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in link_account command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while linking your account. Please try again.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="unlink-account", description="Unlink your Discord account from Seerr"
    )
    async def unlink_account(self, interaction: discord.Interaction):
        """Unlink Discord account from Seerr account"""
        try:
            existing_account = self.database.get_seerr_account_by_discord_id(
                str(interaction.user.id)
            )
            if not existing_account:
                embed = discord.Embed(
                    title="No Linked Account",
                    description="Your Discord account is not linked to any Seerr account.",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            success = self.database.unlink_seerr_account(str(interaction.user.id))

            if success:
                embed = discord.Embed(
                    title="Account Unlinked Successfully!",
                    description=f"Your Discord account has been unlinked from Seerr user: **{existing_account['seerr_username']}**",
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="Unlink Failed",
                    description="Failed to unlink your account. Please try again or contact an administrator.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in unlink_account command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while unlinking your account. Please try again.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="status", description="Check your account status and request statistics"
    )
    async def status(self, interaction: discord.Interaction):
        """Check account status and statistics"""
        try:
            account = self.database.get_seerr_account_by_discord_id(str(interaction.user.id))
            if not account:
                embed = discord.Embed(
                    title="No Linked Account",
                    description="You need to link your Seerr account first using `/link-account`.",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="Account Status",
                description=f"**Seerr User:** {account['seerr_username']}",
                color=discord.Color.blue(),
            )

            try:
                user_stats = self.seerr_api.get_user_stats(account["seerr_user_id"])
                if user_stats:
                    embed.add_field(
                        name="Request Statistics",
                        value=f"**Total Requests:** {user_stats.get('total', 'N/A')}\n"
                        f"**Approved:** {user_stats.get('approved', 'N/A')}\n"
                        f"**Pending:** {user_stats.get('pending', 'N/A')}\n"
                        f"**Declined:** {user_stats.get('declined', 'N/A')}",
                        inline=False,
                    )
            except Exception as e:
                logger.warning(f"Could not fetch user stats: {e}")

            embed.add_field(
                name="Linked Since",
                value=account["linked_at"],
                inline=True,
            )

            embed.add_field(
                name="Account Status",
                value="Active" if account["is_active"] else "Inactive",
                inline=True,
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in status command: {e}")
            embed = discord.Embed(
                title="Error",
                description="An error occurred while checking your status. Please try again.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
