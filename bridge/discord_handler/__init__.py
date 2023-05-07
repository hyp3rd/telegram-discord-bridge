"""Initialize the discord_handler module."""

try:
    from .core import (fetch_discord_reference, forward_to_discord,
                       get_mention_roles, is_builtin_mention, start_discord)
    from .health import DiscordClientHealth
except ImportError as ex:
    raise ex
