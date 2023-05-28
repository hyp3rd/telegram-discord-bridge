"""Process State Enum."""

try:
    from .process_state import ProcessStateEnum
except ImportError as exc:
    raise ImportError('Failed importing ProcessStateEnum') from exc
