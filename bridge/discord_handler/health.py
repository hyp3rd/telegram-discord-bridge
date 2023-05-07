"""Core helpers for the Discord Client"""

from typing import Tuple

import discord


class DiscordClientHealth:
    """A simple class to keep context for the client handler function"""
    _instance = None

    def __new__(cls, *args):  # pylint: disable=unused-argument
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def report_status(client: discord.Client, bot_max_latency: float) -> Tuple[str, bool]:
        """Report the health status of a Discord Client"""
        status: str = "Discord Client is healthy and connected"

        if client.latency > bot_max_latency:
            status = "Discord Client's latency is too high"
            return status, False

        if not client.is_ready():
            status = "Discord Client's internal cache is not ready"
            return status, False

        if client.is_closed():
            status = "Discord Client's websocket connection is closed"
            return status, False

        if client.user is None:
            status = "Discord Client is not authenticated"
            return status, False

        return status, True
