"""Initialize the discord_handler module."""

try:
    from .core import DiscordHandler
    from .health import DiscordClientHealth
    from .embed import DiscordeEmbedHandler
except ImportError as ex:
    raise ex
