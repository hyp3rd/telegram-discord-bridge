"""Initialize the core module."""

try:
    from .singleton import SingletonMeta
except ImportError as ex:
    raise ex
