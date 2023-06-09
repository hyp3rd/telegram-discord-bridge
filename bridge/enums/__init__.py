"""Process State Enum."""

try:
    from .process_state import ProcessStateEnum
    from .request_type import RequestTypeEnum
except ImportError as exc:
    raise ImportError('Failed importing ProcessStateEnum') from exc
