import asyncio
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler

import discord
from discord.ext import commands

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.webhook_server import WebhookServer
from bot.admin_commands import AdminCommands
from bot.commands import SeerrCommands
from config import Config
from database.database import Database
from seerr.api import SeerrAPI

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            "data/logs/discordeerr.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class SeerrBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix=None, intents=intents, help_command=None)

        self.database = Database()
        self.seerr_api = SeerrAPI()
        self.webhook_server = None

    async def setup_hook(self):
        """Setup hook called when bot is starting"""
        logger.info("Setting up bot...")

        await self.add_cog(SeerrCommands(self, self.database, self.seerr_api))
        await self.add_cog(AdminCommands(self, self.database, self.seerr_api))

        logger.info("Bot setup complete")

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        logger.info("Syncing commands to Discord...")

        commands = list(self.tree.get_commands())
        logger.debug(f"Registered {len(commands)} commands")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Syncing commands globally (attempt {attempt + 1}/{max_retries})")
                await asyncio.wait_for(self.tree.sync(), timeout=60.0)

                logger.info("Commands synced successfully!")
                break

            except TimeoutError:
                logger.warning(f"Command sync timed out (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    logger.debug("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    logger.error("Command sync failed after all retries")
            except Exception as e:
                logger.error(f"Error syncing commands (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    logger.debug("Retrying in 5 seconds...")
                    await asyncio.sleep(5)
                else:
                    logger.error("Command sync failed after all retries")

        await self.test_connections()
        await self.start_webhook_server()

        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="Seerr requests")
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ):
        """Handle application command errors gracefully"""
        if isinstance(error, discord.app_commands.errors.CommandNotFound):
            logger.warning(
                f"Command not found: {interaction.command.name if interaction.command else 'Unknown'}"
            )
            embed = discord.Embed(
                title="Command Not Found",
                description="This command has been removed or is not available. Please try refreshing Discord or contact an administrator.",
                color=discord.Color.red(),
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except discord.errors.InteractionResponded:
                    pass
        elif isinstance(error, discord.app_commands.errors.MissingPermissions):
            embed = discord.Embed(
                title="Permission Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                pass
        elif isinstance(error, discord.app_commands.errors.CheckFailure):
            pass
        else:
            logger.error(f"Application command error: {error}")
            embed = discord.Embed(
                title="Error",
                description="An unexpected error occurred. Please try again later.",
                color=discord.Color.red(),
            )
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                pass

    async def on_error(self, event_method: str, *args, **kwargs):
        """Handle all bot errors including command tree errors"""
        logger.error(f"Error in {event_method}: {args} {kwargs}")

        if event_method == "on_interaction" and args:
            interaction = args[0]
            if hasattr(interaction, "response") and not interaction.response.is_done():
                embed = discord.Embed(
                    title="Command Error",
                    description="This command is no longer available. Please try refreshing Discord or contact an administrator.",
                    color=discord.Color.red(),
                )
                try:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                except discord.errors.InteractionResponded:
                    pass

    async def test_connections(self):
        """Test all external connections"""
        logger.info("Testing connections...")

        if self.seerr_api.test_connection():
            logger.info("Seerr API connection successful")
        else:
            logger.warning("Seerr API connection failed")

        try:
            self.database.get_admin_setting("test")
            logger.info("Database connection successful")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")

    async def start_webhook_server(self):
        """Start the webhook server"""
        try:
            self.webhook_server = WebhookServer(self, self.database, self.seerr_api)
            self.webhook_server.start_in_thread()
            logger.info("Webhook server started")
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("I don't have the required permissions to execute this command.")
        else:
            logger.error(f"Command error: {error}")
            await ctx.send("An error occurred while executing the command.")

    async def cleanup(self):
        """Cleanup resources before shutdown"""
        logger.info("Cleaning up bot resources...")

        try:
            if hasattr(self, "webhook_server") and self.webhook_server:
                logger.info("Stopping webhook server...")
                self.webhook_server.stop()

            if hasattr(self, "database") and self.database:
                logger.info("Closing database connections...")

            logger.info("Bot cleanup complete")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


async def main():
    """Main function to run the bot"""
    if not Config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is required in environment variables or .env file")
        sys.exit(1)

    if not Config.SEERR_URL:
        logger.warning("SEERR_URL not configured - some features may not work")

    if not Config.SEERR_API_KEY:
        logger.warning("SEERR_API_KEY not configured - some features may not work")

    bot = SeerrBot()
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if not shutdown_requested:
            shutdown_requested = True
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            if hasattr(bot, "loop") and bot.loop and not bot.loop.is_closed():
                bot.loop.create_task(shutdown_bot(bot))
            else:
                logger.info("Bot not fully started, exiting...")
                sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        if not shutdown_requested:
            await shutdown_bot(bot)


async def shutdown_bot(bot):
    """Gracefully shutdown the bot"""
    logger.info("Shutting down bot gracefully...")

    try:
        await bot.cleanup()

        if not bot.is_closed():
            logger.info("Closing bot connection...")
            await bot.close()

        logger.info("Bot shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


if __name__ == "__main__":
    asyncio.run(main())
