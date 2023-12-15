"""the bridge."""

try:
    import bridge.discord
    import bridge.openai.handler
    import bridge.release
    import bridge.telegram.core
    import bridge.utils
except ImportError as ex:
    raise ex
