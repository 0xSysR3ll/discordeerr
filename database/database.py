import logging
import sqlite3
from contextlib import contextmanager
from typing import Any

from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except Exception as e:
            logger.error(f"Database error: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS seerr_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    discord_id TEXT NOT NULL,
                    seerr_user_id INTEGER NOT NULL,
                    seerr_username TEXT NOT NULL,
                    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(discord_id, seerr_user_id)
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    seerr_user_id INTEGER,
                    payload TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    sent_dm BOOLEAN DEFAULT FALSE,
                    sent_channel BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()
            logger.info("Database initialized successfully")

    def add_user(self, discord_id: str, username: str) -> bool:
        """Add or update a Discord user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO users (discord_id, username, last_seen)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (discord_id, username),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False

    def set_user_admin(self, discord_id: str, is_admin: bool) -> bool:
        """Set admin status for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE users SET is_admin = ? WHERE discord_id = ?
                """,
                    (is_admin, discord_id),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting user admin status: {e}")
            return False

    def set_admin(self, discord_id: str) -> bool:
        """Set the single admin user (removes any existing admin)"""
        return self.set_user_admin(discord_id, True) and self.remove_all_admins_except(discord_id)

    def remove_admin(self) -> bool:
        """Remove admin status from all users"""
        return self.remove_all_admins_except(None)

    def remove_all_admins_except(self, discord_id: str | None) -> bool:
        """Remove admin status from all users except the specified one"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if discord_id:
                    cursor.execute(
                        "UPDATE users SET is_admin = FALSE WHERE discord_id != ?",
                        (discord_id,),
                    )
                else:
                    cursor.execute("UPDATE users SET is_admin = FALSE")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error removing admin status: {e}")
            return False

    def is_user_admin(self, discord_id: str) -> bool:
        """Check if user is admin"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT is_admin FROM users WHERE discord_id = ?",
                    (discord_id,),
                )
                result = cursor.fetchone()
                return result["is_admin"] if result else False
        except Exception as e:
            logger.error(f"Error checking user admin status: {e}")
            return False

    def get_admin(self) -> dict[str, Any] | None:
        """Get the single admin user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT discord_id, username, last_seen
                    FROM users
                    WHERE is_admin = TRUE
                    LIMIT 1
                """
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting admin user: {e}")
            return None

    def link_seerr_account(self, discord_id: str, seerr_user_id: int, seerr_username: str) -> bool:
        """Link a Discord account to a Seerr account"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO seerr_accounts
                    (discord_id, seerr_user_id, seerr_username, linked_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (discord_id, seerr_user_id, seerr_username),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error linking Seerr account: {e}")
            return False

    def force_link_seerr_account(
        self, discord_id: str, seerr_user_id: int, seerr_username: str
    ) -> bool:
        """Force link a Seerr account, overriding any existing links"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM seerr_accounts WHERE discord_id = ?",
                    (discord_id,),
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO seerr_accounts
                    (discord_id, seerr_user_id, seerr_username, linked_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (discord_id, seerr_user_id, seerr_username),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error force linking Seerr account: {e}")
            return False

    def unlink_seerr_account(self, discord_id: str) -> bool:
        """Unlink a Discord account from Seerr"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM seerr_accounts WHERE discord_id = ?",
                    (discord_id,),
                )

                cursor.execute(
                    "DELETE FROM users WHERE discord_id = ? AND is_admin = FALSE",
                    (discord_id,),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error unlinking Seerr account: {e}")
            return False

    def get_seerr_account_by_discord_id(self, discord_id: str) -> dict[str, Any] | None:
        """Get Seerr account linked to a Discord ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM seerr_accounts
                    WHERE discord_id = ?
                    ORDER BY linked_at DESC
                    LIMIT 1
                """,
                    (discord_id,),
                )
                result = cursor.fetchone()
                return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting Seerr account by Discord ID: {e}")
            return None

    def get_discord_id_by_seerr_user_id(self, seerr_user_id: int) -> str | None:
        """Get Discord ID linked to a Seerr user ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT discord_id FROM seerr_accounts
                    WHERE seerr_user_id = ?
                    ORDER BY linked_at DESC
                    LIMIT 1
                """,
                    (seerr_user_id,),
                )
                result = cursor.fetchone()
                return result["discord_id"] if result else None
        except Exception as e:
            logger.error(f"Error getting Discord ID by Seerr user ID: {e}")
            return None

    def log_webhook_event(
        self, event_type: str, seerr_user_id: int = None, payload: str = ""
    ) -> int:
        """Log a webhook event and return the event ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO webhook_events (event_type, seerr_user_id, payload)
                    VALUES (?, ?, ?)
                """,
                    (event_type, seerr_user_id, payload),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error logging webhook event: {e}")
            return None

    def mark_webhook_processed(
        self, event_id: int, sent_dm: bool = False, sent_channel: bool = False
    ) -> bool:
        """Mark a webhook event as processed"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE webhook_events
                    SET processed = TRUE, sent_dm = ?, sent_channel = ?
                    WHERE id = ?
                """,
                    (sent_dm, sent_channel, event_id),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking webhook processed: {e}")
            return False

    def get_admin_setting(self, key: str) -> str | None:
        """Get an admin setting"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM admin_settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result["value"] if result else None
        except Exception as e:
            logger.error(f"Error getting admin setting: {e}")
            return None

    def set_admin_setting(self, key: str, value: str) -> bool:
        """Set an admin setting"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO admin_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, value),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error setting admin setting: {e}")
            return False

    def get_all_users(self) -> list[dict[str, Any]]:
        """Get all users"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT u.*, ja.seerr_username, ja.seerr_user_id, ja.linked_at
                    FROM users u
                    LEFT JOIN seerr_accounts ja ON u.discord_id = ja.discord_id
                    ORDER BY u.last_seen DESC
                """
                )
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []

    def get_user_stats(self, discord_id: str) -> dict[str, Any]:
        """Get comprehensive user statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                user_info = None
                linked_account = None
                webhook_count = 0

                cursor.execute(
                    "SELECT * FROM users WHERE discord_id = ?",
                    (discord_id,),
                )
                result = cursor.fetchone()
                if result:
                    user_info = dict(result)

                cursor.execute(
                    """
                    SELECT * FROM seerr_accounts
                    WHERE discord_id = ?
                    ORDER BY linked_at DESC
                    LIMIT 1
                """,
                    (discord_id,),
                )
                result = cursor.fetchone()
                if result:
                    linked_account = dict(result)

                cursor.execute(
                    "SELECT COUNT(*) as count FROM webhook_events WHERE seerr_user_id = ?",
                    (linked_account["seerr_user_id"] if linked_account else None,),
                )
                result = cursor.fetchone()
                if result:
                    webhook_count = result["count"]

                return {
                    "user_info": user_info,
                    "linked_account": linked_account,
                    "webhook_count": webhook_count,
                }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}
