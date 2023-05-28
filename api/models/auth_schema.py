"""Auth Schema."""

from pydantic import BaseModel


class TelegramAuthSchema(BaseModel):
    """Telegram Auth Schema."""
    password: str = ""
    code: str | int = 0


class TelegramAuthResponse(BaseModel):
    """Telegram Auth Response Schema."""
    status: str
    message: str
    error: str = ""


class TelegramAuthResponseSchema(BaseModel):
    """Telegram Auth Response Schema."""
    auth: TelegramAuthResponse = TelegramAuthResponse
