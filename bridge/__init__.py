"""the bridge."""

try:
    import bridge.discord_handler
    import bridge.openai_handler
    import bridge.telegram_handler.core
    import bridge.utils
except ImportError as ex:
    raise ex
