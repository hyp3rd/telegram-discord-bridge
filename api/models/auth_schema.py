"""Auth Schema."""

from pydantic import BaseModel


class TelegramAuthSchema(BaseModel):
    """Telegram Auth Schema."""
    password: str = ""
    code: str | int = 0


class TelegramAuthResponseSchema(BaseModel):
    """Telegram Auth Response Schema."""
    operation_status: str
