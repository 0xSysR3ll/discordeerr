import logging
from typing import Any

import requests

from config import Config

logger = logging.getLogger(__name__)


class SeerrAPI:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or Config.SEERR_URL
        self.api_key = api_key or Config.SEERR_API_KEY
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update(
                {"X-API-Key": self.api_key, "Content-Type": "application/json"}
            )

    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict | None:
        """Make a request to the Seerr API"""
        try:
            url = f"{self.base_url.rstrip('/')}/api/v1/{endpoint.lstrip('/')}"

            if method.upper() == "GET":
                response = self.session.get(url)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data)
            elif method.upper() == "DELETE":
                response = self.session.delete(url)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Seerr API request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in Seerr API request: {e}")
            return None

    def get_users(self) -> list[dict[str, Any]] | None:
        """Get all users from Seerr"""
        try:
            response = self._make_request("user")
            if not response:
                return None

            if isinstance(response, dict) and "results" in response:
                return response["results"]
            elif isinstance(response, list):
                return response
            else:
                logger.warning("Unexpected response format from user endpoint")
                return None

        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Get a specific user by ID"""
        try:
            response = self._make_request(f"user/{user_id}")
            return response
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

    def verify_user_discord_id(self, discord_id: str) -> dict[str, Any] | None:
        """Verify if a Discord ID exists in Seerr"""
        try:
            users = self.get_users()
            if not users:
                return None

            for user in users:
                if isinstance(user, dict):
                    user_id = user.get("id")
                    if not user_id:
                        continue

                    settings = self.get_user_settings(user_id)
                    if settings and isinstance(settings, dict):
                        user_discord_id = settings.get("discordId")
                        if user_discord_id and str(user_discord_id) == str(discord_id):
                            return user

            return None

        except Exception as e:
            logger.error(f"Error verifying Discord ID: {e}")
            return None

    def get_user_settings(self, user_id: int) -> dict[str, Any] | None:
        """Get user settings"""
        try:
            response = self._make_request(f"user/{user_id}/settings/main")
            return response
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return None

    def get_user_requests(
        self, user_id: int, page: int = 1, limit: int = 50
    ) -> dict[str, Any] | None:
        """Get user requests"""
        try:
            response = self._make_request(f"user/{user_id}/requests?page={page}&limit={limit}")
            return response
        except Exception as e:
            logger.error(f"Error getting user requests: {e}")
            return None

    def get_user_stats(self, user_id: int) -> dict[str, Any] | None:
        """Get user request statistics"""
        try:
            response = self._make_request(f"user/{user_id}/requests")
            if not response or not isinstance(response, dict):
                return None

            results = response.get("results", [])
            if not isinstance(results, list):
                return None

            pending_requests = len([r for r in results if r.get("status") == 1])
            approved_requests = len([r for r in results if r.get("status") == 2])
            declined_requests = len([r for r in results if r.get("status") == 3])
            failed_requests = len([r for r in results if r.get("status") == 4])
            completed_requests = len([r for r in results if r.get("status") == 5])

            return {
                "total": len(results),
                "pending": pending_requests,
                "approved": approved_requests,
                "declined": declined_requests,
                "failed": failed_requests,
                "completed": completed_requests,
            }

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return None

    def test_connection(self) -> bool:
        """Test if the Seerr API is accessible"""
        try:
            response = self._make_request("status")
            return response is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
