import asyncio
import logging
from threading import Thread

from flask import Flask, jsonify, request

from config import Config
from webhook.handler import WebhookHandler

logger = logging.getLogger(__name__)


class WebhookServer:
    def __init__(self, bot, database, seerr_api):
        self.app = Flask(__name__)
        self.bot = bot
        self.database = database
        self.seerr_api = seerr_api
        self.webhook_handler = WebhookHandler(bot, database, seerr_api)

        self.app.route("/webhook", methods=["POST"])(self.webhook_endpoint)
        self.app.route("/health", methods=["GET"])(self.health_check)

        logging.getLogger("werkzeug").disabled = True

    def webhook_endpoint(self):
        """Handle incoming webhook from Seerr"""
        try:
            if request.method != "POST":
                return jsonify({"error": "Method not allowed"}), 405

            if Config.WEBHOOK_AUTH_HEADER:
                auth_header = request.headers.get("Authorization")
                if not auth_header:
                    return jsonify({"error": "Authorization header required"}), 401

                if auth_header != Config.WEBHOOK_AUTH_HEADER:
                    return jsonify({"error": "Invalid authorization"}), 401

            webhook_data = request.get_json()
            if not webhook_data:
                return jsonify({"error": "Invalid JSON data"}), 400

            event_id = self.database.log_webhook_event(
                event_type=webhook_data.get("notification_type", "unknown"),
                payload=str(webhook_data),
            )

            asyncio.run_coroutine_threadsafe(
                self.webhook_handler.process_webhook(webhook_data), self.bot.loop
            )

            return jsonify({"status": "success", "event_id": event_id}), 200

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return jsonify({"error": "Internal server error"}), 500

    def health_check(self):
        """Health check endpoint"""
        try:
            bot_status = "ready" if self.bot.is_ready() else "not ready"

            try:
                self.database.get_admin_setting("health_check")
                db_status = "connected"
            except Exception:
                db_status = "error"

            seerr_status = "connected" if self.seerr_api.test_connection() else "disconnected"

            return (
                jsonify(
                    {
                        "status": "healthy",
                        "bot": bot_status,
                        "database": db_status,
                        "seerr": seerr_status,
                    }
                ),
                200,
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({"status": "unhealthy", "error": str(e)}), 500

    def run(self):
        """Run the webhook server"""
        try:
            logger.info(f"Starting webhook server on {Config.WEBHOOK_HOST}:{Config.WEBHOOK_PORT}")
            self.app.run(
                host=Config.WEBHOOK_HOST,
                port=Config.WEBHOOK_PORT,
                debug=Config.DEBUG_MODE,
                use_reloader=False,
            )
        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            raise

    def start_in_thread(self):
        """Start the webhook server in a separate thread"""
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("Webhook server started in background thread")
        return self.thread

    def stop(self):
        """Stop the webhook server"""
        logger.info("Stopping webhook server...")
        logger.info("Webhook server stopped")
