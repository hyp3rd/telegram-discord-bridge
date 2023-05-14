"""the bridge."""

try:
    from .app import controller
except ImportError as ex:
    raise ex
