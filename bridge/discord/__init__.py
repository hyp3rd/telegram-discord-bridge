"""Initialize the discord_handler module."""

try:
    from .core import DiscordHandler
    from .health import DiscordClientHealth
except ImportError as ex:
    raise ex
