import json
import logging
from datetime import datetime
from typing import Any

import discord

from config import Config
from database.database import Database
from seerr.api import SeerrAPI

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __init__(self, bot: discord.Client, database: Database, seerr_api: SeerrAPI):
        self.bot = bot
        self.database = database
        self.seerr_api = seerr_api

    async def process_webhook(self, webhook_data: dict[str, Any]) -> bool:
        """Process incoming webhook data from Seerr"""
        try:
            # Extract notification type from the webhook data
            notification_type = webhook_data.get("notification_type", "unknown")

            # Map notification types to our event types
            event_type = self._map_notification_type(notification_type)

            # Extract user ID from the appropriate field based on notification type
            seerr_user_id = self._extract_user_id_by_notification_type(
                webhook_data, notification_type
            )

            payload = json.dumps(webhook_data)

            event_id = self.database.log_webhook_event(
                event_type=event_type, seerr_user_id=seerr_user_id, payload=payload
            )

            if not event_id:
                logger.error("Failed to log webhook event")
                return False

            # Process based on event type
            match event_type:
                case "request_pending_approval":
                    success = await self._handle_request_pending(webhook_data, event_id)
                case "request_auto_approved":
                    success = await self._handle_request_auto_approved(webhook_data, event_id)
                case "request_approved":
                    success = await self._handle_request_approved(webhook_data, event_id)
                case "request_declined":
                    success = await self._handle_request_declined(webhook_data, event_id)
                case "request_available":
                    success = await self._handle_request_available(webhook_data, event_id)
                case "request_processing_failed":
                    success = await self._handle_request_failed(webhook_data, event_id)
                case "issue_reported":
                    success = await self._handle_issue_reported(
                        webhook_data, event_id, seerr_user_id
                    )
                case "issue_comment":
                    success = await self._handle_issue_comment(
                        webhook_data, event_id, seerr_user_id
                    )
                case "issue_resolved":
                    success = await self._handle_issue_resolved(
                        webhook_data, event_id, seerr_user_id
                    )
                case "issue_reopened":
                    success = await self._handle_issue_reopened(
                        webhook_data, event_id, seerr_user_id
                    )
                case "test_notification":
                    success = await self._handle_test_notification(webhook_data, event_id)
                case _:
                    logger.info(f"Unhandled webhook event type: {notification_type}")
                    success = True  # Don't fail for unhandled events

            return success

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False

    def _map_notification_type(self, notification_type: str) -> str:
        """Map Seerr notification types to our internal event types"""
        mapping = {
            # Media Request Notifications
            "MEDIA_PENDING": "request_pending_approval",
            "MEDIA_AUTO_APPROVED": "request_auto_approved",
            "MEDIA_APPROVED": "request_approved",
            "MEDIA_DECLINED": "request_declined",
            "MEDIA_AVAILABLE": "request_available",
            "MEDIA_FAILED": "request_processing_failed",
            # Issue Notifications
            "ISSUE_CREATED": "issue_reported",
            "ISSUE_COMMENT": "issue_comment",
            "ISSUE_RESOLVED": "issue_resolved",
            "ISSUE_REOPENED": "issue_reopened",
            # Test Notification
            "TEST_NOTIFICATION": "test_notification",
        }
        return mapping.get(notification_type, notification_type.lower())

    def _extract_user_id_by_notification_type(
        self, webhook_data: dict[str, Any], notification_type: str
    ) -> int | None:
        """Extract user ID from webhook data based on notification type"""
        try:
            # Define field mappings for different notification types
            field_mappings = {
                # Request notifications that should send DMs
                "MEDIA_APPROVED": "notifyuser_settings_discordId",
                "MEDIA_DECLINED": "notifyuser_settings_discordId",
                "MEDIA_AVAILABLE": "notifyuser_settings_discordId",
                # Issue notifications - only resolved/reopened send DMs
                "ISSUE_RESOLVED": "reportedBy_settings_discordId",
                "ISSUE_REOPENED": "reportedBy_settings_discordId",
                # Comment notifications
                "ISSUE_COMMENT": "commentedBy_settings_discordId",
            }

            # Get the appropriate field for this notification type
            field_name = field_mappings.get(notification_type)
            if not field_name:
                # Admin notifications (no specific user)
                return None

            return self._extract_user_id_with_validation(webhook_data, field_name, field_name)

        except Exception as e:
            logger.error(f"Error extracting user ID for notification type {notification_type}: {e}")
            return None

    def _extract_user_id_with_validation(
        self,
        webhook_data: dict[str, Any],
        notification_discord_id_field: str,
        expected_discord_id_field: str,
    ) -> int | None:
        """Extract user ID with validation that Discord IDs match"""
        try:
            # Get the Discord ID from the notification
            notification_discord_id = webhook_data.get(notification_discord_id_field)
            if not notification_discord_id:
                logger.debug(f"No Discord ID found in {notification_discord_id_field}")
            return None

            # Get the expected Discord ID (should be the same for most cases)
            expected_discord_id = webhook_data.get(expected_discord_id_field)

            # Validate that the Discord IDs match (if both are present)
            if expected_discord_id and notification_discord_id != expected_discord_id:
                logger.warning(
                    f"Discord ID mismatch: notification={notification_discord_id}, expected={expected_discord_id}. "
                    f"This might indicate a configuration issue in Seerr."
                )
                # For now, we'll still try to send the DM to the notification Discord ID
                # but log the warning for admin awareness

            # Convert Discord ID to Seerr user ID
            seerr_user_id = self.database.get_seerr_user_id_by_discord_id(notification_discord_id)
            if seerr_user_id:
                logger.debug(
                    f"Found Seerr user {seerr_user_id} for Discord ID {notification_discord_id}"
                )
                return seerr_user_id
            else:
                logger.debug(f"No linked account found for Discord ID {notification_discord_id}")
                return None

        except Exception as e:
            logger.error(f"Error extracting user ID with validation: {e}")
            return None

    async def _handle_request_pending(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request pending approval event"""
        return await self._handle_admin_request(
            data, event_id, "Pending Approval", discord.Color.orange()
        )

    async def _handle_request_auto_approved(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request automatically approved event"""
        return await self._handle_admin_request(
            data, event_id, "Processing", discord.Color.purple()
        )

    async def _handle_admin_request(
        self, data: dict[str, Any], event_id: int, status: str, color: discord.Color
    ) -> bool:
        """Handle admin-only request notifications (channel only)"""
        try:
            embed = self._create_request_embed(data=data, status=status, color=color)
            view = self._create_request_view()
            return await self._send_channel_notification(embed, event_id, view)
        except Exception as e:
            logger.error(f"Error handling admin request: {e}")
            return False

    async def _handle_request_approved(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request approved event"""
        return await self._handle_user_request(
            data, event_id, "Processing", discord.Color.purple(), "request_approved"
        )

    async def _handle_request_declined(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request declined event"""
        return await self._handle_user_request(
            data, event_id, "Declined", discord.Color.red(), "request_declined"
        )

    async def _handle_request_available(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request available event"""
        return await self._handle_user_request(
            data, event_id, "Available", discord.Color.green(), "request_available"
        )

    async def _handle_user_request(
        self,
        data: dict[str, Any],
        event_id: int,
        status: str,
        color: discord.Color,
        notification_type: str,
    ) -> bool:
        """Handle user request notifications (DM + channel)"""
        try:
            user_id = self._extract_user_id_with_validation(
                data, "notifyuser_settings_discordId", "notifyuser_settings_discordId"
            )
            embed = self._create_request_embed(data=data, status=status, color=color)
            view = self._create_request_view()
            return await self._send_notifications(user_id, embed, event_id, notification_type, view)
        except Exception as e:
            logger.error(f"Error handling user request: {e}")
            return False

    async def _handle_request_failed(self, data: dict[str, Any], event_id: int) -> bool:
        """Handle request processing failed event"""
        try:
            # Admin notification - channel only

            # Create standardized request embed
            embed = self._create_request_embed(
                data=data,
                status="Failed",
                color=discord.Color.red(),
            )

            # Add error details if available
            if data.get("extra"):
                embed.add_field(name="Error", value=str(data["extra"]), inline=False)

            # Create view with button to Seerr requests
            view = self._create_request_view()

            # Send only to channel for admin notifications
            return await self._send_channel_notification(embed, event_id, view)

        except Exception as e:
            logger.error(f"Error handling request failed: {e}")
            return False

    async def _handle_issue_reported(
        self, data: dict[str, Any], event_id: int, user_id: int | None = None
    ) -> bool:
        """Handle issue reported event"""
        return await self._handle_issue_event(
            data, event_id, user_id, "issue_reported", discord.Color.red()
        )

    async def _handle_issue_comment(
        self, data: dict[str, Any], event_id: int, user_id: int | None = None
    ) -> bool:
        """Handle issue comment event"""
        return await self._handle_issue_event(
            data, event_id, user_id, "issue_comment", discord.Color.blue(), add_comment=True
        )

    async def _handle_issue_event(
        self,
        data: dict[str, Any],
        event_id: int,
        user_id: int | None,
        notification_type: str,
        color: discord.Color,
        add_comment: bool = False,
    ) -> bool:
        """Generic issue event handler"""
        try:
            embed = self._create_issue_embed(data, color)

            if add_comment:
                commented_by_username = data.get("commentedBy_username")
                comment_message = data.get("comment_message")
                if commented_by_username and comment_message:
                    embed.add_field(
                        name=f"Comment from {commented_by_username}",
                        value=comment_message,
                        inline=False,
                    )

            view = self._create_issue_view(data.get("issue_id"))
            return await self._send_notifications(user_id, embed, event_id, notification_type, view)

        except Exception as e:
            logger.error(f"Error handling issue event {notification_type}: {e}")
            return False

    def _create_view(self, label: str, url: str) -> discord.ui.View | None:
        """Create a reusable view with button"""
        if not url or not Config.SEERR_URL:
            return None

        from discord.ui import Button, View

        view = View(timeout=None)
        view.add_item(
            Button(
                label=label,
                url=url,
                style=discord.ButtonStyle.link,
            )
        )
        return view

    def _create_request_view(self) -> discord.ui.View | None:
        """Create a reusable view with button to redirect to requests"""
        return self._create_view("View Requests", f"{Config.SEERR_URL}/requests")

    def _create_issue_view(self, issue_id: str) -> discord.ui.View | None:
        """Create a reusable view with button to redirect to issue"""
        if not issue_id:
            return None
        return self._create_view("View Issue", f"{Config.SEERR_URL}/issues/{issue_id}")

    def _create_issue_embed(self, data: dict[str, Any], color: discord.Color) -> discord.Embed:
        """Create a standardized issue embed with common fields"""
        media_title = data.get("subject", "Unknown Title")
        media_type = data.get("media_type", "Unknown")
        media_tmdbid = data.get("media_tmdbid", "")
        media_image = data.get("image", "")
        issue_type = data.get("issue_type", "Unknown")
        issue_status = data.get("issue_status", "Unknown")
        reported_by_username = data.get("reportedBy_username", "Unknown")
        reported_by_avatar = data.get("reportedBy_avatar", "")
        commented_by_username = data.get("commentedBy_username", "")
        commented_by_avatar = data.get("commentedBy_avatar", "")
        event_title = data.get("event", "Issue Update")

        if media_tmdbid and Config.SEERR_URL:
            if media_type.lower() == "tv":
                media_url = f"{Config.SEERR_URL}/tv/{media_tmdbid}"
            else:
                media_url = f"{Config.SEERR_URL}/movie/{media_tmdbid}"
            description = f"[{media_title}]({media_url})"
        else:
            description = media_title

        embed = discord.Embed(
            title=event_title,
            description=description,
            color=color,
            timestamp=datetime.utcnow(),
        )

        if commented_by_username and commented_by_avatar:
            embed.set_author(name=commented_by_username, icon_url=commented_by_avatar)
        elif reported_by_avatar:
            embed.set_author(name=reported_by_username, icon_url=reported_by_avatar)
        else:
            embed.set_author(name=reported_by_username)

        issue_message = data.get("message", "Unknown issue")
        embed.add_field(name="Issue", value=issue_message, inline=False)

        embed.add_field(name="Reported By", value=reported_by_username, inline=True)
        embed.add_field(name="Issue Type", value=issue_type.title(), inline=True)
        embed.add_field(name="Issue Status", value=issue_status.title(), inline=True)

        if media_type.lower() == "tv":
            extra_data = data.get("extra", [])
            if extra_data and isinstance(extra_data, list):
                for extra_item in extra_data:
                    if (
                        isinstance(extra_item, dict)
                        and "name" in extra_item
                        and "value" in extra_item
                    ):
                        if "season" in extra_item["name"].lower():
                            embed.add_field(
                                name="Affected Season",
                                value=extra_item["value"],
                                inline=True,
                            )
                            break

        if media_image:
            embed.set_thumbnail(url=media_image)

        return embed

    def _create_request_embed(
        self, data: dict[str, Any], status: str, color: discord.Color
    ) -> discord.Embed:
        """Create a standardized request embed with common fields"""
        media_title = data.get("subject", "Unknown Title")
        media_type = data.get("media_type", "Unknown")
        media_tmdbid = data.get("media_tmdbid", "")
        media_image = data.get("image", "")
        requester_username = data.get("requestedBy_username", "Unknown")
        requester_avatar = data.get("requestedBy_avatar", "")
        event_title = data.get("event", "Request Update")

        if media_tmdbid and Config.SEERR_URL:
            if media_type.lower() == "tv":
                media_url = f"{Config.SEERR_URL}/tv/{media_tmdbid}"
            else:
                media_url = f"{Config.SEERR_URL}/movie/{media_tmdbid}"
            description = f"[{media_title}]({media_url})\n\n{data.get('message', '')}"
        else:
            description = f"{media_title}\n\n{data.get('message', '')}"

        embed = discord.Embed(
            title=event_title,
            description=description,
            color=color,
            timestamp=datetime.utcnow(),
        )

        if requester_avatar:
            embed.set_author(name=requester_username, icon_url=requester_avatar)
        else:
            embed.set_author(name=requester_username)

        embed.add_field(
            name="Requested By",
            value=requester_username,
            inline=True,
        )

        if media_type.lower() == "tv":
            seasons = data.get("extra", [])
            if seasons and isinstance(seasons, list):
                season_info = []
                for season in seasons:
                    if isinstance(season, dict) and "name" in season and "value" in season:
                        if "season" in season["name"].lower():
                            season_info.append(season["value"])
                if season_info:
                    embed.add_field(
                        name="Requested Seasons",
                        value=", ".join(season_info),
                        inline=True,
                    )

        embed.add_field(
            name="Request Status",
            value=status,
            inline=True,
        )

        if media_image:
            embed.set_thumbnail(url=media_image)

        return embed

    async def _handle_issue_resolved(
        self, data: dict[str, Any], event_id: int, user_id: int | None = None
    ) -> bool:
        """Handle issue resolved event"""
        return await self._handle_issue_event(
            data, event_id, user_id, "issue_resolved", discord.Color.green()
        )

    async def _handle_issue_reopened(
        self, data: dict[str, Any], event_id: int, user_id: int | None = None
    ) -> bool:
        """Handle issue reopened event"""
        return await self._handle_issue_event(
            data, event_id, user_id, "issue_reopened", discord.Color.gold()
        )

    async def _handle_test_notification(self, webhook_data: dict[str, Any], event_id: int) -> bool:
        """Handle test notification from Seerr"""
        try:
            logger.info("Processing test notification")

            embed = discord.Embed(
                title="Test Notification",
                description=webhook_data.get("message", "Test notification received"),
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )

            discord_id = webhook_data.get("notifyuser_settings_discordId")
            sent_dm = False
            sent_channel = False

            # Send DM if Discord ID provided
            if discord_id:
                user = self.bot.get_user(int(discord_id))
                if user:
                    await user.send(embed=embed)
                    logger.info(f"Sent test notification DM to user {discord_id}")
                    sent_dm = True

            # Always send to channel if configured
            if Config.NOTIFICATION_CHANNEL_ID:
                channel = self.bot.get_channel(Config.NOTIFICATION_CHANNEL_ID)
                if channel:
                    await channel.send(embed=embed)
                    logger.info("Sent test notification to channel")
                    sent_channel = True

            # Mark as processed
            self.database.mark_webhook_processed(event_id, sent_dm, sent_channel)
            return sent_dm or sent_channel

        except Exception as e:
            logger.error(f"Error handling test notification: {e}")
            return False

    async def _send_notifications(
        self,
        seerr_user_id: int | None,
        embed: discord.Embed,
        event_id: int,
        notification_type: str,
        view: discord.ui.View = None,
    ) -> bool:
        """Send notifications to both DM and channel"""
        try:
            # If no Seerr user ID, just send to channel
            if seerr_user_id is None:
                logger.debug("No Seerr user ID provided, sending to channel only")
                sent_channel = await self._send_channel_notification(embed, event_id, view)
                self.database.mark_webhook_processed(event_id, False, sent_channel)
                return sent_channel

            # Get Discord ID for the Seerr user
            discord_id = self.database.get_discord_id_by_seerr_id(seerr_user_id)

            if not discord_id:
                logger.debug(f"No Discord ID found for Seerr user {seerr_user_id}")
                # Still send to channel if configured
                sent_channel = await self._send_channel_notification(embed, event_id, view)
                self.database.mark_webhook_processed(event_id, False, sent_channel)
                return sent_channel

            sent_dm = False
            sent_channel = False

            # Always send DM to user (the main feature)
            sent_dm = await self._send_dm_notification(discord_id, embed, view)

            # Always send to channel (for admin visibility)
            sent_channel = await self._send_channel_notification(embed, event_id, view)

            # Mark as processed
            self.database.mark_webhook_processed(event_id, sent_dm, sent_channel)

            return sent_dm or sent_channel

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return False

    async def _send_dm_notification(
        self, discord_id: str, embed: discord.Embed, view: discord.ui.View = None
    ) -> bool:
        """Send DM notification to user"""
        try:
            user = self.bot.get_user(int(discord_id))
            if user:
                await user.send(embed=embed, view=view)
                logger.debug(f"Sent DM notification to user {discord_id}")
                return True
            else:
                logger.warning(f"Could not find user {discord_id} for DM")
                return False
        except Exception as e:
            logger.error(f"Error sending DM to {discord_id}: {e}")
            return False

    async def _send_channel_notification(
        self, embed: discord.Embed, event_id: int, view: discord.ui.View = None
    ) -> bool:
        """Send notification to configured Discord channel"""
        try:
            if not Config.NOTIFICATION_CHANNEL_ID:
                logger.warning("No notification channel configured")
                return False

            channel = self.bot.get_channel(Config.NOTIFICATION_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed, view=view)
                logger.debug(f"Sent channel notification for event {event_id}")
                return True
            else:
                logger.warning(
                    f"Could not find notification channel {Config.NOTIFICATION_CHANNEL_ID}"
                )
                return False
        except Exception as e:
            logger.error(f"Error sending channel notification: {e}")
            return False
